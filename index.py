import ctypes
import json
import os
import tempfile
import threading
import time
import traceback
import urllib.request
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Optional

import keyboard
import pyperclip
import pyttsx3

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


def _read_float_env(name, default_value):
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default_value

    try:
        return float(raw_value)
    except ValueError:
        return default_value


HOTKEY = os.getenv("READ_HOTKEY", "alt+z").strip() or "alt+z"
COPY_TIMEOUT_SECONDS = _read_float_env("COPY_TIMEOUT_SECONDS", 1.5)
COPY_POLL_INTERVAL_SECONDS = _read_float_env("COPY_POLL_INTERVAL_SECONDS", 0.02)
TTS_BACKEND = os.getenv("TTS_BACKEND", "pyttsx3").strip().lower() or "pyttsx3"
TTS_API_URL = os.getenv("TTS_API_URL", "http://127.0.0.1:8000/tts").strip()
TTS_HTTP_TIMEOUT_SECONDS = _read_float_env("TTS_HTTP_TIMEOUT_SECONDS", 30.0)


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
        self._engine = pyttsx3.init()
        self._speak_lock = threading.Lock()

    def speak(self, text):
        with self._speak_lock:
            self._engine.say(text)
            self._engine.runAndWait()


class HttpWavBackend(SpeechBackend):
    def __init__(self, endpoint_url, timeout_seconds=TTS_HTTP_TIMEOUT_SECONDS):
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds

    def speak(self, text):
        payload = json.dumps({"text": text}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/wav",
            },
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            audio_bytes = response.read()
            content_type = response.headers.get("Content-Type", "")

        if not audio_bytes:
            raise RuntimeError("TTS endpoint returned an empty response.")

        if "wav" not in content_type.lower() and "wave" not in content_type.lower():
            print("Warning: HTTP TTS backend expected WAV audio, but the endpoint returned:", content_type)

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
    if TTS_BACKEND in ("http", "kokoro", "api"):
        return HttpWavBackend(TTS_API_URL)

    if TTS_BACKEND != "pyttsx3":
        print("Unknown TTS_BACKEND value; falling back to pyttsx3.")

    return Pyttsx3Backend()


@dataclass
class ReaderConfig(object):
    hotkey: str = HOTKEY
    copy_timeout_seconds: float = COPY_TIMEOUT_SECONDS
    poll_interval_seconds: float = COPY_POLL_INTERVAL_SECONDS


class TextReaderApp(object):
    def __init__(self, backend, config=None):
        self.backend = backend
        self.config = config or ReaderConfig()
        self._processing_lock = threading.Lock()

    def handle_hotkey(self):
        if not self._processing_lock.acquire(False):
            return

        worker = threading.Thread(target=self._process_selection, daemon=True)
        try:
            worker.start()
        except Exception:
            self._processing_lock.release()
            raise

    def _process_selection(self):
        snapshot = None
        text = None

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
            return
        finally:
            if snapshot is not None:
                try:
                    snapshot.restore()
                except Exception:
                    traceback.print_exc()
            self._processing_lock.release()


def main():
    backend = build_tts_backend()
    app = TextReaderApp(backend)

    print("Prototype running...")
    print("1. Highlight any text in any app.")
    print("2. Press '{0}' to read it.".format(app.config.hotkey.upper().replace("+", " + ")))
    print("Press 'Esc' to quit the script.")
    print("Using TTS backend: {0}".format(TTS_BACKEND))
    if isinstance(backend, HttpWavBackend):
        print("HTTP TTS endpoint: {0}".format(backend.endpoint_url))

    keyboard.add_hotkey(app.config.hotkey, app.handle_hotkey, suppress=True, trigger_on_release=True)
    keyboard.wait("esc")


if __name__ == "__main__":
    main()