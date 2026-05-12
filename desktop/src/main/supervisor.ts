import { app, BrowserWindow } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createWriteStream, type WriteStream } from "node:fs";
import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import {
  createServer as createHttpServer,
  request as requestHttp,
  type IncomingMessage,
  type Server as HttpServer,
  type ServerResponse,
} from "node:http";
import { request as requestHttps } from "node:https";
import { createServer as createTcpServer, connect as connectTcp } from "node:net";
import { constants } from "node:fs";
import { dirname, join } from "node:path";
import {
  type DesktopStartupState,
  type RuntimeMode,
  type ServerTargetSummary,
  loadDesktopStartupState,
  saveDesktopStartupState,
} from "./state";

type ManagedProcessName =
  | "frontend"
  | "redis"
  | "backend"
  | "worker-simulation"
  | "worker-characterization";

type ManagedProcess = {
  name: ManagedProcessName;
  child: ChildProcess;
  logPath: string;
  logStream: WriteStream;
};

type SupervisorStatus = {
  title: string;
  message: string;
  detail?: string;
  mode?: RuntimeMode;
  busy?: boolean;
  state: DesktopStartupState;
  frontendUrl?: string;
  backendUrl?: string;
  logsDir: string;
};

type RuntimePaths = {
  runtimeRoot: string;
  binDir: string;
  frontendServerPath: string;
  backendDir: string;
  runtimeDataDir: string;
  logsDir: string;
};

type LocalRuntimePorts = {
  frontend: number;
  backend: number;
  redis: number;
};

type BackendRuntimeSecrets = {
  sessionSecret: string;
  bootstrapAdminPassword: string;
};

const LOCALHOST = "127.0.0.1";
const FRONTEND_PORT_FALLBACK = 3000;
const BACKEND_PORT_FALLBACK = 8001;
const BACKEND_PROXY_PORT = 8020;
const REDIS_PORT_FALLBACK = 6380;
const STARTUP_TIMEOUT_MS = 120_000;
const HEALTH_TIMEOUT_MS = 2_500;

export class DesktopRuntimeSupervisor {
  private browserWindow: BrowserWindow | null = null;
  private readonly processes = new Map<ManagedProcessName, ManagedProcess>();
  private backendProxy: HttpServer | null = null;
  private activeFrontendUrl: string | null = null;
  private lastStatus: SupervisorStatus | null = null;
  private startupPromise: Promise<void> | null = null;
  private stoppingProcesses = false;

  setWindow(browserWindow: BrowserWindow): void {
    this.browserWindow = browserWindow;
    browserWindow.on("closed", () => {
      if (this.browserWindow === browserWindow) {
        this.browserWindow = null;
      }
    });

    if (this.activeFrontendUrl !== null) {
      void browserWindow.loadURL(this.activeFrontendUrl);
      return;
    }

    if (this.lastStatus !== null) {
      this.showStatus(this.lastStatus);
    }
  }

  async startFromSavedState(): Promise<void> {
    return this.runStartup(() => this.startFromSavedStateImpl());
  }

  async startLocal(
    requestedState: DesktopStartupState,
    options: { autoStartLocalRuntime?: boolean } = {},
  ): Promise<void> {
    return this.runStartup(() => this.startLocalImpl(requestedState, options));
  }

  async startOnline(requestedState: DesktopStartupState, originOverride?: string): Promise<void> {
    return this.runStartup(() => this.startOnlineImpl(requestedState, originOverride));
  }

  async stop(): Promise<void> {
    await this.stopManagedProcesses();
  }

  private async startFromSavedStateImpl(): Promise<void> {
    const state = await loadDesktopStartupState();
    const mode = resolveStartupMode(state);

    if (mode === null) {
      await this.showStartupChooser(state, "Choose a runtime mode to continue.");
      return;
    }

    if (mode === "online") {
      await this.startOnlineImpl(state);
      return;
    }

    await this.startLocalImpl(state);
  }

