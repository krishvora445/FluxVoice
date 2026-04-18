import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_CONFIG: Dict[str, Any] = {
    "active_profile": "pyttsx3-local",
    "profiles": {
        "pyttsx3-local": {
            "tts": {
                "backend": "pyttsx3",
                "fallback_to_pyttsx3": True,
            }
        },
        "kokoro-fastapi-local": {
            "tts": {
                "backend": "http",
                "fallback_to_pyttsx3": True,
                "http": {
                    "url": "http://127.0.0.1:8880/v1/audio/speech",
                    "model": "kokoro",
                    "voice": "af_heart",
                    "response_format": "wav",
                    "streaming_mode": "auto",
                },
            }
        },
        "openai-compatible-local": {
            "tts": {
                "backend": "http",
                "fallback_to_pyttsx3": True,
                "http": {
                    "url": "http://127.0.0.1:8091/v1/audio/speech",
                    "model": "tts-1",
                    "voice": "alloy",
                    "response_format": "wav",
                    "streaming_mode": "auto",
                },
            }
        },
    },
    "hotkeys": {
        "read": "alt+z",
        "stop": "alt+x",
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
    "ui": {
        "enable_legacy_ui": False,
    },
}


ENV_KEY_PATHS: Dict[str, Tuple[str, ...]] = {
    "APP_PROFILE": ("active_profile",),
    "READ_HOTKEY": ("hotkeys", "read"),
    "STOP_HOTKEY": ("hotkeys", "stop"),
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
    active_profile: str
    available_profiles: List[str]
    profile_source: str
    profile_applied: bool
    read_hotkey: str
    stop_hotkey: str
    quit_hotkey: str
    copy_timeout_seconds: float
    copy_poll_interval_seconds: float
    request_queue_maxsize: int
    tts_backend: str
    fallback_to_pyttsx3: bool
    http_tts: HttpTTSConfig
    enable_legacy_ui: bool
    config_json_path: str
    env_file_path: str
    loaded_config_json: bool
    loaded_env_file: bool
    override_keys: List[str] = field(default_factory=list)

    @property
    def source_summary(self) -> str:
        return (
            "config.json={0}, .env={1}, overrides={2}, profile={3}({4})".format(
                "loaded" if self.loaded_config_json else "default",
                "loaded" if self.loaded_env_file else "none",
                len(self.override_keys),
                self.active_profile,
                self.profile_source,
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
    profile_source = "default"

    for source_name, source_values in ((".env", env_file_values), ("process", os.environ)):
        if "APP_PROFILE" in source_values:
            _set_nested(merged, ENV_KEY_PATHS["APP_PROFILE"], source_values["APP_PROFILE"])
            override_keys.append("APP_PROFILE")
            profile_source = source_name

    profiles = merged.get("profiles", {})
    available_profiles: List[str] = []
    profile_applied = False
    active_profile = _to_string(merged.get("active_profile"), "pyttsx3-local")

    if isinstance(profiles, dict):
        available_profiles = sorted(str(profile_name) for profile_name in profiles.keys())
        selected_profile = profiles.get(active_profile)
        if isinstance(selected_profile, dict):
            _deep_merge(merged, selected_profile)
            profile_applied = True
        else:
            print("Warning: active_profile '{0}' not found. Using base config only.".format(active_profile))
    else:
        print("Warning: profiles must be a JSON object.")

    for source_values in (env_file_values, os.environ):
        for env_key, path_parts in ENV_KEY_PATHS.items():
            if env_key == "APP_PROFILE":
                continue
            if env_key in source_values:
                _set_nested(merged, path_parts, source_values[env_key])
                override_keys.append(env_key)

    hotkeys = merged.get("hotkeys", {})
    clipboard = merged.get("clipboard", {})
    queue_config = merged.get("queue", {})
    tts_config = merged.get("tts", {})
    http_config = tts_config.get("http", {})
    ui_config = merged.get("ui", {})

    streaming_mode = _to_string(http_config.get("streaming_mode"), "auto").lower()
    if streaming_mode not in {"auto", "on", "off"}:
        streaming_mode = "auto"

    normalized_backend = _to_string(tts_config.get("backend"), "pyttsx3").lower()

    app_config = AppConfig(
        active_profile=active_profile,
        available_profiles=available_profiles,
        profile_source=profile_source,
        profile_applied=profile_applied,
        read_hotkey=_to_string(hotkeys.get("read"), "alt+z"),
        stop_hotkey=_to_string(hotkeys.get("stop"), "alt+x"),
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
        enable_legacy_ui=_to_bool(ui_config.get("enable_legacy_ui"), False),
        config_json_path=str(config_path),
        env_file_path=str(env_path),
        loaded_config_json=loaded_config_json,
        loaded_env_file=bool(env_file_values),
        override_keys=sorted(set(override_keys)),
    )

    return app_config
