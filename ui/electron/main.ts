import { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage } from "electron";
import type { NativeImage } from "electron";
import path from "node:path";

const WINDOW_WIDTH = 240;
const WINDOW_HEIGHT = 84;

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

function createTrayIcon(): NativeImage {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
      <rect x="8" y="8" width="48" height="48" rx="24" fill="#0a0a0a" />
      <circle cx="32" cy="32" r="11" fill="#f5f5f5" />
    </svg>
  `;
  const dataUrl = `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
  return nativeImage.createFromDataURL(dataUrl);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: true,
    hasShadow: false,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  const rendererUrl = process.env.ELECTRON_RENDERER_URL;
  if (rendererUrl) {
    void mainWindow.loadURL(rendererUrl);
  } else {
    const filePath = path.join(__dirname, "..", "dist", "index.html");
    void mainWindow.loadFile(filePath);
  }

  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function createTray() {
  tray = new Tray(createTrayIcon());
  tray.setToolTip("FluxVoice");

  const menu = Menu.buildFromTemplate([
    {
      label: "Settings",
      click: () => {
        mainWindow?.webContents.send("tray:settings");
      },
    },
    {
      type: "separator",
    },
    {
      label: "Quit",
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(menu);
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  ipcMain.handle("app:quit", () => {
    app.quit();
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  // Keep app alive in tray on desktop platforms.
});

app.on("before-quit", () => {
  tray?.destroy();
  tray = null;
});

