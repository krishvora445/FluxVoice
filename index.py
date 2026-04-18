import ctypes
import os
import queue
import sys
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
from audio_player import AudioPlayer
from floating_dot import FloatingDotWindow
from state_bridge import UIStateBridge
from tray_icon import SystemTrayIcon
from tts_client import (
    OpenAITTSClient,
    TTSClientError,
    cleanup_temp_file,
    split_text_into_sentence_chunks,
    write_temp_audio_file,
)
from ui_state import UIState, UIStateBus


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
STOP_HOTKEY = APP_CONFIG.stop_hotkey
QUIT_HOTKEY = APP_CONFIG.quit_hotkey
COPY_TIMEOUT_SECONDS = APP_CONFIG.copy_timeout_seconds
COPY_POLL_INTERVAL_SECONDS = APP_CONFIG.copy_poll_interval_seconds
REQUEST_QUEUE_MAXSIZE = APP_CONFIG.request_queue_maxsize
TTS_BACKEND = APP_CONFIG.tts_backend
HTTP_TTS_CONFIG = APP_CONFIG.http_tts
HTTP_TTS_FALLBACK_TO_PYTTSX3 = APP_CONFIG.fallback_to_pyttsx3
WORKSPACE_VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
HTTP_PREFLIGHT_ATTEMPTS = 12
HTTP_PREFLIGHT_RETRY_SECONDS = 1.0
EMPTY_SELECTION_FAST_TIMEOUT_SECONDS = 0.35


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


def wait_for_new_clipboard_text(
    previous_sequence_number,
    timeout_seconds=COPY_TIMEOUT_SECONDS,
    poll_interval_seconds=COPY_POLL_INTERVAL_SECONDS,
    early_no_change_timeout_seconds=None,
):
    started_at = time.monotonic()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        current_sequence_number = _clipboard_sequence_number()
        if current_sequence_number != previous_sequence_number:
            text = read_clipboard_text_best_effort()
            if text is not None and text.strip():
                return text

        if (
            early_no_change_timeout_seconds is not None
            and current_sequence_number == previous_sequence_number
            and time.monotonic() - started_at >= early_no_change_timeout_seconds
        ):
            return None
        time.sleep(poll_interval_seconds)

    return None


class SpeechBackend(object):
    def speak(self, text):
        raise NotImplementedError

    def interrupt(self):
        return None

    def shutdown(self):
        return None


class Pyttsx3Backend(SpeechBackend):
    def __init__(self, on_playback_start=None, on_playback_stop=None):
        self._speak_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._generation = 0
        self._current_engine = None
        self._on_playback_start = on_playback_start
        self._on_playback_stop = on_playback_stop

    def _current_generation(self):
        with self._state_lock:
            return self._generation

    def interrupt(self):
        with self._state_lock:
            self._generation += 1
            engine = self._current_engine

        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    def speak(self, text):
        request_generation = self._current_generation()

        with self._speak_lock:
            if request_generation != self._current_generation():
                return

            engine = pyttsx3.init()
            with self._state_lock:
                self._current_engine = engine

            try:
                engine.say(text)
                if self._on_playback_start is not None:
                    self._on_playback_start(None)
                engine.runAndWait()
            finally:
                if self._on_playback_stop is not None:
                    self._on_playback_stop(None)

                with self._state_lock:
                    if self._current_engine is engine:
                        self._current_engine = None

                try:
                    engine.stop()
                except Exception:
                    pass


