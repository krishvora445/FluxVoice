import queue
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Callable, Optional


try:
    import pygame
except ImportError as exc:
    pygame = None
    _PYGAME_IMPORT_ERROR = exc
else:
    _PYGAME_IMPORT_ERROR = None


@dataclass
class PlaybackItem(object):
    file_path: str
    generation: int
    cleanup_callback: Optional[Callable[[str], None]] = None


class AudioPlayer(object):
    def __init__(self, poll_interval_seconds=0.01, on_playback_start=None, on_playback_stop=None):
        if pygame is None:
            raise RuntimeError(
                "pygame is required for AudioPlayer. Install it with `pip install pygame`."
            ) from _PYGAME_IMPORT_ERROR

        self.poll_interval_seconds = poll_interval_seconds
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._interrupt_event = threading.Event()
        self._state_lock = threading.Lock()
        self._generation = 0
        self._current_item = None
        self._on_playback_start = on_playback_start
        self._on_playback_stop = on_playback_stop

        self._init_mixer()

        self._worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="audio-player-worker",
        )
        self._worker.start()

    def _init_mixer(self):
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def get_generation(self):
        with self._state_lock:
            return self._generation

    def enqueue_file(self, file_path, generation=None, cleanup_callback=None):
        with self._state_lock:
            target_generation = self._generation if generation is None else generation

        self._queue.put(
            PlaybackItem(
                file_path=file_path,
                generation=target_generation,
                cleanup_callback=cleanup_callback,
            )
        )

    def stop(self, clear_queue=True):
        return self.interrupt(clear_queue=clear_queue)

    def interrupt(self, clear_queue=True):
        with self._state_lock:
            self._generation += 1
            generation = self._generation
            has_current = self._current_item is not None

        self._interrupt_event.set()
        self._stop_music()

        if clear_queue:
            self._drain_queue(cleanup=True)

        if not has_current:
            self._interrupt_event.clear()

        return generation

    def _stop_music(self):
        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            traceback.print_exc()

    def _drain_queue(self, cleanup):
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break

            if cleanup:
                self._cleanup_item(item)

    def shutdown(self):
        self._stop_event.set()
        self._interrupt_event.set()
        self._stop_music()
        self._drain_queue(cleanup=True)

        if self._worker.is_alive():
            self._worker.join(timeout=1.5)

        try:
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            traceback.print_exc()

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            with self._state_lock:
                current_generation = self._generation

            if item.generation != current_generation:
                self._cleanup_item(item)
                continue

            self._play_item(item)

    def _play_item(self, item):
        with self._state_lock:
            self._current_item = item

        try:
            pygame.mixer.music.load(item.file_path)
            pygame.mixer.music.play()
            if self._on_playback_start is not None:
                try:
                    self._on_playback_start(item)
                except Exception:
                    traceback.print_exc()

            while pygame.mixer.music.get_busy():
                if self._stop_event.is_set() or self._interrupt_event.is_set():
                    self._stop_music()
                    break

                with self._state_lock:
                    generation_mismatch = item.generation != self._generation
                if generation_mismatch:
                    self._stop_music()
                    break

                time.sleep(self.poll_interval_seconds)
        except Exception:
            traceback.print_exc()
        finally:
            self._cleanup_item(item)
            with self._state_lock:
                self._current_item = None
            self._interrupt_event.clear()
            if self._on_playback_stop is not None:
                try:
                    self._on_playback_stop(item)
                except Exception:
                    traceback.print_exc()

    def _cleanup_item(self, item):
        if item.cleanup_callback is None:
            return

        try:
            item.cleanup_callback(item.file_path)
        except Exception:
            traceback.print_exc()
