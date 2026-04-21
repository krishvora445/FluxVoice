import queue
import threading
import traceback
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


try:
    import sounddevice as sd
except ImportError as exc:
    sd = None
    _SOUNDDEVICE_IMPORT_ERROR = exc
else:
    _SOUNDDEVICE_IMPORT_ERROR = None


@dataclass
class PlaybackItem(object):
    audio_chunks: Iterable[bytes]
    generation: int
    close_callback: Optional[Callable[[], None]] = None


class _WavChunkDecoder(object):
    def __init__(self):
        self._buffer = bytearray()
        self._header_parsed = False
        self._channels = None
        self._sample_rate = None
        self._sample_width_bytes = None
        self._bytes_per_frame = None
        self._data_size = None
        self._data_started = False
        self._data_emitted = 0

    @property
    def ready(self):
        return self._header_parsed and self._data_started

    @property
    def channels(self):
        return self._channels

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def sample_width_bytes(self):
        return self._sample_width_bytes

    def feed(self, chunk: bytes):
        if chunk:
            self._buffer.extend(chunk)

        if not self._header_parsed:
            self._try_parse_header()

        return self._drain_pcm()

    def flush(self):
        if not self._header_parsed:
            return []

        if self._bytes_per_frame and self._buffer:
            remainder = len(self._buffer) % self._bytes_per_frame
            if remainder:
                del self._buffer[-remainder:]

        if not self._buffer:
            return []

        out = bytes(self._buffer)
        self._buffer.clear()
        return [out]

    def _try_parse_header(self):
        if len(self._buffer) < 12:
            return

        if bytes(self._buffer[0:4]) != b"RIFF" or bytes(self._buffer[8:12]) != b"WAVE":
            raise RuntimeError("Streaming playback only supports WAV/RIFF audio.")

        offset = 12
        data_chunk_offset = None
        data_chunk_size = None

        while offset + 8 <= len(self._buffer):
            chunk_id = bytes(self._buffer[offset : offset + 4])
            chunk_size = int.from_bytes(self._buffer[offset + 4 : offset + 8], "little")
            data_start = offset + 8
            if chunk_id == b"data":
                data_chunk_offset = data_start
                data_chunk_size = chunk_size
                break

            if chunk_id == b"fmt ":
                if data_start + 16 > len(self._buffer):
                    break
                payload = bytes(self._buffer[data_start : data_start + min(chunk_size, 16)])
                if len(payload) < 16:
                    raise RuntimeError("Invalid WAV header: fmt chunk is too short.")
                audio_format = int.from_bytes(payload[0:2], "little")
                channels = int.from_bytes(payload[2:4], "little")
                sample_rate = int.from_bytes(payload[4:8], "little")
                bits_per_sample = int.from_bytes(payload[14:16], "little")

                if audio_format != 1:
                    raise RuntimeError("Streaming playback only supports PCM WAV (format=1).")
                if channels <= 0 or sample_rate <= 0 or bits_per_sample <= 0:
                    raise RuntimeError("Invalid WAV format metadata.")

                self._channels = channels
                self._sample_rate = sample_rate
                self._sample_width_bytes = bits_per_sample // 8
                if self._sample_width_bytes not in (1, 2, 3, 4):
                    raise RuntimeError("Unsupported PCM sample width: {0} bytes".format(self._sample_width_bytes))
                self._bytes_per_frame = self._channels * self._sample_width_bytes

            padded_size = chunk_size + (chunk_size % 2)
            chunk_end = data_start + padded_size
            if chunk_end > len(self._buffer):
                break
            offset = chunk_end

        if data_chunk_offset is None or self._channels is None:
            return

        del self._buffer[:data_chunk_offset]
        self._header_parsed = True
        self._data_started = True
        self._data_size = data_chunk_size

    def _drain_pcm(self):
        if not self.ready or not self._buffer:
            return []

        allowed = len(self._buffer)
        if self._data_size is not None:
            remaining = self._data_size - self._data_emitted
            if remaining <= 0:
                self._buffer.clear()
                return []
            allowed = min(allowed, remaining)

        if self._bytes_per_frame:
            allowed -= allowed % self._bytes_per_frame

        if allowed <= 0:
            return []

        out = bytes(self._buffer[:allowed])
        del self._buffer[:allowed]
        self._data_emitted += allowed
        return [out]