class HttpTTSBackend(SpeechBackend):
    def __init__(self, http_config, fallback_backend=None, on_playback_start=None, on_playback_stop=None):
        self.http_config = http_config
        self.fallback_backend = fallback_backend
        self.client = OpenAITTSClient(http_config)
        self.audio_player = AudioPlayer(
            on_playback_start=on_playback_start,
            on_playback_stop=on_playback_stop,
        )
        self._state_lock = threading.Lock()
        self._generation = 0

    def _current_generation(self):
        with self._state_lock:
            return self._generation

    def _is_stale(self, request_generation):
        return request_generation != self._current_generation()

    def interrupt(self):
        with self._state_lock:
            self._generation += 1

        self.audio_player.interrupt(clear_queue=True)

    def shutdown(self):
        self.audio_player.shutdown()
        if self.fallback_backend is not None:
            self.fallback_backend.shutdown()

    def speak(self, text):
        request_generation = self._current_generation()

        try:
            self._speak_http(text, request_generation)
        except Exception as exc:
            if self._is_stale(request_generation):
                return

            if self.fallback_backend is None:
                raise

            print("HTTP TTS failed ({0}); using pyttsx3 fallback.".format(exc))
            self.fallback_backend.speak(text)

    def _speak_http(self, text, request_generation):
        chunks = [text]
        if self.http_config.chunking_enabled:
            chunked_text = split_text_into_sentence_chunks(text, self.http_config.max_chunk_chars)
            if chunked_text:
                chunks = chunked_text

        start_time = time.monotonic()
        first_audio_logged = False

        for chunk in chunks:
            if self._is_stale(request_generation):
                return

            result = self.client.synthesize(chunk)
            if self._is_stale(request_generation):
                return

            if not first_audio_logged:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                mode_label = "streaming" if result.used_streaming else "buffered"
                if len(chunks) > 1:
                    mode_label = mode_label + " + sentence-chunking"
                print("HTTP TTS first-audio latency: {0} ms ({1}).".format(latency_ms, mode_label))
                first_audio_logged = True

            default_extension = "." + str(self.http_config.response_format).lstrip(".")
            temp_audio_path = write_temp_audio_file(
                audio_bytes=result.audio_bytes,
                content_type=result.content_type,
                default_extension=default_extension,
            )

            if self._is_stale(request_generation):
                cleanup_temp_file(temp_audio_path)
                return

            self.audio_player.enqueue_file(
                file_path=temp_audio_path,
                generation=request_generation,
                cleanup_callback=cleanup_temp_file,
            )

        if len(chunks) > 1:
            total_ms = int((time.monotonic() - start_time) * 1000)
            print("HTTP TTS queued {0} chunks in {1} ms.".format(len(chunks), total_ms))


def preflight_http_tts_endpoint(http_config):
    client = OpenAITTSClient(http_config)
    try:
        result = client.synthesize("FluxVoice startup check.")
    except TTSClientError as exc:
        return False, str(exc)

    if not result.audio_bytes:
        return False, "HTTP preflight returned empty audio payload."

    return True, "ok"


def preflight_http_tts_endpoint_with_retry(http_config, attempts=HTTP_PREFLIGHT_ATTEMPTS, retry_seconds=HTTP_PREFLIGHT_RETRY_SECONDS):
    last_message = "unknown"

    for attempt in range(1, max(1, int(attempts)) + 1):
        preflight_ok, preflight_message = preflight_http_tts_endpoint(http_config)
        if preflight_ok:
            return True, "ok"

        last_message = preflight_message
        if attempt < attempts:
            print(
                "HTTP preflight attempt {0}/{1} failed ({2}); retrying in {3:.1f}s...".format(
                    attempt,
                    attempts,
                    preflight_message,
                    retry_seconds,
                )
            )
            time.sleep(retry_seconds)

    return False, last_message


def build_tts_backend(on_playback_start=None, on_playback_stop=None):
    pyttsx3_backend = Pyttsx3Backend(
        on_playback_start=on_playback_start,
        on_playback_stop=on_playback_stop,
    )

    if TTS_BACKEND in ("http", "kokoro", "api", "openai"):
        fallback_backend = pyttsx3_backend if HTTP_TTS_FALLBACK_TO_PYTTSX3 else None
        try:
            http_backend = HttpTTSBackend(
                HTTP_TTS_CONFIG,
                fallback_backend=fallback_backend,
                on_playback_start=on_playback_start,
                on_playback_stop=on_playback_stop,
            )
            preflight_ok, preflight_message = preflight_http_tts_endpoint_with_retry(HTTP_TTS_CONFIG)
            if preflight_ok:
                return http_backend

            raise RuntimeError(preflight_message)
        except Exception as exc:
            if fallback_backend is None:
                raise RuntimeError(
                    "HTTP backend init/preflight failed with fallback disabled: {0}. "
                    "Kokoro endpoint is required: {1}.".format(exc, HTTP_TTS_CONFIG.url)
                )

            print("HTTP backend init/preflight failed ({0}); falling back to pyttsx3.".format(exc))
            print("Tip: start your local TTS server and verify endpoint {0}.".format(HTTP_TTS_CONFIG.url))
            return pyttsx3_backend

    if TTS_BACKEND != "pyttsx3":
        print("Unknown TTS_BACKEND value; falling back to pyttsx3.")

    return pyttsx3_backend