  private async startLocalImpl(
    requestedState: DesktopStartupState,
    options: { autoStartLocalRuntime?: boolean } = {},
  ): Promise<void> {
    const state: DesktopStartupState = {
      ...requestedState,
      last_runtime_mode: "local",
      auto_start_local_runtime:
        options.autoStartLocalRuntime ?? requestedState.auto_start_local_runtime,
    };
    await saveDesktopStartupState(state);
    await this.stopManagedProcesses();

    const paths = await resolveRuntimePaths();
    const ports = await resolveLocalRuntimePorts();
    const backendUrl = `http://${LOCALHOST}:${ports.backend}`;

    await this.showStatus({
      title: state.auto_start_local_runtime ? "Starting Local Mode" : "Starting Frontend",
      message: state.auto_start_local_runtime
        ? "Launching the local Redis, backend, and worker sidecars."
        : "Launching the frontend without local backend sidecars.",
      busy: true,
      mode: "local",
      state,
      backendUrl,
      logsDir: paths.logsDir,
    });

    try {
      const frontendBackendUrl = await this.startBackendProxy(backendUrl);
      if (state.auto_start_local_runtime) {
        await this.startLocalSidecars(paths, ports, backendUrl);
      }

      const frontendUrl = await this.startFrontend(paths, ports.frontend, frontendBackendUrl, "local");
      this.activeFrontendUrl = frontendUrl;
      await saveDesktopStartupState(state);
      await this.loadFrontend(frontendUrl);
    } catch (error) {
      await this.showStatus({
        title: "Local Mode Could Not Start",
        message: "The shell is still available, but a local runtime process failed to become ready.",
        detail: formatError(error),
        mode: "local",
        state,
        backendUrl,
        logsDir: paths.logsDir,
      });
    }
  }

  private async startOnlineImpl(
    requestedState: DesktopStartupState,
    originOverride?: string,
  ): Promise<void> {
    const targetOrigin = normalizeServerOrigin(
      originOverride ?? requestedState.last_online_target?.origin ?? "",
    );
    if (targetOrigin === null) {
      await this.showStartupChooser(
        {
          ...requestedState,
          last_runtime_mode: "online",
        },
        "Enter an online server target before using Online Mode.",
      );
      return;
    }

    await this.stopManagedProcesses();

    const paths = await resolveRuntimePaths();
    const validatingState: DesktopStartupState = {
      ...requestedState,
      last_runtime_mode: "online",
      last_online_target: {
        origin: targetOrigin,
        label: requestedState.last_online_target?.label ?? null,
        is_active: true,
        validation_status: "target_unreachable",
        last_checked_at: null,
      },
    };

    await this.showStatus({
      title: "Validating Online Target",
      message: `Checking ${targetOrigin} before entering Online Mode.`,
      busy: true,
      mode: "online",
      state: validatingState,
      backendUrl: targetOrigin,
      logsDir: paths.logsDir,
    });

    const validation = await validateServerTarget(targetOrigin);
    if (validation.validation_status !== "validated") {
      await this.showStatus({
        title: "Online Target Unavailable",
        message: "Online Mode was not entered because the server target did not validate.",
        detail: validation.detail,
        mode: "online",
        state: {
          ...validatingState,
          last_online_target: validation,
        },
        backendUrl: targetOrigin,
        logsDir: paths.logsDir,
      });
      return;
    }

    const state: DesktopStartupState = {
      ...requestedState,
      last_runtime_mode: "online",
      last_online_target: validation,
    };
    await saveDesktopStartupState(state);

    try {
      const frontendBackendUrl = await this.startBackendProxy(targetOrigin);
      const frontendPort = await resolvePortFromEnvironment(
        "SC_DESKTOP_FRONTEND_PORT",
        FRONTEND_PORT_FALLBACK,
      );
      const frontendUrl = await this.startFrontend(paths, frontendPort, frontendBackendUrl, "online");
      this.activeFrontendUrl = frontendUrl;
      await this.loadFrontend(frontendUrl);
    } catch (error) {
      await this.showStatus({
        title: "Online Shell Could Not Start",
        message: "The target validated, but the local frontend process failed to become ready.",
        detail: formatError(error),
        mode: "online",
        state,
        backendUrl: targetOrigin,
        logsDir: paths.logsDir,
      });
    }
  }

