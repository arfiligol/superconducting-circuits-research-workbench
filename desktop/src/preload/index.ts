import { contextBridge, ipcRenderer } from "electron";

const desktopShell = {
  platform: process.platform,
  versions: {
    chrome: process.versions.chrome,
    electron: process.versions.electron,
    node: process.versions.node,
  },
  retryStartup: () => ipcRenderer.invoke("desktop:retry-startup"),
  startLocal: (options?: { autoStartLocalRuntime?: boolean }) =>
    ipcRenderer.invoke("desktop:start-local", options ?? {}),
  startOnline: (options: { origin: string }) =>
    ipcRenderer.invoke("desktop:start-online", options),
};

contextBridge.exposeInMainWorld("desktopShell", desktopShell);
