import { app } from "electron";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

export type RuntimeMode = "local" | "online";

export type StartupBehavior =
  | "restore_last_mode"
  | "always_local"
  | "always_online"
  | "ask_on_launch";

export type ServerTargetValidationStatus =
  | "validated"
  | "target_validation_failed"
  | "target_unreachable"
  | "target_incompatible"
  | "online_target_rejected";

export type ServerTargetSummary = {
  origin: string;
  label: string | null;
  is_active: boolean;
  validation_status: ServerTargetValidationStatus;
  last_checked_at: string | null;
};

export type DesktopStartupState = {
  startup_behavior: StartupBehavior;
  last_runtime_mode: RuntimeMode;
  last_online_target: ServerTargetSummary | null;
  auto_start_local_runtime: boolean;
};

const DEFAULT_STARTUP_STATE: DesktopStartupState = {
  startup_behavior: "restore_last_mode",
  last_runtime_mode: "local",
  last_online_target: null,
  auto_start_local_runtime: true,
};

const RUNTIME_MODES = new Set<RuntimeMode>(["local", "online"]);
const STARTUP_BEHAVIORS = new Set<StartupBehavior>([
  "restore_last_mode",
  "always_local",
  "always_online",
  "ask_on_launch",
]);
const VALIDATION_STATUSES = new Set<ServerTargetValidationStatus>([
  "validated",
  "target_validation_failed",
  "target_unreachable",
  "target_incompatible",
  "online_target_rejected",
]);

export function getStartupStatePath(): string {
  return join(app.getPath("userData"), "connection-state.json");
}

export async function loadDesktopStartupState(): Promise<DesktopStartupState> {
  const state = await readPersistedState();
  return applyEnvironmentOverrides(state);
}

export async function saveDesktopStartupState(state: DesktopStartupState): Promise<void> {
  const statePath = getStartupStatePath();
  await mkdir(dirname(statePath), { recursive: true });
  await writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

function applyEnvironmentOverrides(state: DesktopStartupState): DesktopStartupState {
  const nextState: DesktopStartupState = { ...state };

  const startupBehavior = process.env.SC_DESKTOP_STARTUP_BEHAVIOR;
  if (isStartupBehavior(startupBehavior)) {
    nextState.startup_behavior = startupBehavior;
  }

  const runtimeMode = process.env.SC_DESKTOP_RUNTIME_MODE;
  if (isRuntimeMode(runtimeMode)) {
    nextState.last_runtime_mode = runtimeMode;
  }

  const autoStart = parseBoolean(process.env.SC_DESKTOP_AUTO_START_LOCAL_RUNTIME);
  if (autoStart !== null) {
    nextState.auto_start_local_runtime = autoStart;
  }

  const onlineTarget = process.env.SC_DESKTOP_ONLINE_TARGET?.trim();
  if (onlineTarget) {
    nextState.last_online_target = {
      origin: onlineTarget,
      label: process.env.SC_DESKTOP_ONLINE_TARGET_LABEL?.trim() || null,
      is_active: true,
      validation_status: "validated",
      last_checked_at: null,
    };
  }

  return nextState;
}

async function readPersistedState(): Promise<DesktopStartupState> {
  try {
    const rawState = await readFile(getStartupStatePath(), "utf8");
    return coerceDesktopStartupState(JSON.parse(rawState));
  } catch (error) {
    if (isNodeError(error) && error.code === "ENOENT") {
      return { ...DEFAULT_STARTUP_STATE };
    }
    return { ...DEFAULT_STARTUP_STATE };
  }
}

function coerceDesktopStartupState(candidate: unknown): DesktopStartupState {
  if (!isRecord(candidate)) {
    return { ...DEFAULT_STARTUP_STATE };
  }

  return {
    startup_behavior: isStartupBehavior(candidate.startup_behavior)
      ? candidate.startup_behavior
      : DEFAULT_STARTUP_STATE.startup_behavior,
    last_runtime_mode: isRuntimeMode(candidate.last_runtime_mode)
      ? candidate.last_runtime_mode
      : DEFAULT_STARTUP_STATE.last_runtime_mode,
    last_online_target: coerceServerTargetSummary(candidate.last_online_target),
    auto_start_local_runtime:
      typeof candidate.auto_start_local_runtime === "boolean"
        ? candidate.auto_start_local_runtime
        : DEFAULT_STARTUP_STATE.auto_start_local_runtime,
  };
}

function coerceServerTargetSummary(candidate: unknown): ServerTargetSummary | null {
  if (!isRecord(candidate) || typeof candidate.origin !== "string") {
    return null;
  }

  return {
    origin: candidate.origin,
    label: typeof candidate.label === "string" ? candidate.label : null,
    is_active: typeof candidate.is_active === "boolean" ? candidate.is_active : true,
    validation_status: isServerTargetValidationStatus(candidate.validation_status)
      ? candidate.validation_status
      : "target_validation_failed",
    last_checked_at:
      typeof candidate.last_checked_at === "string" ? candidate.last_checked_at : null,
  };
}

function isRuntimeMode(value: unknown): value is RuntimeMode {
  return typeof value === "string" && RUNTIME_MODES.has(value as RuntimeMode);
}

function isStartupBehavior(value: unknown): value is StartupBehavior {
  return typeof value === "string" && STARTUP_BEHAVIORS.has(value as StartupBehavior);
}

function isServerTargetValidationStatus(value: unknown): value is ServerTargetValidationStatus {
  return typeof value === "string" && VALIDATION_STATUSES.has(value as ServerTargetValidationStatus);
}

function parseBoolean(value: string | undefined): boolean | null {
  if (value === undefined) {
    return null;
  }

  if (["1", "true", "yes", "on"].includes(value.toLowerCase())) {
    return true;
  }

  if (["0", "false", "no", "off"].includes(value.toLowerCase())) {
    return false;
  }

  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && "code" in error;
}
