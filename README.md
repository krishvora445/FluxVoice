# FluxVoice 

A lightweight, fully local, system-wide text-to-speech reader for Windows. 

Tired of copying and pasting text into browser tabs or paying for cloud-based TTS subscriptions? **FluxVoice** runs silently in the background. Just highlight text in *any* application—your IDE, a browser, or a PDF—hit your global hotkey, and instantly hear it read back in a natural, human-quality voice.

### ✨ Features
* **Global OS Integration:** Works seamlessly across every Windows application.
* **100% Local Processing:** No network bottlenecks, no cloud APIs, and complete data privacy.
* **Frictionless Workflow:** Highlight -> `Alt + Z` -> Listen. 
* **Customizable Audio:** Built to hook into high-fidelity open-source TTS engines like Kokoro.

## Quick Setup (Windows)

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python .\index.py
```

## Switch To Local Kokoro (OpenAI-Compatible HTTP)

1. Start local Kokoro server (use the same port configured in `config.json` profile `kokoro-fastapi-local`).
2. Set `APP_PROFILE=kokoro-fastapi-local` in `.env`.
3. Restart `index.py`.

Helper script:

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
.\setup_kokoro_fastapi.ps1
```

Optional endpoint smoke test (sends real `POST` request):

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
.\setup_kokoro_fastapi.ps1 -CheckEndpoint -SmokeTest
```

If your configured endpoint is `http://127.0.0.1:8880/v1/audio/speech`, start Kokoro with Docker Compose:

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
docker compose up -d
```

To stop it later:

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
docker compose down
```

Notes:
- `GET /v1/audio/speech` returning `405 Method Not Allowed` in browser logs is expected; this endpoint only supports `POST`.
- If speech sounds robotic, check startup logs for `Runtime TTS backend: Pyttsx3Backend` (that means HTTP was not active and fallback was used).

## UI State Bridge (Milestone 2)

FluxVoice now exposes a local WebSocket state stream on `ws://127.0.0.1:8765`.

- Payload format:
  - `type`: event type (`state_change`)
  - `timestamp`: unix timestamp in seconds
  - `payload.state`: one of `idle`, `processing`, `playing`

Smoke test:

```powershell
cd C:\Users\krish\PhpstormProjects\FluxVoice
.\.venv\Scripts\python.exe .\state_bridge_smoke_test.py
```