@dataclass
class ReaderConfig(object):
    hotkey: str = HOTKEY
    stop_hotkey: str = STOP_HOTKEY
    quit_hotkey: str = QUIT_HOTKEY
    copy_timeout_seconds: float = COPY_TIMEOUT_SECONDS
    poll_interval_seconds: float = COPY_POLL_INTERVAL_SECONDS
    request_queue_maxsize: int = REQUEST_QUEUE_MAXSIZE


class TextReaderApp(object):
    def __init__(self, backend, state_bus, config=None):
        self.backend = backend
        self.state_bus = state_bus
        self.config = config or ReaderConfig()
        self._request_queue = queue.Queue(maxsize=self.config.request_queue_maxsize)
        self._stop_event = threading.Event()
        self._request_state_lock = threading.Lock()
        self._request_epoch = 0
        self._last_hotkey_at = 0.0
        self._hotkey_debounce_seconds = 0.15
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="text-reader-worker")
        self._worker.start()

    def _bump_request_epoch(self):
        with self._request_state_lock:
            self._request_epoch += 1
            return self._request_epoch

    def _current_request_epoch(self):
        with self._request_state_lock:
            return self._request_epoch

    def handle_hotkey(self):
        if self._stop_event.is_set():
            return

        now = time.monotonic()
        with self._request_state_lock:
            if now - self._last_hotkey_at < self._hotkey_debounce_seconds:
                return
            self._last_hotkey_at = now

        # Read hotkey preempts old playback and pending chunks before processing new selection.
        epoch = self._bump_request_epoch()
        self.backend.interrupt()
        self._clear_pending_requests()

        self._enqueue_read_request(epoch)

    def handle_stop_hotkey(self):
        if self._stop_event.is_set():
            return

        self._bump_request_epoch()
        self.backend.interrupt()
        self._clear_pending_requests()
        self.state_bus.publish(UIState.IDLE)
        print("Playback stopped and queue cleared.")

    def _enqueue_read_request(self, epoch):
        try:
            self._request_queue.put_nowait(epoch)
            if self._request_queue.qsize() > 1:
                print("Reader is busy; request queued.")
        except queue.Full:
            print("Reader queue is full; wait for current speech to finish.")

    def _clear_pending_requests(self):
        while True:
            try:
                self._request_queue.get_nowait()
            except queue.Empty:
                break

    def stop(self):
        self._stop_event.set()
        self.backend.interrupt()
        if self._worker.is_alive():
            self._worker.join(timeout=1.5)
        self.backend.shutdown()

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                epoch = self._request_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                self._process_selection_once(epoch)
            except Exception:
                traceback.print_exc()

    def _process_selection_once(self, epoch):
        snapshot = None

        try:
            snapshot = ClipboardSnapshot.capture()
            previous_sequence_number = _clipboard_sequence_number()
            keyboard.send("ctrl+c")
            text = wait_for_new_clipboard_text(
                previous_sequence_number,
                timeout_seconds=self.config.copy_timeout_seconds,
                poll_interval_seconds=self.config.poll_interval_seconds,
                early_no_change_timeout_seconds=EMPTY_SELECTION_FAST_TIMEOUT_SECONDS,
            )

            if epoch != self._current_request_epoch():
                return

            if not text or not text.strip():
                self.state_bus.publish(UIState.ERROR)
                print("No text was highlighted. (Make sure the text window is active!)")
                time.sleep(1.2)
                self.state_bus.publish(UIState.IDLE)
                return

            preview = text.replace("\r", " ").replace("\n", " ")
            print("Reading: '{0}...'".format(preview[:50]))

            self.state_bus.publish(UIState.PROCESSING)
            self.backend.speak(text)
            if not isinstance(self.backend, HttpTTSBackend):
                self.state_bus.publish(UIState.IDLE)
        except Exception:
            self.state_bus.publish(UIState.IDLE)
            traceback.print_exc()
        finally:
            if snapshot is not None:
                try:
                    snapshot.restore()
                except Exception:
                    traceback.print_exc()


