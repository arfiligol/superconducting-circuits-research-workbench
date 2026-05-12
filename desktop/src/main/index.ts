import { app, BrowserWindow, ipcMain } from "electron";
import { join } from "node:path";
import { loadDesktopStartupState } from "./state";
import { DesktopRuntimeSupervisor } from "./supervisor";

const userDataDir = process.env.SC_DESKTOP_USER_DATA_DIR;
if (userDataDir) {
  app.setPath("userData", userDataDir);
}

const supervisor = new DesktopRuntimeSupervisor();
let shutdownInProgress = false;
let supervisorStoppedForQuit = false;

function createFallbackHtml(startUrl: string): string {
  return [
    "<!doctype html>",
    "<html lang=\"en\">",
    "  <head>",
    "    <meta charset=\"utf-8\" />",
    "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
    "    <title>Superconducting Circuits Desktop</title>",
    "    <style>",
    "      body { font-family: 'Avenir Next', 'Segoe UI', sans-serif; margin: 0; min-height: 100vh; display: grid; place-items: center; background: #101828; color: #f8fafc; }",
    "      main { max-width: 32rem; padding: 2rem; border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 24px; background: rgba(15, 23, 42, 0.82); }",
    "      h1 { margin-top: 0; font-size: 1.8rem; }",
    "      p { line-height: 1.6; color: #cbd5e1; }",
    "      code { font-family: ui-monospace, monospace; color: #93c5fd; }",
    "    </style>",
    "  </head>",
    "  <body>",
    "    <main>",
    "      <h1>Desktop shell ready</h1>",
    `      <p>Loading <code>${startUrl}</code>.</p>`,
    "    </main>",
    "  </body>",
    "</html>",
  ].join("");
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: "#101828",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: join(__dirname, "../preload/index.js"),
    },
  });

  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  supervisor.setWindow(window);

  const startUrl = process.env.DESKTOP_START_URL;
  if (startUrl) {
    void window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(createFallbackHtml(startUrl))}`);
    void window.loadURL(startUrl);
  }

  return window;
}

ipcMain.handle("desktop:start-local", async (_event, options: unknown) => {
  const state = await loadDesktopStartupState();
  const autoStartLocalRuntime =
    isRecord(options) && typeof options.autoStartLocalRuntime === "boolean"
      ? options.autoStartLocalRuntime
      : undefined;
  await supervisor.startLocal(state, { autoStartLocalRuntime });
});

ipcMain.handle("desktop:start-online", async (_event, options: unknown) => {
  const state = await loadDesktopStartupState();
  const origin = isRecord(options) && typeof options.origin === "string" ? options.origin : undefined;
  await supervisor.startOnline(state, origin);
});

ipcMain.handle("desktop:retry-startup", async () => {
  await supervisor.startFromSavedState();
});

app.whenReady().then(() => {
  createWindow();
  if (!process.env.DESKTOP_START_URL) {
    void supervisor.startFromSavedState();
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", (event) => {
  if (supervisorStoppedForQuit) {
    return;
  }

  event.preventDefault();
  void stopSupervisorThenQuit();
});

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function stopSupervisorThenQuit(): Promise<void> {
  if (shutdownInProgress) {
    return;
  }

  shutdownInProgress = true;
  await supervisor.stop();
  supervisorStoppedForQuit = true;
  app.quit();
}

process.once("SIGTERM", () => {
  void stopSupervisorThenExit();
});

process.once("SIGINT", () => {
  void stopSupervisorThenExit();
});

async function stopSupervisorThenExit(): Promise<void> {
  if (shutdownInProgress) {
    return;
  }

  shutdownInProgress = true;
  await supervisor.stop();
  process.exit(0);
}
