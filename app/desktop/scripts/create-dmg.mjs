import { execFile } from "node:child_process";
import { constants } from "node:fs";
import { access, lstat, mkdir, readFile, readdir, readlink, rm, symlink } from "node:fs/promises";
import { join, resolve } from "node:path";
import { promisify } from "node:util";

const desktopDir = resolve(import.meta.dirname, "..");
const releaseDir = join(desktopDir, "release");
const appName = "Superconducting Circuits";
const appBundlePath = join(releaseDir, `${appName}-darwin-arm64`, `${appName}.app`);
const dmgRootDir = join(releaseDir, "dmg-root-darwin-arm64");
const execFileAsync = promisify(execFile);

async function main() {
  if (process.platform !== "darwin") {
    throw new Error("DMG packaging is only available on macOS.");
  }

  await assertReadable(appBundlePath);
  const packageVersion = await readPackageVersion();
  const dmgPath = join(releaseDir, `${appName.replaceAll(" ", "-")}-${packageVersion}-darwin-arm64.dmg`);
  await rm(dmgRootDir, { force: true, recursive: true });
  await rm(dmgPath, { force: true });
  await mkdir(dmgRootDir, { recursive: true });
  const stagedAppPath = join(dmgRootDir, `${appName}.app`);
  await execFileAsync("ditto", [appBundlePath, stagedAppPath]);
  await validateAppBundle(stagedAppPath);
  await verifyCodeSignature(stagedAppPath);
  await symlink("/Applications", join(dmgRootDir, "Applications"));
  await execFileAsync("hdiutil", [
    "create",
    "-volname",
    appName,
    "-srcfolder",
    dmgRootDir,
    "-ov",
    "-format",
    "UDZO",
    dmgPath,
  ]);
  await rm(dmgRootDir, { force: true, recursive: true });
  console.log(`Created ${dmgPath}`);
}

async function validateAppBundle(stagedAppPath) {
  const frameworkPath = join(
    stagedAppPath,
    "Contents",
    "Frameworks",
    "Electron Framework.framework",
    "Electron Framework",
  );
  await assertReadable(frameworkPath);

  for (const entry of await listSymlinks(stagedAppPath)) {
    if (entry.target.startsWith("/")) {
      throw new Error(
        `App bundle contains an absolute symlink: ${entry.path} -> ${entry.target}`,
      );
    }
  }
}

async function verifyCodeSignature(stagedAppPath) {
  await execFileAsync("codesign", [
    "--verify",
    "--deep",
    "--strict",
    "--verbose=4",
    stagedAppPath,
  ]);
}

async function listSymlinks(rootPath) {
  const symlinks = [];
  const queue = [rootPath];
  while (queue.length > 0) {
    const currentPath = queue.pop();
    if (currentPath === undefined) {
      continue;
    }

    const stat = await lstat(currentPath);
    if (stat.isSymbolicLink()) {
      symlinks.push({
        path: currentPath,
        target: await readlink(currentPath),
      });
      continue;
    }

    if (!stat.isDirectory()) {
      continue;
    }

    for (const childName of await readdir(currentPath)) {
      queue.push(join(currentPath, childName));
    }
  }

  return symlinks;
}

async function readPackageVersion() {
  const packageJson = JSON.parse(await readFile(join(desktopDir, "package.json"), "utf8"));
  if (typeof packageJson.version !== "string" || packageJson.version.length === 0) {
    throw new Error("desktop/package.json must define a non-empty version.");
  }

  return packageJson.version;
}

async function assertReadable(path) {
  try {
    await access(path, constants.R_OK);
  } catch {
    throw new Error(`Missing packaged app at ${path}. Run npm run package:mac-arm64 first.`);
  }
}

await main();