  private async runStartup(start: () => Promise<void>): Promise<void> {
    if (this.startupPromise !== null) {
      return this.startupPromise;
    }

    const startupPromise = start().finally(() => {
      if (this.startupPromise === startupPromise) {
        this.startupPromise = null;
      }
    });
    this.startupPromise = startupPromise;
    return startupPromise;
  }

  private async startLocalSidecars(
    paths: RuntimePaths,
    ports: LocalRuntimePorts,
    backendUrl: string,
  ): Promise<void> {
    await mkdir(paths.runtimeDataDir, { recursive: true });
    const redisUrl = `redis://${LOCALHOST}:${ports.redis}/0`;

    const redisExecutable = await findExecutable("redis-server", paths.binDir);
    if (redisExecutable === null) {
      throw new Error("redis-server was not found in the packaged runtime or PATH.");
    }

    await this.spawnManagedProcess("redis", redisExecutable, [
      "--bind",
      LOCALHOST,
      "--port",
      String(ports.redis),
      "--save",
      "",
      "--appendonly",
      "no",
      "--dir",
      paths.runtimeDataDir,
    ]);
    await waitForTcpPort(LOCALHOST, ports.redis, STARTUP_TIMEOUT_MS);

    const uvExecutable = await findExecutable("uv", paths.binDir);
    if (uvExecutable === null) {
      throw new Error("uv was not found in the packaged runtime or PATH.");
    }

    const backendSecrets = await loadBackendRuntimeSecrets(paths.runtimeDataDir);
    const backendEnv = buildBackendEnvironment(paths, ports, backendUrl, redisUrl, backendSecrets);
    await this.spawnManagedProcess(
      "backend",
      uvExecutable,
      [
        "run",
        "--project",
        paths.backendDir,
        "python",
        "-c",
        "from src.app.infrastructure.worker_runtime.entrypoints import run_uvicorn_app; run_uvicorn_app()",
      ],
      {
        cwd: paths.backendDir,
        env: backendEnv,
      },
    );
    await waitForHttpOk(`${backendUrl}/health`, STARTUP_TIMEOUT_MS);

    await this.spawnManagedProcess(
      "worker-simulation",
      uvExecutable,
      [
        "run",
        "--project",
        paths.backendDir,
        "python",
        "-c",
        "from src.app.infrastructure.worker_runtime.entrypoints import run_simulation_worker; run_simulation_worker()",
      ],
      {
        cwd: paths.backendDir,
        env: backendEnv,
      },
    );
    await this.spawnManagedProcess(
      "worker-characterization",
      uvExecutable,
      [
        "run",
        "--project",
        paths.backendDir,
        "python",
        "-c",
        "from src.app.infrastructure.worker_runtime.entrypoints import run_characterization_worker; run_characterization_worker()",
      ],
      {
        cwd: paths.backendDir,
        env: backendEnv,
      },
    );
  }

  private async startFrontend(
    paths: RuntimePaths,
    port: number,
    backendBaseUrl: string,
    mode: RuntimeMode,
  ): Promise<string> {
    const frontendUrl = `http://${LOCALHOST}:${port}`;
    const nodeExecutable = await findExecutable("node", paths.binDir);
    if (nodeExecutable === null) {
      throw new Error("node was not found in the packaged runtime or PATH.");
    }

    await this.spawnManagedProcess("frontend", nodeExecutable, [paths.frontendServerPath], {
      cwd: dirname(paths.frontendServerPath),
      env: {
        ...buildProcessEnvironment(paths.binDir),
        BACKEND_BASE_URL: backendBaseUrl,
        HOSTNAME: LOCALHOST,
        NEXT_TELEMETRY_DISABLED: "1",
        PORT: String(port),
        SC_DESKTOP_RUNTIME_MODE: mode,
      },
    });
    await waitForHttpOk(frontendUrl, STARTUP_TIMEOUT_MS);
    return frontendUrl;
  }

