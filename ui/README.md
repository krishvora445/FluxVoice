# FluxVoice UI (Milestone 1)

Electron + React shell for the FluxVoice HUD.

## Scope in this milestone

- Transparent, frameless, always-on-top Electron window.
- Native Electron tray menu with `Settings` and `Quit`.
- Preload bridge exposing `window.fluxvoice.quitApp()`.
- Draggable minimalist HUD pill (`-webkit-app-region: drag`).
- Strict grayscale Tailwind/shadcn token baseline.

## Dev run

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice\ui
npm install
npm run dev
```

## Build

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice\ui
npm run build
```

## Notes

- Python engine is intentionally not auto-launched in this milestone.
- WebSocket bridge integration starts in Milestone 2.