def main():
    shutdown_event = threading.Event()
    state_bus = UIStateBus()
    state_bridge = UIStateBridge(state_bus=state_bus)
    try:
        state_bridge.start()
    except Exception as exc:
        print("Fatal: could not start UI state bridge on ws://127.0.0.1:8765 ({0}).".format(exc))
        print("Tip: make sure only one FluxVoice engine process is running.")
        return
    print("UI state bridge listening on ws://127.0.0.1:8765")

    def on_playback_start(_item):
        state_bus.publish(UIState.PLAYING)

    def on_playback_stop(_item):
        state_bus.publish(UIState.IDLE)

    try:
        backend = build_tts_backend(
            on_playback_start=on_playback_start,
            on_playback_stop=on_playback_stop,
        )
    except Exception as exc:
        print("Fatal: TTS backend startup failed ({0}).".format(exc))
        state_bus.publish(UIState.ERROR)
        time.sleep(1.2)
        state_bus.publish(UIState.IDLE)
        state_bridge.stop()
        return
    app = TextReaderApp(backend, state_bus=state_bus)
    overlay = None
    tray = None

    if APP_CONFIG.enable_legacy_ui:
        overlay = FloatingDotWindow(state_bus=state_bus, shutdown_event=shutdown_event)
        tray = SystemTrayIcon(
            on_quit=lambda: shutdown_event.set(),
            on_settings=lambda: print("Settings clicked (coming soon)."),
        )
        tray.start()
    else:
        print("Legacy Tkinter/pystray UI disabled (ui.enable_legacy_ui=false).")

    def request_shutdown():
        print("Shutdown requested. Exiting...")
        shutdown_event.set()

    print("Prototype running...")
    print("1. Highlight any text in any app.")
    print("2. Press '{0}' to read it.".format(format_hotkey_for_display(app.config.hotkey)))
    print("3. Press '{0}' to stop current playback.".format(format_hotkey_for_display(app.config.stop_hotkey)))
    print("Press '{0}' to quit the script.".format(format_hotkey_for_display(app.config.quit_hotkey)))
    print("Configured TTS backend: {0}".format(TTS_BACKEND))
    print("Runtime TTS backend: {0}".format(type(backend).__name__))
    if TTS_BACKEND in ("http", "kokoro", "api", "openai") and not isinstance(backend, HttpTTSBackend):
        print("Warning: HTTP backend requested, but runtime backend is pyttsx3 fallback.")
    print("Active profile: {0}".format(APP_CONFIG.active_profile))
    if APP_CONFIG.available_profiles:
        print("Available profiles: {0}".format(", ".join(APP_CONFIG.available_profiles)))
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
    stop_hotkey_id = keyboard.add_hotkey(app.config.stop_hotkey, app.handle_stop_hotkey, suppress=True, trigger_on_release=True)
    quit_hotkey_id = keyboard.add_hotkey(app.config.quit_hotkey, request_shutdown, suppress=True, trigger_on_release=True)

    try:
        if overlay is not None:
            overlay.run()
        else:
            while not shutdown_event.is_set():
                time.sleep(0.2)
    except KeyboardInterrupt:
        request_shutdown()
    finally:
        keyboard.remove_hotkey(read_hotkey_id)
        keyboard.remove_hotkey(stop_hotkey_id)
        keyboard.remove_hotkey(quit_hotkey_id)
        if tray is not None:
            tray.stop()
        state_bridge.stop()
        app.stop()


if __name__ == "__main__":
    main()