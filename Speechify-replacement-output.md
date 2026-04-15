# 📁 PROJECT EXPORT FOR LLMs

## 📊 Project Information

- **Project Name**: `Speechify-replacement`
- **Generated On**: 2026-04-14 12:00:20 (Asia/Calcutta / GMT+06:30)
- **Total Files Processed**: 7
- **Export Tool**: Easy Whole Project to Single Text File for LLMs v1.1.0
- **Tool Author**: Jota / José Guilherme Pandolfi

### ⚙️ Export Configuration

| Setting | Value |
|---------|-------|
| Language | `en` |
| Max File Size | `1 MB` |
| Include Hidden Files | `false` |
| Output Format | `both` |

## 🌳 Project Structure

```
├── 📁 __pycache__/
│   ├── 📄 app_config.cpython-314.pyc (13.87 KB)
│   ├── 📄 index.cpython-314.pyc (27.14 KB)
│   └── 📄 tts_client.cpython-314.pyc (12.15 KB)
├── 📄 app_config.py (8.73 KB)
├── 📄 config.json (604 B)
├── 📄 index.py (15.93 KB)
└── 📄 tts_client.py (7.11 KB)
```

## 📑 Table of Contents

**Project Files:**

- [📄 app_config.py](#📄-app-config-py)
- [📄 config.json](#📄-config-json)
- [📄 index.py](#📄-index-py)
- [📄 tts_client.py](#📄-tts-client-py)

---

## 📈 Project Statistics

| Metric | Count |
|--------|-------|
| Total Files | 7 |
| Total Directories | 1 |
| Text Files | 4 |
| Binary Files | 3 |
| Total Size | 85.52 KB |

### 📄 File Types Distribution

| Extension | Count |
|-----------|-------|
| `.pyc` | 3 |
| `.py` | 3 |
| `.json` | 1 |

## 💻 File Code Contents

## 🚫 Binary/Excluded Files

The following files were not included in the text content:

- `__pycache__/app_config.cpython-314.pyc`
- `__pycache__/index.cpython-314.pyc`
- `__pycache__/tts_client.cpython-314.pyc`

### <a id="📄-app-config-py"></a>📄 `app_config.py`

**File Info:**
- **Size**: 8.73 KB
- **Extension**: `.py`
- **Language**: `python`
- **Location**: `app_config.py`
- **Relative Path**: `root`
- **Created**: 2026-04-14 11:57:23 (Asia/Calcutta / GMT+06:30)
- **Modified**: 2026-04-14 12:00:20 (Asia/Calcutta / GMT+06:30)
- **MD5**: `98f8732647a822f827e2a3561845ca92`
- **SHA256**: `216d14729634e7216d25d8b26ed6228b5518bf7d5e2396ec501a639f6bc30b0f`
- **Encoding**: ASCII

**File code content:**

```python
import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "hotkeys": {
        "read": "ctrl+alt+z",
        "quit": "ctrl+alt+q",
    },
    "clipboard": {
        "copy_timeout_seconds": 1.5,
        "poll_interval_seconds": 0.02,
    },
    "queue": {
        "maxsize": 4,
    },
    "tts": {
        "backend": "pyttsx3",
        "fallback_to_pyttsx3": True,
        "http": {
            "url": "http://127.0.0.1:8000/v1/audio/speech",
            "timeout_seconds": 30.0,
            "streaming_mode": "auto",
            "chunking_enabled": True,
            "max_chunk_chars": 350,
            "model": "kokoro",
            "voice": "af_heart",
            "response_format": "wav",
            "api_key": "",
        },
    },
}


ENV_KEY_PATHS: Dict[str, Tuple[str, ...]] = {
    "READ_HOTKEY": ("hotkeys", "read"),
    "QUIT_HOTKEY": ("hotkeys", "quit"),
    "COPY_TIMEOUT_SECONDS": ("clipboard", "copy_timeout_seconds"),
    "COPY_POLL_INTERVAL_SECONDS": ("clipboard", "poll_interval_seconds"),
    "REQUEST_QUEUE_MAXSIZE": ("queue", "maxsize"),
    "TTS_BACKEND": ("tts", "backend"),
    "TTS_FALLBACK_TO_PYTTSX3": ("tts", "fallback_to_pyttsx3"),
    "TTS_API_URL": ("tts", "http", "url"),
    "TTS_HTTP_TIMEOUT_SECONDS": ("tts", "http", "timeout_seconds"),
    "TTS_STREAMING_MODE": ("tts", "http", "streaming_mode"),
    "TTS_ENABLE_CHUNKING": ("tts", "http", "chunking_enabled"),
    "TTS_MAX_CHUNK_CHARS": ("tts", "http", "max_chunk_chars"),
    "TTS_MODEL": ("tts", "http", "model"),
    "TTS_VOICE": ("tts", "http", "voice"),
    "TTS_RESPONSE_FORMAT": ("tts", "http", "response_format"),
    "TTS_API_KEY": ("tts", "http", "api_key"),
}


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    for key, overlay_value in overlay.items():
        base_value = base.get(key)
        if isinstance(base_value, dict) and isinstance(overlay_value, dict):
            _deep_merge(base_value, overlay_value)
        else:
            base[key] = overlay_value
    return base


def _set_nested(mapping: Dict[str, Any], key_path: Tuple[str, ...], value: Any) -> None:
    current = mapping
    for key in key_path[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[key_path[-1]] = value


def _read_env_file(env_path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (value.startswith("\"") and value.endswith("\"")) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        values[key] = value

    return values


def _to_bool(value: Any, default_value: bool) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False

    if isinstance(value, (int, float)):
        return bool(value)

    return default_value


def _to_int(value: Any, default_value: int, minimum_value: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default_value

    if parsed < minimum_value:
        return default_value

    return parsed


def _to_float(value: Any, default_value: float, minimum_value: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default_value

    if parsed < minimum_value:
        return default_value

    return parsed


def _to_string(value: Any, default_value: str) -> str:
    if value is None:
        return default_value

    text = str(value).strip()
    if not text:
        return default_value

    return text


@dataclass
class HttpTTSConfig(object):
    url: str
    timeout_seconds: float
    streaming_mode: str
    chunking_enabled: bool
    max_chunk_chars: int
    model: str
    voice: str
    response_format: str
    api_key: str


@dataclass
class AppConfig(object):
    read_hotkey: str
    quit_hotkey: str
    copy_timeout_seconds: float
    copy_poll_interval_seconds: float
    request_queue_maxsize: int
    tts_backend: str
    fallback_to_pyttsx3: bool
    http_tts: HttpTTSConfig
    config_json_path: str
    env_file_path: str
    loaded_config_json: bool
    loaded_env_file: bool
    override_keys: List[str] = field(default_factory=list)

    @property
    def source_summary(self) -> str:
        return (
            "config.json={0}, .env={1}, overrides={2}".format(
                "loaded" if self.loaded_config_json else "default",
                "loaded" if self.loaded_env_file else "none",
                len(self.override_keys),
            )
        )


def load_app_config(base_dir: str) -> AppConfig:
    base_path = Path(base_dir)
    config_path_setting = os.getenv("APP_CONFIG_PATH", "").strip()
    config_path = Path(config_path_setting).expanduser() if config_path_setting else (base_path / "config.json")

    merged = copy.deepcopy(DEFAULT_CONFIG)
    loaded_config_json = False

    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(config_data, dict):
                _deep_merge(merged, config_data)
                loaded_config_json = True
            else:
                print("Warning: config.json is not a JSON object. Using defaults.")
        except (OSError, json.JSONDecodeError) as exc:
            print("Warning: failed to parse config.json ({0}). Using defaults.".format(exc))

    env_path = base_path / ".env"
    env_file_values = _read_env_file(env_path)
    override_keys: List[str] = []

    for source_values in (env_file_values, os.environ):
        for env_key, path_parts in ENV_KEY_PATHS.items():
            if env_key in source_values:
                _set_nested(merged, path_parts, source_values[env_key])
                override_keys.append(env_key)

    hotkeys = merged.get("hotkeys", {})
    clipboard = merged.get("clipboard", {})
    queue_config = merged.get("queue", {})
    tts_config = merged.get("tts", {})
    http_config = tts_config.get("http", {})

    streaming_mode = _to_string(http_config.get("streaming_mode"), "auto").lower()
    if streaming_mode not in {"auto", "on", "off"}:
        streaming_mode = "auto"

    normalized_backend = _to_string(tts_config.get("backend"), "pyttsx3").lower()

    app_config = AppConfig(
        read_hotkey=_to_string(hotkeys.get("read"), "ctrl+alt+z"),
        quit_hotkey=_to_string(hotkeys.get("quit"), "ctrl+alt+q"),
        copy_timeout_seconds=_to_float(clipboard.get("copy_timeout_seconds"), 1.5, minimum_value=0.05),
        copy_poll_interval_seconds=_to_float(clipboard.get("poll_interval_seconds"), 0.02, minimum_value=0.005),
        request_queue_maxsize=_to_int(queue_config.get("maxsize"), 4, minimum_value=1),
        tts_backend=normalized_backend,
        fallback_to_pyttsx3=_to_bool(tts_config.get("fallback_to_pyttsx3"), True),
        http_tts=HttpTTSConfig(
            url=_to_string(http_config.get("url"), "http://127.0.0.1:8000/v1/audio/speech"),
            timeout_seconds=_to_float(http_config.get("timeout_seconds"), 30.0, minimum_value=1.0),
            streaming_mode=streaming_mode,
            chunking_enabled=_to_bool(http_config.get("chunking_enabled"), True),
            max_chunk_chars=_to_int(http_config.get("max_chunk_chars"), 350, minimum_value=80),
            model=_to_string(http_config.get("model"), "kokoro"),
            voice=_to_string(http_config.get("voice"), "af_heart"),
            response_format=_to_string(http_config.get("response_format"), "wav").lower(),
            api_key=_to_string(http_config.get("api_key"), ""),
        ),
        config_json_path=str(config_path),
        env_file_path=str(env_path),
        loaded_config_json=loaded_config_json,
        loaded_env_file=bool(env_file_values),
        override_keys=sorted(set(override_keys)),
    )

    return app_config

```

---

### <a id="📄-config-json"></a>📄 `config.json`

**File Info:**
- **Size**: 604 B
- **Extension**: `.json`
- **Language**: `json`
- **Location**: `config.json`
- **Relative Path**: `root`
- **Created**: 2026-04-14 11:58:01 (Asia/Calcutta / GMT+06:30)
- **Modified**: 2026-04-14 12:00:20 (Asia/Calcutta / GMT+06:30)
- **MD5**: `d38162aa9e92162717f608f5a4a21239`
- **SHA256**: `41c88992be98b378971641e97fb2bb5c9aed5f3467aaa89eb25bd79bc685dfd2`
- **Encoding**: ASCII

**File code content:**

```json
{
  "hotkeys": {
    "read": "ctrl+alt+z",
    "quit": "ctrl+alt+q"
  },
  "clipboard": {
    "copy_timeout_seconds": 1.5,
    "poll_interval_seconds": 0.02
  },
  "queue": {
    "maxsize": 4
  },
  "tts": {
    "backend": "pyttsx3",
    "fallback_to_pyttsx3": true,
    "http": {
      "url": "http://127.0.0.1:8000/v1/audio/speech",
      "timeout_seconds": 30.0,
      "streaming_mode": "auto",
      "chunking_enabled": true,
      "max_chunk_chars": 350,
      "model": "kokoro",
      "voice": "af_heart",
      "response_format": "wav",
      "api_key": ""
    }
  }
}

```

---

### <a id="📄-index-py"></a>📄 `index.py`

**File Info:**
- **Size**: 15.93 KB
- **Extension**: `.py`
- **Language**: `python`
- **Location**: `index.py`
- **Relative Path**: `root`
- **Created**: 2026-04-14 10:13:34 (Asia/Calcutta / GMT+06:30)
- **Modified**: 2026-04-14 12:00:20 (Asia/Calcutta / GMT+06:30)
- **MD5**: `de51fdcbc8648737e91b57bd76f7f779`
- **SHA256**: `aa6eb2d45976601db947da6f17dbc71ca8ec9fba399b55b329b31ceccd10b851`
- **Encoding**: ASCII

**File code content:**

```python
import ctypes
import os
import queue
import sys
import tempfile
import threading
import time
import traceback
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Optional

import keyboard
import pyperclip
import pyttsx3

from app_config import AppConfig, load_app_config
from tts_client import OpenAITTSClient, TTSClientError, split_text_into_sentence_chunks

try:
    import winsound
except ImportError:
    winsound = None


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
user32.EnumClipboardFormats.restype = wintypes.UINT
user32.GetClipboardSequenceNumber.argtypes = []
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HANDLE]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
kernel32.GlobalFree.restype = wintypes.HANDLE

CF_TEXT = 1
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_CONFIG: AppConfig = load_app_config(BASE_DIR)

HOTKEY = APP_CONFIG.read_hotkey
QUIT_HOTKEY = APP_CONFIG.quit_hotkey
COPY_TIMEOUT_SECONDS = APP_CONFIG.copy_timeout_seconds
COPY_POLL_INTERVAL_SECONDS = APP_CONFIG.copy_poll_interval_seconds
REQUEST_QUEUE_MAXSIZE = APP_CONFIG.request_queue_maxsize
TTS_BACKEND = APP_CONFIG.tts_backend
HTTP_TTS_CONFIG = APP_CONFIG.http_tts
HTTP_TTS_FALLBACK_TO_PYTTSX3 = APP_CONFIG.fallback_to_pyttsx3
WORKSPACE_VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")


def format_hotkey_for_display(hotkey):
    return hotkey.upper().replace("+", " + ")


def is_running_workspace_venv():
    if not os.path.exists(WORKSPACE_VENV_PYTHON):
        return False

    current_python = os.path.normcase(os.path.abspath(sys.executable))
    expected_python = os.path.normcase(os.path.abspath(WORKSPACE_VENV_PYTHON))
    return current_python == expected_python


def _open_clipboard_with_retry(timeout_seconds=0.25, poll_interval_seconds=0.01):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if user32.OpenClipboard(None):
            return True
        time.sleep(poll_interval_seconds)
    return False


def _clipboard_sequence_number():
    return int(user32.GetClipboardSequenceNumber())


def _read_clipboard_text_from_native_clipboard():
    if not _open_clipboard_with_retry():
        return None

    try:
        unicode_handle = user32.GetClipboardData(CF_UNICODETEXT)
        if unicode_handle:
            pointer = kernel32.GlobalLock(unicode_handle)
            if pointer:
                try:
                    return ctypes.wstring_at(pointer)
                finally:
                    kernel32.GlobalUnlock(unicode_handle)

        ansi_handle = user32.GetClipboardData(CF_TEXT)
        if ansi_handle:
            pointer = kernel32.GlobalLock(ansi_handle)
            if pointer:
                try:
                    raw_bytes = ctypes.string_at(pointer)
                    if raw_bytes:
                        return raw_bytes.decode("mbcs", errors="replace")
                finally:
                    kernel32.GlobalUnlock(ansi_handle)
    finally:
        user32.CloseClipboard()

    return None


def read_clipboard_text_best_effort():
    text = _read_clipboard_text_from_native_clipboard()
    if text is not None:
        return text

    try:
        return pyperclip.paste()
    except Exception:
        return None


@dataclass
class ClipboardEntry(object):
    format_id: int
    data: bytes


@dataclass
class ClipboardSnapshot(object):
    entries: List[ClipboardEntry]
    text_backup: Optional[str] = None

    @classmethod
    def capture(cls):
        text_backup = None
        if pyperclip is not None:
            try:
                clipboard_text = pyperclip.paste()
                if clipboard_text:
                    text_backup = clipboard_text
            except Exception:
                text_backup = None

        entries = []
        if not _open_clipboard_with_retry(timeout_seconds=0.5):
            return cls(entries=entries, text_backup=text_backup)

        try:
            format_id = 0
            while True:
                format_id = user32.EnumClipboardFormats(format_id)
                if format_id == 0:
                    break

                handle = user32.GetClipboardData(format_id)
                if not handle:
                    continue

                size = kernel32.GlobalSize(handle)
                if not size:
                    continue

                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    continue

                try:
                    data = ctypes.string_at(pointer, size)
                finally:
                    kernel32.GlobalUnlock(handle)

                entries.append(ClipboardEntry(format_id=format_id, data=data))
        finally:
            user32.CloseClipboard()

        return cls(entries=entries, text_backup=text_backup)

    def restore(self):
        native_restored_any = False

        if self.entries and _open_clipboard_with_retry(timeout_seconds=0.5):
            try:
                if not user32.EmptyClipboard():
                    print("Warning: clipboard restore could not clear the clipboard.")
                    return

                for entry in self.entries:
                    if not entry.data:
                        continue

                    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(entry.data))
                    if not handle:
                        continue

                    pointer = kernel32.GlobalLock(handle)
                    if not pointer:
                        kernel32.GlobalFree(handle)
                        continue

                    try:
                        ctypes.memmove(pointer, entry.data, len(entry.data))
                    finally:
                        kernel32.GlobalUnlock(handle)

                    if user32.SetClipboardData(entry.format_id, handle):
                        native_restored_any = True
                    else:
                        kernel32.GlobalFree(handle)
            finally:
                user32.CloseClipboard()

        if not native_restored_any and self.text_backup is not None and pyperclip is not None:
            try:
                pyperclip.copy(self.text_backup)
            except Exception:
                traceback.print_exc()


def wait_for_new_clipboard_text(previous_sequence_number, timeout_seconds=COPY_TIMEOUT_SECONDS, poll_interval_seconds=COPY_POLL_INTERVAL_SECONDS):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        current_sequence_number = _clipboard_sequence_number()
        if current_sequence_number != previous_sequence_number:
            text = read_clipboard_text_best_effort()
            if text is not None and text.strip():
                return text
        time.sleep(poll_interval_seconds)

    return None


class SpeechBackend(object):
    def speak(self, text):
        raise NotImplementedError


class Pyttsx3Backend(SpeechBackend):
    def __init__(self):
        self._speak_lock = threading.Lock()

    def speak(self, text):
        with self._speak_lock:
            engine = pyttsx3.init()
            try:
                engine.say(text)
                engine.runAndWait()
            finally:
                try:
                    engine.stop()
                except Exception:
                    pass


class HttpTTSBackend(SpeechBackend):
    def __init__(self, http_config, fallback_backend=None):
        self.http_config = http_config
        self.fallback_backend = fallback_backend
        self.client = OpenAITTSClient(http_config)

    def speak(self, text):
        try:
            self._speak_http(text)
        except Exception as exc:
            if self.fallback_backend is None:
                raise

            print("HTTP TTS failed ({0}); using pyttsx3 fallback.".format(exc))
            self.fallback_backend.speak(text)

    def _speak_http(self, text):
        chunks = [text]
        if self.http_config.chunking_enabled:
            chunked_text = split_text_into_sentence_chunks(text, self.http_config.max_chunk_chars)
            if chunked_text:
                chunks = chunked_text

        start_time = time.monotonic()
        first_audio_logged = False

        for chunk in chunks:
            result = self.client.synthesize(chunk)

            if not first_audio_logged:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                mode_label = "streaming" if result.used_streaming else "buffered"
                if len(chunks) > 1:
                    mode_label = mode_label + " + sentence-chunking"
                print("HTTP TTS first-audio latency: {0} ms ({1}).".format(latency_ms, mode_label))
                first_audio_logged = True

            self._play_audio_bytes(result.audio_bytes, result.content_type)

        if len(chunks) > 1:
            total_ms = int((time.monotonic() - start_time) * 1000)
            print("HTTP TTS finished {0} chunks in {1} ms.".format(len(chunks), total_ms))

    def _play_audio_bytes(self, audio_bytes, content_type):
        if not audio_bytes:
            raise TTSClientError("TTS endpoint returned empty audio bytes.")

        normalized_content_type = (content_type or "").lower()
        if normalized_content_type and "wav" not in normalized_content_type and "wave" not in normalized_content_type:
            raise TTSClientError(
                "Playback currently supports WAV only; endpoint returned content-type '{0}'.".format(content_type)
            )

        if winsound is None:
            raise RuntimeError("winsound is required to play WAV audio on Windows.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file:
            temp_audio_file.write(audio_bytes)
            temp_audio_path = temp_audio_file.name

        try:
            winsound.PlaySound(temp_audio_path, winsound.SND_FILENAME)
        finally:
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass


def build_tts_backend():
    pyttsx3_backend = Pyttsx3Backend()

    if TTS_BACKEND in ("http", "kokoro", "api", "openai"):
        fallback_backend = pyttsx3_backend if HTTP_TTS_FALLBACK_TO_PYTTSX3 else None
        return HttpTTSBackend(HTTP_TTS_CONFIG, fallback_backend=fallback_backend)

    if TTS_BACKEND != "pyttsx3":
        print("Unknown TTS_BACKEND value; falling back to pyttsx3.")

    return pyttsx3_backend


@dataclass
class ReaderConfig(object):
    hotkey: str = HOTKEY
    quit_hotkey: str = QUIT_HOTKEY
    copy_timeout_seconds: float = COPY_TIMEOUT_SECONDS
    poll_interval_seconds: float = COPY_POLL_INTERVAL_SECONDS
    request_queue_maxsize: int = REQUEST_QUEUE_MAXSIZE


class TextReaderApp(object):
    def __init__(self, backend, config=None):
        self.backend = backend
        self.config = config or ReaderConfig()
        self._request_queue = queue.Queue(maxsize=self.config.request_queue_maxsize)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="text-reader-worker")
        self._worker.start()

    def handle_hotkey(self):
        if self._stop_event.is_set():
            return

        try:
            self._request_queue.put_nowait(time.monotonic())
            if self._request_queue.qsize() > 1:
                print("Reader is busy; request queued.")
        except queue.Full:
            print("Reader queue is full; wait for current speech to finish.")

    def stop(self):
        self._stop_event.set()
        if self._worker.is_alive():
            self._worker.join(timeout=1.5)

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                self._request_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                self._process_selection_once()
            except Exception:
                traceback.print_exc()

    def _process_selection_once(self):
        snapshot = None

        try:
            snapshot = ClipboardSnapshot.capture()
            previous_sequence_number = _clipboard_sequence_number()
            keyboard.send("ctrl+c")
            text = wait_for_new_clipboard_text(
                previous_sequence_number,
                timeout_seconds=self.config.copy_timeout_seconds,
                poll_interval_seconds=self.config.poll_interval_seconds,
            )

            if not text or not text.strip():
                print("No text was highlighted. (Make sure the text window is active!)")
                return

            preview = text.replace("\r", " ").replace("\n", " ")
            print("Reading: '{0}...'".format(preview[:50]))

            self.backend.speak(text)
        except Exception:
            traceback.print_exc()
        finally:
            if snapshot is not None:
                try:
                    snapshot.restore()
                except Exception:
                    traceback.print_exc()


def main():
    backend = build_tts_backend()
    app = TextReaderApp(backend)
    shutdown_event = threading.Event()

    def request_shutdown():
        print("Shutdown requested. Exiting...")
        shutdown_event.set()

    print("Prototype running...")
    print("1. Highlight any text in any app.")
    print("2. Press '{0}' to read it.".format(format_hotkey_for_display(app.config.hotkey)))
    print("Press '{0}' to quit the script.".format(format_hotkey_for_display(app.config.quit_hotkey)))
    print("Using TTS backend: {0}".format(TTS_BACKEND))
    print("Config sources: {0}".format(APP_CONFIG.source_summary))
    print("Python interpreter: {0}".format(sys.executable))
    if not is_running_workspace_venv():
        print("Warning: not running workspace .venv interpreter.")
        print("Expected: {0}".format(WORKSPACE_VENV_PYTHON))
    if isinstance(backend, HttpTTSBackend):
        print("HTTP TTS endpoint: {0}".format(backend.http_config.url))
        print("HTTP voice/model: {0}/{1}".format(backend.http_config.voice, backend.http_config.model))
        print("HTTP streaming mode: {0}".format(backend.http_config.streaming_mode))
        print("HTTP chunk fallback enabled: {0}".format(backend.http_config.chunking_enabled))
        print("HTTP pyttsx3 fallback enabled: {0}".format(bool(backend.fallback_backend)))

    read_hotkey_id = keyboard.add_hotkey(app.config.hotkey, app.handle_hotkey, suppress=True, trigger_on_release=True)
    quit_hotkey_id = keyboard.add_hotkey(app.config.quit_hotkey, request_shutdown, suppress=True, trigger_on_release=True)

    try:
        shutdown_event.wait()
    finally:
        keyboard.remove_hotkey(read_hotkey_id)
        keyboard.remove_hotkey(quit_hotkey_id)
        app.stop()


if __name__ == "__main__":
    main()
```

---

### <a id="📄-tts-client-py"></a>📄 `tts_client.py`

**File Info:**
- **Size**: 7.11 KB
- **Extension**: `.py`
- **Language**: `python`
- **Location**: `tts_client.py`
- **Relative Path**: `root`
- **Created**: 2026-04-14 11:57:55 (Asia/Calcutta / GMT+06:30)
- **Modified**: 2026-04-14 12:00:20 (Asia/Calcutta / GMT+06:30)
- **MD5**: `74e788658a9846b432f0b732cee322fe`
- **SHA256**: `92f18e610e8730392436b1f925a52d43e9ef200639953170338f33ab9eb50db9`
- **Encoding**: ASCII

**File code content:**

```python
import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from app_config import HttpTTSConfig


class TTSClientError(RuntimeError):
    pass


@dataclass
class SynthesizedAudio(object):
    audio_bytes: bytes
    content_type: str
    used_streaming: bool


class OpenAITTSClient(object):
    def __init__(self, config: HttpTTSConfig):
        self.config = config

    def synthesize(self, text: str) -> SynthesizedAudio:
        if self.config.streaming_mode in {"on", "auto"}:
            try:
                return self._synthesize_with_stream_flag(text)
            except TTSClientError:
                if self.config.streaming_mode == "on":
                    raise

        return self._synthesize_buffered(text)

    def _synthesize_with_stream_flag(self, text: str) -> SynthesizedAudio:
        payload = self._build_payload(text, stream=True)

        with self._post_json(payload) as response:
            content_type = response.headers.get("Content-Type", "")
            content_type_lower = content_type.lower()

            if "text/event-stream" in content_type_lower:
                audio_bytes = b"".join(self._iter_sse_audio_chunks(response))
                if not audio_bytes:
                    raise TTSClientError("Streaming endpoint returned no audio chunks.")
                return SynthesizedAudio(
                    audio_bytes=audio_bytes,
                    content_type=content_type,
                    used_streaming=True,
                )

            audio_bytes = response.read()
            if not audio_bytes:
                raise TTSClientError("Streaming request returned an empty body.")

            return SynthesizedAudio(
                audio_bytes=audio_bytes,
                content_type=content_type,
                used_streaming=False,
            )

    def _synthesize_buffered(self, text: str) -> SynthesizedAudio:
        payload = self._build_payload(text, stream=False)

        with self._post_json(payload) as response:
            audio_bytes = response.read()
            content_type = response.headers.get("Content-Type", "")

        if not audio_bytes:
            raise TTSClientError("Buffered request returned an empty body.")

        return SynthesizedAudio(
            audio_bytes=audio_bytes,
            content_type=content_type,
            used_streaming=False,
        )

    def _build_payload(self, text: str, stream: bool) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "model": self.config.model,
            "input": text,
            "voice": self.config.voice,
            "response_format": self.config.response_format,
        }

        if stream:
            payload["stream"] = True

        return payload

    def _post_json(self, payload: Dict[str, object]):
        encoded_payload = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

        if self.config.api_key and self.config.api_key.upper() != "EMPTY":
            headers["Authorization"] = "Bearer {0}".format(self.config.api_key)

        request = urllib.request.Request(
            self.config.url,
            data=encoded_payload,
            headers=headers,
        )

        try:
            return urllib.request.urlopen(request, timeout=self.config.timeout_seconds)
        except urllib.error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read(500).decode("utf-8", errors="replace")
            except Exception:
                pass
            raise TTSClientError(
                "TTS HTTP error {0}: {1}".format(exc.code, error_body or exc.reason)
            ) from exc
        except urllib.error.URLError as exc:
            raise TTSClientError("TTS network error: {0}".format(exc.reason)) from exc
        except TimeoutError as exc:
            raise TTSClientError("TTS request timed out.") from exc

    def _iter_sse_audio_chunks(self, response) -> Iterable[bytes]:
        for raw_line in response:
            decoded_line = raw_line.decode("utf-8", errors="replace").strip()
            if not decoded_line or decoded_line.startswith(":"):
                continue
            if not decoded_line.startswith("data:"):
                continue

            data_payload = decoded_line[5:].strip()
            if not data_payload or data_payload in {"[DONE]", "DONE"}:
                continue

            try:
                message = json.loads(data_payload)
            except json.JSONDecodeError:
                continue

            maybe_audio = _extract_base64_audio(message)
            if maybe_audio:
                yield maybe_audio


def _extract_base64_audio(message: Dict[str, object]) -> Optional[bytes]:
    candidates: List[object] = [
        message.get("audio"),
        message.get("audioContent"),
        message.get("delta"),
    ]

    result_data = message.get("result")
    if isinstance(result_data, dict):
        candidates.extend(
            [
                result_data.get("audio"),
                result_data.get("audioContent"),
                result_data.get("delta"),
            ]
        )

    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue

        try:
            return base64.b64decode(candidate)
        except Exception:
            continue

    return None


def split_text_into_sentence_chunks(text: str, max_chunk_chars: int) -> List[str]:
    compact = " ".join(text.split())
    if not compact:
        return []

    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]
    if not sentences:
        return _split_long_text(compact, max_chunk_chars)

    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chunk_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_text(sentence, max_chunk_chars))
            continue

        if not current:
            current = sentence
            continue

        proposal = "{0} {1}".format(current, sentence)
        if len(proposal) <= max_chunk_chars:
            current = proposal
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def _split_long_text(text: str, max_chunk_chars: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    pieces: List[str] = []
    current = words[0]

    for word in words[1:]:
        proposal = "{0} {1}".format(current, word)
        if len(proposal) <= max_chunk_chars:
            current = proposal
            continue

        pieces.append(current)
        current = word

    if current:
        pieces.append(current)

    return pieces

```

---