class AudioPlayer(object):
    def __init__(self, poll_interval_seconds=0.01, on_playback_start=None, on_playback_stop=None):
        if sd is None:
            raise RuntimeError(
                "sounddevice is required for AudioPlayer. Install it with `pip install sounddevice`."
            ) from _SOUNDDEVICE_IMPORT_ERROR

        self.poll_interval_seconds = poll_interval_seconds
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._interrupt_event = threading.Event()
        self._state_lock = threading.Lock()
        self._generation = 0
        self._current_item = None
        self._on_playback_start = on_playback_start
        self._on_playback_stop = on_playback_stop

        self._worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="audio-player-worker",
        )
        self._worker.start()

    def get_generation(self):
        with self._state_lock:
            return self._generation

    def enqueue_stream(self, audio_chunks, generation=None, close_callback=None):
        with self._state_lock:
            target_generation = self._generation if generation is None else generation

        self._queue.put(
            PlaybackItem(
                audio_chunks=audio_chunks,
                generation=target_generation,
                close_callback=close_callback,
            )
        )

    def stop(self, clear_queue=True):
        return self.interrupt(clear_queue=clear_queue)

    def interrupt(self, clear_queue=True):
        with self._state_lock:
            self._generation += 1
            generation = self._generation
            has_current = self._current_item is not None
            current_item = self._current_item

        self._interrupt_event.set()
        if current_item is not None and current_item.close_callback is not None:
            try:
                current_item.close_callback()
            except Exception:
                traceback.print_exc()

        if clear_queue:
            self._drain_queue(cleanup=True)

        if not has_current:
            self._interrupt_event.clear()

        return generation

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
        with self._state_lock:
            current_item = self._current_item
        if current_item is not None and current_item.close_callback is not None:
            try:
                current_item.close_callback()
            except Exception:
                traceback.print_exc()
        self._drain_queue(cleanup=True)

        if self._worker.is_alive():
            self._worker.join(timeout=1.5)

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

        stream = None
        playback_started = False
        try:
            decoder = _WavChunkDecoder()
            for chunk in item.audio_chunks:
                if self._stop_event.is_set() or self._interrupt_event.is_set():
                    break

                with self._state_lock:
                    generation_mismatch = item.generation != self._generation
                if generation_mismatch:
                    break

                pcm_blocks = decoder.feed(chunk)
                if not pcm_blocks:
                    continue

                if stream is None:
                    dtype = _dtype_for_sample_width(decoder.sample_width_bytes)
                    stream = sd.RawOutputStream(
                        samplerate=decoder.sample_rate,
                        channels=decoder.channels,
                        dtype=dtype,
                        blocksize=0,
                    )
                    stream.start()

                for pcm in pcm_blocks:
                    if not pcm:
                        continue
                    if not playback_started:
                        playback_started = True
                        if self._on_playback_start is not None:
                            try:
                                self._on_playback_start(item)
                            except Exception:
                                traceback.print_exc()
                    stream.write(pcm)

            if stream is not None and not self._stop_event.is_set() and not self._interrupt_event.is_set():
                for pcm in decoder.flush():
                    if pcm:
                        if not playback_started:
                            playback_started = True
                            if self._on_playback_start is not None:
                                try:
                                    self._on_playback_start(item)
                                except Exception:
                                    traceback.print_exc()
                        stream.write(pcm)
        except Exception:
            traceback.print_exc()
        finally:
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass
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
        if item.close_callback is None:
            return

        try:
            item.close_callback()
        except Exception:
            traceback.print_exc()


def _dtype_for_sample_width(sample_width_bytes):
    mapping = {
        1: "uint8",
        2: "int16",
        3: "int24",
        4: "int32",
    }
    dtype = mapping.get(int(sample_width_bytes or 0))
    if dtype is None:
        raise RuntimeError("Unsupported PCM sample width: {0}".format(sample_width_bytes))
    return dtype