  private async startBackendProxy(targetBaseUrl: string): Promise<string> {
    await this.stopBackendProxy();

    const targetUrl = new URL(targetBaseUrl);
    const proxyUrl = `http://${LOCALHOST}:${BACKEND_PROXY_PORT}`;
    const proxy = createHttpServer((request, response) => {
      proxyBackendRequest(request, response, targetUrl);
    });

    await listenHttpServer(proxy, BACKEND_PROXY_PORT);
    this.backendProxy = proxy;
    return proxyUrl;
  }

  private async loadFrontend(frontendUrl: string): Promise<void> {
    if (this.browserWindow === null) {
      return;
    }

    await this.browserWindow.loadURL(frontendUrl);
  }

  private async showStartupChooser(
    state: DesktopStartupState,
    message: string,
  ): Promise<void> {
    const paths = await resolveRuntimePaths();
    await this.showStatus({
      title: "Choose Runtime Mode",
      message,
      state,
      logsDir: paths.logsDir,
    });
  }

  private async showStatus(status: SupervisorStatus): Promise<void> {
    this.lastStatus = status;
    if (this.browserWindow === null) {
      return;
    }

    await this.browserWindow.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(createStatusHtml(status))}`,
    );
  }

  private async spawnManagedProcess(
    name: ManagedProcessName,
    command: string,
    args: string[],
    options: { cwd?: string; env?: NodeJS.ProcessEnv } = {},
  ): Promise<void> {
    const paths = await resolveRuntimePaths();
    await mkdir(paths.logsDir, { recursive: true });

    const logPath = join(paths.logsDir, `${name}.log`);
    const logStream = createWriteStream(logPath, { flags: "a" });
    logStream.write(`\n[${new Date().toISOString()}] ${command} ${args.join(" ")}\n`);

    const child = spawn(command, args, {
      cwd: options.cwd ?? app.getAppPath(),
      detached: process.platform !== "win32",
      env: options.env ?? buildProcessEnvironment(paths.binDir),
      stdio: ["ignore", "pipe", "pipe"],
    });

    child.stdout?.pipe(logStream, { end: false });
    child.stderr?.pipe(logStream, { end: false });
    child.on("exit", (code, signal) => {
      logStream.write(
        `[${new Date().toISOString()}] exited code=${String(code)} signal=${String(signal)}\n`,
      );
      if (this.processes.get(name)?.child === child) {
        this.processes.delete(name);
      }
      if (!this.stoppingProcesses && name !== "frontend") {
        void this.reportUnexpectedExit(name, code, signal);
      }
    });

    child.on("error", (error) => {
      logStream.write(`[${new Date().toISOString()}] spawn error: ${formatError(error)}\n`);
    });

    this.processes.set(name, {
      name,
      child,
      logPath,
      logStream,
    });
  }

  private async reportUnexpectedExit(
    name: ManagedProcessName,
    code: number | null,
    signal: NodeJS.Signals | null,
  ): Promise<void> {
    if (this.lastStatus === null || this.activeFrontendUrl !== null) {
      return;
    }

    await this.showStatus({
      ...this.lastStatus,
      title: "Runtime Process Exited",
      message: `${name} exited before the runtime became ready.`,
      detail: `code=${String(code)} signal=${String(signal)}`,
    });
  }

  private async stopManagedProcesses(): Promise<void> {
    this.activeFrontendUrl = null;
    this.stoppingProcesses = true;
    await this.stopBackendProxy();
    const processes = Array.from(this.processes.values()).reverse();
    await Promise.allSettled(processes.map((processEntry) => terminateManagedProcess(processEntry)));
    this.processes.clear();
    this.stoppingProcesses = false;
  }

  private async stopBackendProxy(): Promise<void> {
    if (this.backendProxy === null) {
      return;
    }

    const proxy = this.backendProxy;
    this.backendProxy = null;
    await new Promise<void>((resolve, reject) => {
      proxy.close((error) => {
        if (error !== undefined) {
          reject(error);
          return;
        }
        resolve();
      });
    });
  }
}

function resolveStartupMode(state: DesktopStartupState): RuntimeMode | null {
  if (state.startup_behavior === "ask_on_launch") {
    return null;
  }

  if (state.startup_behavior === "always_local") {
    return "local";
  }

  if (state.startup_behavior === "always_online") {
    return "online";
  }

  return state.last_runtime_mode;
}

async function resolveRuntimePaths(): Promise<RuntimePaths> {
  const runtimeRoot = join(app.getAppPath(), "resources", "runtime");
  const frontendServerPath = await firstAccessiblePath([
    join(runtimeRoot, "frontend", "frontend", "server.js"),
    join(runtimeRoot, "frontend", "server.js"),
  ]);
  if (frontendServerPath === null) {
    throw new Error(`Missing packaged frontend server under ${runtimeRoot}.`);
  }

  return {
    runtimeRoot,
    binDir: join(runtimeRoot, "bin"),
    frontendServerPath,
    backendDir: join(runtimeRoot, "backend"),
    runtimeDataDir: join(app.getPath("userData"), "runtime"),
    logsDir: join(app.getPath("userData"), "logs"),
  };
}

async function resolveLocalRuntimePorts(): Promise<LocalRuntimePorts> {
  const [frontend, backend, redis] = await Promise.all([
    resolvePortFromEnvironment("SC_DESKTOP_FRONTEND_PORT", FRONTEND_PORT_FALLBACK),
    resolvePortFromEnvironment("SC_DESKTOP_BACKEND_PORT", BACKEND_PORT_FALLBACK),
    resolvePortFromEnvironment("SC_DESKTOP_REDIS_PORT", REDIS_PORT_FALLBACK),
  ]);
  return { frontend, backend, redis };
}

async function resolvePortFromEnvironment(envName: string, fallback: number): Promise<number> {
  const explicitPort = Number.parseInt(process.env[envName] ?? "", 10);
  if (Number.isInteger(explicitPort) && explicitPort > 0 && explicitPort < 65536) {
    return explicitPort;
  }

  return findOpenPort(fallback);
}

function buildBackendEnvironment(
  paths: RuntimePaths,
  ports: LocalRuntimePorts,
  backendUrl: string,
  redisUrl: string,
  secrets: BackendRuntimeSecrets,
): NodeJS.ProcessEnv {
  return {
    ...buildProcessEnvironment(paths.binDir),
    OBJC_DISABLE_INITIALIZE_FORK_SAFETY: "YES",
    PYTHONUNBUFFERED: "1",
    SC_APP_BASE_URL: backendUrl,
    SC_APP_HOST: LOCALHOST,
    SC_APP_PORT: String(ports.backend),
    SC_APP_RELOAD: "false",
    SC_AUDIT_DATABASE_PATH: join(paths.runtimeDataDir, "audit-log.db"),
    SC_BOOTSTRAP_ADMIN_PASSWORD: secrets.bootstrapAdminPassword,
    SC_DATABASE_PATH: join(paths.runtimeDataDir, "database.db"),
    SC_ENVIRONMENT: "desktop",
    SC_REDIS_URL: redisUrl,
    SC_RQ_REDIS_URL: redisUrl,
    SC_SESSION_SECRET: secrets.sessionSecret,
    UV_CACHE_DIR: join(paths.runtimeDataDir, "uv-cache"),
    UV_PROJECT_ENVIRONMENT: join(paths.runtimeDataDir, "backend-venv"),
  };
}

async function loadBackendRuntimeSecrets(runtimeDataDir: string): Promise<BackendRuntimeSecrets> {
  const secretsPath = join(runtimeDataDir, "backend-secrets.json");
  try {
    return coerceBackendRuntimeSecrets(JSON.parse(await readFile(secretsPath, "utf8")));
  } catch {
    const secrets = createBackendRuntimeSecrets();
    await writeFile(secretsPath, `${JSON.stringify(secrets, null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    return secrets;
  }
}

function createBackendRuntimeSecrets(): BackendRuntimeSecrets {
  return {
    sessionSecret: randomBytes(48).toString("base64url"),
    bootstrapAdminPassword: randomBytes(24).toString("base64url"),
  };
}

function coerceBackendRuntimeSecrets(candidate: unknown): BackendRuntimeSecrets {
  if (
    typeof candidate === "object" &&
    candidate !== null &&
    "sessionSecret" in candidate &&
    "bootstrapAdminPassword" in candidate &&
    typeof candidate.sessionSecret === "string" &&
    candidate.sessionSecret.length >= 32 &&
    typeof candidate.bootstrapAdminPassword === "string" &&
    candidate.bootstrapAdminPassword.length >= 16
  ) {
    return {
      sessionSecret: candidate.sessionSecret,
      bootstrapAdminPassword: candidate.bootstrapAdminPassword,
    };
  }

  return createBackendRuntimeSecrets();
}

function buildProcessEnvironment(binDir: string): NodeJS.ProcessEnv {
  const pathValue = [
    binDir,
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
    process.env.PATH ?? "",
  ]
    .filter(Boolean)
    .join(":");

  return {
    ...process.env,
    PATH: pathValue,
  };
}

async function findExecutable(name: string, binDir: string): Promise<string | null> {
  const bundledExecutable = join(binDir, name);
  if (await isExecutable(bundledExecutable)) {
    return bundledExecutable;
  }

  const pathEntries = buildProcessEnvironment(binDir).PATH?.split(":") ?? [];
  for (const pathEntry of pathEntries) {
    const candidate = join(pathEntry, name);
    if (await isExecutable(candidate)) {
      return candidate;
    }
  }

  return null;
}

async function firstAccessiblePath(paths: string[]): Promise<string | null> {
  for (const path of paths) {
    if (await isReadable(path)) {
      return path;
    }
  }

  return null;
}

async function isExecutable(path: string): Promise<boolean> {
  try {
    await access(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function isReadable(path: string): Promise<boolean> {
  try {
    await access(path, constants.R_OK);
    return true;
  } catch {
    return false;
  }
}

async function findOpenPort(startPort: number): Promise<number> {
  for (let port = startPort; port < startPort + 200; port += 1) {
    if (await canBindPort(port)) {
      return port;
    }
  }

  throw new Error(`No open TCP port found from ${startPort}.`);
}

function canBindPort(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = createTcpServer();
    server.once("error", () => {
      resolve(false);
    });
    server.once("listening", () => {
      server.close(() => {
        resolve(true);
      });
    });
    server.listen(port, LOCALHOST);
  });
}

function listenHttpServer(server: HttpServer, port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.once("listening", () => {
      server.off("error", reject);
      resolve();
    });
    server.listen(port, LOCALHOST);
  });
}

