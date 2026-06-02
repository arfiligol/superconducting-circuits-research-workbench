import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { chmod, copyFile, cp, mkdir, rm } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import { promisify } from "node:util";

const desktopDir = resolve(import.meta.dirname, "..");
const rootDir = resolve(desktopDir, "..", "..");
const runtimeDir = join(desktopDir, "resources", "runtime");
const frontendRuntimeDir = join(runtimeDir, "frontend");
const backendRuntimeDir = join(runtimeDir, "backend");
const coreRuntimeDir = join(runtimeDir, "core");
const runtimeBinDir = join(runtimeDir, "bin");
const execFileAsync = promisify(execFile);

async function main() {
  const standaloneDir = join(rootDir, "app", "frontend", ".next", "standalone");
  if (!existsSync(standaloneDir)) {
    throw new Error("Missing app/frontend/.next/standalone. Run the frontend production build first.");
  }

  await rm(runtimeDir, { force: true, recursive: true });
  await mkdir(runtimeDir, { recursive: true });

  await cp(standaloneDir, frontendRuntimeDir, {
    dereference: true,
    recursive: true,
  });
  await cp(
    join(rootDir, "app", "frontend", ".next", "static"),
    resolveFrontendStaticDestination(standaloneDir),
    {
      dereference: true,
      recursive: true,
    },
  );

  await copyRuntimeTree(join(rootDir, "app", "backend"), backendRuntimeDir);
  await copyRuntimeTree(join(rootDir, "core"), coreRuntimeDir);
  await copySidecarBinary("node");
  await copySidecarBinary("uv");
  await copySidecarBinary("julia");
}

function resolveFrontendStaticDestination(standaloneDir) {
  if (existsSync(join(standaloneDir, "server.js"))) {
    return join(frontendRuntimeDir, ".next", "static");
  }

  return join(frontendRuntimeDir, "frontend", ".next", "static");
}

async function copyRuntimeTree(source, destination) {
  await cp(source, destination, {
    dereference: true,
    filter: (path) => {
      const relativePath = path.slice(source.length).replaceAll("\\", "/");
      return !shouldSkip(relativePath);
    },
    recursive: true,
  });
}

function shouldSkip(relativePath) {
  const parts = relativePath.split("/").filter(Boolean);
  return parts.some((part) =>
    [
      ".DS_Store",
      ".pytest_cache",
      ".ruff_cache",
      ".venv",
      "__pycache__",
      "htmlcov",
      "tests",
    ].includes(part),
  ) || parts.some((part) => part.endsWith(".egg-info"));
}

async function copySidecarBinary(name) {
  const source = await findExecutable(name);
  if (source === null) {
    throw new Error(`Could not find required sidecar binary: ${name}`);
  }

  await mkdir(runtimeBinDir, { recursive: true });
  const destination = join(runtimeBinDir, name);
  await copyFile(source, destination);
  await chmod(destination, 0o755);

  if (process.platform === "darwin") {
    await vendorDarwinDependencies(destination);
  }
}

async function findExecutable(name) {
  const pathEntries = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
    process.env.PATH ?? "",
  ]
    .join(":")
    .split(":")
    .filter(Boolean);

  for (const pathEntry of pathEntries) {
    const candidate = join(pathEntry, name);
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return null;
}

async function vendorDarwinDependencies(entrypoint) {
  const queue = [entrypoint];
  const visited = new Set();
  const filesToSign = new Set([entrypoint]);

  while (queue.length > 0) {
    const current = queue.pop();
    if (current === undefined || visited.has(current)) {
      continue;
    }
    visited.add(current);

    if (current !== entrypoint) {
      await runInstallNameTool(["-id", `@loader_path/${basename(current)}`, current]);
    }

    for (const dependency of await listDarwinDependencies(current)) {
      if (isSystemDarwinDependency(dependency)) {
        continue;
      }

      const destination = join(runtimeBinDir, basename(dependency));
      if (!existsSync(destination)) {
        await copyFile(dependency, destination);
        await chmod(destination, 0o755);
        queue.push(destination);
        filesToSign.add(destination);
      }

      await runInstallNameTool([
        "-change",
        dependency,
        `@loader_path/${basename(dependency)}`,
        current,
      ]);
      filesToSign.add(current);
    }
  }

  for (const file of filesToSign) {
    await execFileAsync("codesign", ["--force", "--sign", "-", file]);
  }
}

async function listDarwinDependencies(path) {
  const { stdout } = await execFileAsync("otool", ["-L", path]);
  return stdout
    .split("\n")
    .slice(1)
    .map((line) => line.trim().split(/\s+/)[0])
    .filter(Boolean)
    .filter((dependency) => !dependency.startsWith("@"));
}

async function runInstallNameTool(args) {
  await execFileAsync("install_name_tool", args);
}

function isSystemDarwinDependency(path) {
  return path.startsWith("/usr/lib/") || path.startsWith("/System/Library/");
}

await main();
