import { execFile } from "node:child_process";
import { constants } from "node:fs";
import { access, lstat, readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { promisify } from "node:util";

const desktopDir = resolve(import.meta.dirname, "..");
const releaseDir = join(desktopDir, "release");
const appName = "Superconducting Circuits";
const defaultAppBundlePath = join(releaseDir, `${appName}-darwin-arm64`, `${appName}.app`);
const execFileAsync = promisify(execFile);

async function main() {
  if (process.platform !== "darwin") {
    throw new Error("macOS app signing is only available on macOS.");
  }

  const appBundlePath = resolve(process.argv[2] ?? defaultAppBundlePath);
  await assertReadable(appBundlePath);
  await signAppBundle(appBundlePath);
  await verifyCodeSignature(appBundlePath);
  console.log(`Signed and verified ${appBundlePath}`);
}

async function signAppBundle(appBundlePath) {
  const targets = await collectSigningTargets(appBundlePath);

  for (const target of targets.machOFiles) {
    await signPath(target);
  }

  for (const target of targets.appBundles) {
    await signPath(target, ["--deep"]);
  }

  for (const target of targets.frameworkBundles) {
    await signPath(target, ["--deep"]);
  }

  await signPath(appBundlePath, ["--deep"]);
}

async function collectSigningTargets(appBundlePath) {
  const appBundles = [];
  const frameworkBundles = [];
  const machOFiles = [];
  const queue = [appBundlePath];

  while (queue.length > 0) {
    const currentPath = queue.pop();
    if (currentPath === undefined) {
      continue;
    }

    const stat = await lstat(currentPath);
    if (stat.isSymbolicLink()) {
      continue;
    }

    if (stat.isDirectory()) {
      if (currentPath !== appBundlePath && currentPath.endsWith(".app")) {
        appBundles.push(currentPath);
      } else if (currentPath.endsWith(".framework")) {
        frameworkBundles.push(currentPath);
      }

      for (const childName of await readdir(currentPath)) {
        queue.push(join(currentPath, childName));
      }
      continue;
    }

    if (stat.isFile() && shouldInspectAsMachO(currentPath, stat.mode) && await isMachO(currentPath)) {
      machOFiles.push(currentPath);
    }
  }

  return {
    appBundles: sortDeepestFirst(appBundles),
    frameworkBundles: sortDeepestFirst(frameworkBundles),
    machOFiles: sortDeepestFirst(machOFiles),
  };
}

function shouldInspectAsMachO(path, mode) {
  return Boolean(mode & 0o111) || path.endsWith(".dylib") || path.endsWith(".so");
}

async function isMachO(path) {
  const { stdout } = await execFileAsync("file", ["-b", path]);
  return stdout.trimStart().startsWith("Mach-O");
}

function sortDeepestFirst(paths) {
  return [...new Set(paths)].sort((a, b) => b.split("/").length - a.split("/").length);
}

async function signPath(path, extraArgs = []) {
  await execFileAsync("codesign", [
    "--force",
    "--sign",
    "-",
    ...extraArgs,
    path,
  ]);
}

async function verifyCodeSignature(appBundlePath) {
  await execFileAsync("codesign", [
    "--verify",
    "--deep",
    "--strict",
    "--verbose=4",
    appBundlePath,
  ]);
}

async function assertReadable(path) {
  try {
    await access(path, constants.R_OK);
  } catch {
    throw new Error(`Missing packaged app at ${path}. Run npm run package:mac-arm64 first.`);
  }
}

await main();
