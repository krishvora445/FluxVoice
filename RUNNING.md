# FluxVoice Run Guide

This guide shows exactly **what to run**, **where to run it**, and **how many terminals** you need.

## Quick Summary

- **Electron UI only:** 1 terminal
- **Python engine only:** 1 terminal
- **Side-by-side validation (recommended):** 2 terminals
- **Full Kokoro HTTP flow:** 3 terminals (UI + Python + Kokoro server)

## Terminal 1: Electron UI (Vite + Electron)

Run from:

```powershell
C:\Users\krish\PhpstormProjects\FluxVoice\ui
```

Commands:

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice\ui
npm install
npm run dev
```

What you should see:
- Transparent Electron window
- WhisperPill HUD
- Monochrome connection indicator (hollow when disconnected, solid/glow when connected)

## Terminal 2: Python Core Engine

Run from:

```powershell
C:\Users\krish\PhpstormProjects\FluxVoice
```

Commands (local/offline voice path):

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
.\.venv\Scripts\Activate.ps1
$env:APP_PROFILE="pyttsx3-local"
python -u .\index.py
```

Commands (Kokoro HTTP path):

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
.\.venv\Scripts\Activate.ps1
$env:APP_PROFILE="kokoro-fastapi-local"
python -u .\index.py
```

What you should see in logs:
- `UI state bridge listening on ws://127.0.0.1:8765`
- Hotkey help text

## Terminal 3 (Optional): Kokoro Server

Only needed for `kokoro-fastapi-local` profile.

Command:

```powershell
docker run --rm -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest
```

## Recommended Side-by-Side Test (Milestone 4)

1. Start **Terminal 1** (`ui`, `npm run dev`).
2. Start **Terminal 2** (`python index.py`).
3. Confirm indicator turns connected.
4. Highlight text and press `Alt + Z`.
5. Press `Alt + X` to stop.
6. Press `Ctrl + Alt + Q` to quit Python engine.

## Legacy Tkinter/Pystray Toggle

Legacy UI modules are still present but are now gated by config:

```json
"ui": {
  "enable_legacy_ui": false
}
```

- `false`: Tkinter floating dot and pystray tray **do not execute**.
- `true`: legacy UI starts again.

This lets you run Electron side-by-side without Tkinter interference.

