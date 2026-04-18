import { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage, screen } from "electron";
import type { NativeImage } from "electron";
import { spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const WINDOW_WIDTH = 240;
const WINDOW_HEIGHT = 84;

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let engineProcess: ChildProcess | null = null;
let isShuttingDown = false;

type EngineLaunchSpec = {
  command: string;
  args: string[];
  cwd: string;
  source: string;
};

function fileExists(filePath: string): boolean {
  try {
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function getWorkspaceRootCandidates(): string[] {
  return [
    path.resolve(app.getAppPath(), ".."),
    process.resourcesPath,
    process.cwd(),
  ];
}

function resolveWorkspaceRoot(): string {
  for (const candidate of getWorkspaceRootCandidates()) {
    const configPath = path.join(candidate, "config.json");
    if (fileExists(configPath)) {
      return candidate;
    }
  }

  return path.resolve(app.getAppPath(), "..");
}

function readCustomEnginePathFromConfig(workspaceRoot: string): string | null {
  const configPath = path.join(workspaceRoot, "config.json");
  if (!fileExists(configPath)) {
    return null;
  }

  try {
    const raw = fs.readFileSync(configPath, "utf8");
    const parsed = JSON.parse(raw) as { engine_path?: unknown; ui?: { engine_path?: unknown } };
    const uiValue = parsed.ui?.engine_path;
    const rootValue = parsed.engine_path;
    const candidate = uiValue !== undefined ? uiValue : rootValue;

    if (candidate === null || candidate === undefined) {
      return null;
    }

    if (typeof candidate !== "string") {
      throw new Error("config engine_path must be a string when provided.");
    }

    const trimmed = candidate.trim();
    if (!trimmed) {
      return null;
    }

    return trimmed;
  } catch (error) {
    console.error("[engine] Failed to parse config.json for engine_path:", error);
    return null;
  }
}

function resolveCustomEnginePath(customPath: string): string {
  const resolveBase = app.isPackaged ? process.resourcesPath : app.getAppPath();
  return path.isAbsolute(customPath) ? customPath : path.resolve(resolveBase, customPath);
}

function resolveEngineLaunchSpec(): EngineLaunchSpec {
  const workspaceRoot = resolveWorkspaceRoot();

  // Priority 1: explicit config engine_path override (hard-fail if invalid).
  const customEnginePath = readCustomEnginePathFromConfig(workspaceRoot);
  if (customEnginePath) {
    const resolvedCustomPath = resolveCustomEnginePath(customEnginePath);
    if (!fileExists(resolvedCustomPath)) {
      throw new Error(
        `Invalid config engine_path: '${customEnginePath}' resolved to '${resolvedCustomPath}', but file was not found.`,
      );
    }

    return {
      command: resolvedCustomPath,
      args: [],
      cwd: path.dirname(resolvedCustomPath),
      source: "config.engine_path",
    };
  }

  // Priority 2: bundled executable (future packaging).
  const bundledExe = path.resolve(app.getAppPath(), "..", "engine", "fluxvoice.exe");
  if (fileExists(bundledExe)) {
    return {
      command: bundledExe,
      args: [],
      cwd: path.dirname(bundledExe),
      source: "bundled executable",
    };
  }

  // Priority 3: workspace venv python + index.py.
  const venvPython = path.join(workspaceRoot, ".venv", "Scripts", "python.exe");
  const indexScript = path.join(workspaceRoot, "index.py");

  if (!fileExists(venvPython)) {
    throw new Error(`Python fallback not found: ${venvPython}`);
  }
  if (!fileExists(indexScript)) {
    throw new Error(`Engine entrypoint not found: ${indexScript}`);
  }

  return {
    command: venvPython,
    args: ["-u", indexScript],
    cwd: workspaceRoot,
    source: "workspace .venv",
  };
}

function startEngineProcess() {
  if (engineProcess !== null) {
    return;
  }

  const spec = resolveEngineLaunchSpec();
  console.log(`[engine] starting via ${spec.source}: ${spec.command} ${spec.args.join(" ")}`);

  const child = spawn(spec.command, spec.args, {
    cwd: spec.cwd,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  engineProcess = child;

  child.stdout.on("data", (chunk: Buffer) => {
    process.stdout.write(`[engine] ${chunk.toString()}`);
  });

  child.stderr.on("data", (chunk: Buffer) => {
    process.stderr.write(`[engine:err] ${chunk.toString()}`);
  });

  child.on("exit", (code, signal) => {
    console.log(`[engine] exited (code=${String(code)}, signal=${String(signal)})`);
    engineProcess = null;
    if (!isShuttingDown && code !== 0) {
      console.error("[engine] exited unexpectedly; keeping Electron alive for inspection.");
    }
  });

  child.on("error", (error) => {
    console.error("[engine] spawn error:", error);
    engineProcess = null;
  });
}

function stopEngineProcess() {
  const child = engineProcess;
  if (!child) {
    return;
  }

  try {
    child.kill();
  } catch (error) {
    console.error("[engine] failed to stop child process cleanly:", error);
  }

  // Force terminate process tree on Windows to avoid zombie keyboard-hook holders.
  if (process.platform === "win32" && child.pid) {
    const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      windowsHide: true,
      stdio: "ignore",
    });
    killer.on("error", () => {
      // Best-effort hard kill fallback.
    });
  }

  engineProcess = null;
}

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
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;
  const x = Math.round((width - WINDOW_WIDTH) / 2);
  const y = Math.round(height - WINDOW_HEIGHT - 36);

  mainWindow = new BrowserWindow({
    x,
    y,
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
  try {
    startEngineProcess();
  } catch (error) {
    console.error("[engine] startup failed:", error);
    app.quit();
    return;
  }

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
  isShuttingDown = true;
  stopEngineProcess();
  app.quit();
});

app.on("before-quit", () => {
  isShuttingDown = true;
  stopEngineProcess();
  tray?.destroy();
  tray = null;
});