function proxyBackendRequest(
  incomingRequest: IncomingMessage,
  outgoingResponse: ServerResponse,
  targetBaseUrl: URL,
): void {
  const targetUrl = new URL(incomingRequest.url ?? "/", targetBaseUrl);
  const headers = { ...incomingRequest.headers };
  delete headers.connection;
  delete headers["content-length"];
  delete headers.host;
  headers.host = targetUrl.host;

  const proxyRequest = (targetUrl.protocol === "https:" ? requestHttps : requestHttp)(
    targetUrl,
    {
      headers,
      method: incomingRequest.method,
    },
    (proxyResponse) => {
      outgoingResponse.writeHead(proxyResponse.statusCode ?? 502, proxyResponse.headers);
      proxyResponse.pipe(outgoingResponse);
    },
  );

  proxyRequest.on("error", (error) => {
    if (outgoingResponse.headersSent) {
      outgoingResponse.destroy(error);
      return;
    }

    outgoingResponse.writeHead(502, { "content-type": "application/json" });
    outgoingResponse.end(
      JSON.stringify({
        detail: "Backend target proxy failed",
        error: formatError(error),
      }),
    );
  });

  incomingRequest.pipe(proxyRequest);
}

async function validateServerTarget(origin: string): Promise<ServerTargetSummary & { detail?: string }> {
  try {
    await waitForHttpOk(`${origin}/health`, HEALTH_TIMEOUT_MS);
    return {
      origin,
      label: null,
      is_active: true,
      validation_status: "validated",
      last_checked_at: new Date().toISOString(),
    };
  } catch (error) {
    return {
      origin,
      label: null,
      is_active: true,
      validation_status: "target_unreachable",
      last_checked_at: new Date().toISOString(),
      detail: formatError(error),
    };
  }
}

