import { contextBridge, ipcRenderer } from "electron";

type TraySettingsHandler = () => void;

contextBridge.exposeInMainWorld("fluxvoice", {
  quitApp: () => ipcRenderer.invoke("app:quit"),
  onTraySettings: (handler: TraySettingsHandler) => {
    const wrapped = () => handler();
    ipcRenderer.on("tray:settings", wrapped);
    return () => ipcRenderer.removeListener("tray:settings", wrapped);
  },
});