function normalizeServerOrigin(value: string): string | null {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return null;
  }

  const withProtocol = /^[a-z][a-z\d+\-.]*:\/\//i.test(trimmedValue)
    ? trimmedValue
    : `http://${trimmedValue}`;

  try {
    return new URL(withProtocol).origin;
  } catch {
    return null;
  }
}

async function waitForHttpOk(url: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown = null;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(2_000),
      });
      if (response.ok) {
        return;
      }
      lastError = new Error(`${url} responded with HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }

    await sleep(500);
  }

  throw new Error(`Timed out waiting for ${url}: ${formatError(lastError)}`);
}

async function waitForTcpPort(host: string, port: number, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown = null;

  while (Date.now() < deadline) {
    try {
      await connectToTcpPort(host, port);
      return;
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }

  throw new Error(`Timed out waiting for ${host}:${port}: ${formatError(lastError)}`);
}

function connectToTcpPort(host: string, port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const socket = connectTcp({ host, port });
    socket.setTimeout(1_000);
    socket.once("connect", () => {
      socket.end();
      resolve();
    });
    socket.once("timeout", () => {
      socket.destroy();
      reject(new Error("connection timed out"));
    });
    socket.once("error", reject);
  });
}

function terminateManagedProcess(processEntry: ManagedProcess): Promise<void> {
  return new Promise((resolve) => {
    const { child, logStream } = processEntry;
    if (child.exitCode !== null || child.killed) {
      logStream.end();
      resolve();
      return;
    }

    const timeout = setTimeout(() => {
      sendSignal(child, "SIGKILL");
    }, 3_000);

    child.once("exit", () => {
      clearTimeout(timeout);
      logStream.end();
      resolve();
    });
    sendSignal(child, "SIGTERM");
  });
}

function sendSignal(child: ChildProcess, signal: NodeJS.Signals): void {
  if (child.pid === undefined) {
    return;
  }

  try {
    if (process.platform !== "win32") {
      process.kill(-child.pid, signal);
      return;
    }
    child.kill(signal);
  } catch (error) {
    if (!isNoSuchProcessError(error)) {
      child.kill(signal);
    }
  }
}

function isNoSuchProcessError(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ESRCH";
}

function createStatusHtml(status: SupervisorStatus): string {
  const onlineTarget = status.state.last_online_target?.origin ?? "";
  const disabledAttribute = status.busy ? "disabled" : "";
  const busyHint = status.busy
    ? `<p class="notice">Startup is in progress. No action is needed unless this page changes to an error state.</p>`
    : "";
  const detail = status.detail
    ? `<pre class="detail">${escapeHtml(status.detail)}</pre>`
    : "";
  const frontendUrl = status.frontendUrl
    ? `<div><span>Frontend</span><code>${escapeHtml(status.frontendUrl)}</code></div>`
    : "";
  const backendUrl = status.backendUrl
    ? `<div><span>Backend Target</span><code>${escapeHtml(status.backendUrl)}</code></div>`
    : "";

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Superconducting Circuits Desktop</title>
    <style>
      :root {
        color-scheme: light dark;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #f4f1ea;
        color: #18212f;
      }
      main {
        width: min(860px, calc(100vw - 48px));
        display: grid;
        gap: 22px;
      }
      h1 {
        margin: 0;
        font-size: 30px;
        line-height: 1.15;
      }
      p {
        margin: 0;
        color: #44546a;
        line-height: 1.55;
      }
      .panel {
        border: 1px solid #d1c6b4;
        border-radius: 8px;
        background: rgba(255, 252, 246, 0.92);
        padding: 24px;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      button {
        border: 1px solid #243244;
        border-radius: 6px;
        background: #243244;
        color: white;
        cursor: pointer;
        font: inherit;
        font-weight: 650;
        min-height: 40px;
        padding: 0 14px;
      }
      button.secondary {
        background: transparent;
        color: #243244;
      }
      button:disabled,
      input:disabled {
        cursor: progress;
        opacity: 0.58;
      }
      label {
        color: #2f4054;
        display: grid;
        gap: 6px;
        font-size: 13px;
        font-weight: 650;
      }
      input[type="text"] {
        border: 1px solid #b8ab98;
        border-radius: 6px;
        font: inherit;
        min-height: 38px;
        padding: 0 10px;
      }
      input[type="checkbox"] {
        inline-size: 16px;
        block-size: 16px;
      }
      .row {
        align-items: center;
        display: flex;
        gap: 8px;
      }
      .grid {
        display: grid;
        gap: 12px;
      }
      .facts {
        display: grid;
        gap: 8px;
        font-size: 13px;
      }
      .facts div {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .facts span {
        color: #667085;
        min-width: 120px;
      }
      code {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 12px;
      }
      .detail {
        background: #1f2937;
        border-radius: 6px;
        color: #f8fafc;
        margin: 0;
        max-height: 180px;
        overflow: auto;
        padding: 12px;
        white-space: pre-wrap;
      }
      .notice {
        border-left: 3px solid #486581;
        color: #334155;
        padding-left: 12px;
      }
      @media (prefers-color-scheme: dark) {
        body {
          background: #111827;
          color: #f8fafc;
        }
        p, label {
          color: #cbd5e1;
        }
        .panel {
          background: #182231;
          border-color: #334155;
        }
        button.secondary {
          border-color: #94a3b8;
          color: #f8fafc;
        }
        input[type="text"] {
          background: #111827;
          border-color: #475569;
          color: #f8fafc;
        }
        .facts span {
          color: #94a3b8;
        }
        .notice {
          color: #cbd5e1;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="panel grid">
        <h1>${escapeHtml(status.title)}</h1>
        <p>${escapeHtml(status.message)}</p>
        ${busyHint}
        ${detail}
        <div class="facts">
          <div><span>Startup Behavior</span><code>${escapeHtml(status.state.startup_behavior)}</code></div>
          <div><span>Last Mode</span><code>${escapeHtml(status.state.last_runtime_mode)}</code></div>
          <div><span>Local Sidecars</span><code>${status.state.auto_start_local_runtime ? "auto-start" : "manual"}</code></div>
          ${frontendUrl}
          ${backendUrl}
          <div><span>Logs</span><code>${escapeHtml(status.logsDir)}</code></div>
        </div>
      </section>
      <section class="panel grid">
        <div class="actions">
          <button id="start-local" ${disabledAttribute}>Start Local Mode</button>
          <button id="frontend-only" class="secondary" ${disabledAttribute}>Frontend Only</button>
          <button id="retry" class="secondary" ${disabledAttribute}>Retry Last Mode</button>
        </div>
        <label class="row">
          <input id="auto-start" type="checkbox" ${status.state.auto_start_local_runtime ? "checked" : ""} ${disabledAttribute} />
          Auto-start local backend and worker sidecars
        </label>
      </section>
      <section class="panel grid">
        <label>
          Online Server Target
          <input id="online-target" type="text" value="${escapeAttribute(onlineTarget)}" placeholder="https://server.example.com" ${disabledAttribute} />
        </label>
        <div class="actions">
          <button id="start-online" ${disabledAttribute}>Use Online Target</button>
        </div>
      </section>
    </main>
    <script>
      const autoStart = document.querySelector("#auto-start");
      const target = document.querySelector("#online-target");
      const disable = () => {
        document.querySelectorAll("button, input").forEach((element) => {
          element.disabled = true;
        });
      };
      document.querySelector("#start-local").addEventListener("click", async () => {
        disable();
        await window.desktopShell.startLocal({ autoStartLocalRuntime: autoStart.checked });
      });
      document.querySelector("#frontend-only").addEventListener("click", async () => {
        disable();
        await window.desktopShell.startLocal({ autoStartLocalRuntime: false });
      });
      document.querySelector("#retry").addEventListener("click", async () => {
        disable();
        await window.desktopShell.retryStartup();
      });
      document.querySelector("#start-online").addEventListener("click", async () => {
        disable();
        await window.desktopShell.startOnline({ origin: target.value });
      });
    </script>
  </body>
</html>`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value: string): string {
  return escapeHtml(value).replaceAll("`", "&#96;");
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.stack ?? error.message;
  }

  return String(error);
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}
