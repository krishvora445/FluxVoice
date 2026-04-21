import base64
import json
import os
import re
import socket
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, List, Optional

from app_config import HttpTTSConfig


class TTSClientError(RuntimeError):
    pass


@dataclass
class SynthesizedAudio(object):
    audio_bytes: bytes
    content_type: str
    used_streaming: bool


@dataclass
class SynthesizedAudioStream(object):
    content_type: str
    used_streaming: bool
    audio_chunks: Iterable[bytes]
    close: Optional[Callable[[], None]] = None


def write_temp_audio_file(audio_bytes: bytes, content_type: str, default_extension: str = ".wav") -> str:
    suffix = _guess_audio_suffix(content_type, default_extension)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio_file:
        temp_audio_file.write(audio_bytes)
        return temp_audio_file.name


def cleanup_temp_file(file_path: str) -> None:
    if not file_path:
        return

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def _guess_audio_suffix(content_type: str, default_extension: str) -> str:
    normalized = (content_type or "").lower()

    if "wav" in normalized or "wave" in normalized:
        return ".wav"
    if "ogg" in normalized or "opus" in normalized:
        return ".ogg"
    if "mpeg" in normalized or "mp3" in normalized:
        return ".mp3"

    cleaned = (default_extension or ".wav").strip()
    if not cleaned:
        return ".wav"
    if not cleaned.startswith("."):
        cleaned = "." + cleaned

    return cleaned


class OpenAITTSClient(object):
    def __init__(self, config: HttpTTSConfig):
        self.config = config

    def synthesize(self, text: str) -> SynthesizedAudio:
        stream_result = self.synthesize_stream(text)
        try:
            audio_bytes = b"".join(stream_result.audio_chunks)
        finally:
            if stream_result.close is not None:
                try:
                    stream_result.close()
                except Exception:
                    pass

        if not audio_bytes:
            raise TTSClientError("TTS request returned an empty audio payload.")

        return SynthesizedAudio(
            audio_bytes=audio_bytes,
            content_type=stream_result.content_type,
            used_streaming=stream_result.used_streaming,
        )

    def synthesize_stream(self, text: str) -> SynthesizedAudioStream:
        if self.config.streaming_mode in {"on", "auto"}:
            try:
                return self._synthesize_with_stream_flag(text)
            except TTSClientError:
                if self.config.streaming_mode == "on":
                    raise

        return self._synthesize_buffered(text)

    def _synthesize_with_stream_flag(self, text: str) -> SynthesizedAudioStream:
        payload = self._build_payload(text, stream=True)

        response = self._post_json(payload)
        content_type = response.headers.get("Content-Type", "")
        content_type_lower = content_type.lower()
        stream_lock = threading.Lock()

        def close_response() -> None:
            with stream_lock:
                try:
                    response.close()
                except Exception:
                    pass

        if "text/event-stream" in content_type_lower:
            iterator = self._iter_sse_audio_chunks(response, stream_lock)
            return SynthesizedAudioStream(
                content_type=content_type,
                used_streaming=True,
                audio_chunks=iterator,
                close=close_response,
            )

        _validate_streaming_content_type(content_type, "Streaming request")
        iterator = self._iter_raw_audio_chunks(response, stream_lock)
        return SynthesizedAudioStream(
            content_type=content_type,
            used_streaming=False,
            audio_chunks=iterator,
            close=close_response,
        )

    def _synthesize_buffered(self, text: str) -> SynthesizedAudioStream:
        payload = self._build_payload(text, stream=False)
        response = self._post_json(payload)
        content_type = response.headers.get("Content-Type", "")
        _validate_streaming_content_type(content_type, "Buffered request")
        stream_lock = threading.Lock()

        def close_response() -> None:
            with stream_lock:
                try:
                    response.close()
                except Exception:
                    pass

        iterator = self._iter_raw_audio_chunks(response, stream_lock)
        return SynthesizedAudioStream(
            content_type=content_type,
            used_streaming=False,
            audio_chunks=iterator,
            close=close_response,
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
            detail = _extract_error_detail(error_body)
            hint = ""
            if exc.code == 404:
                hint = " (check the /v1/audio/speech path and port)"
            elif exc.code in {401, 403}:
                hint = " (check TTS_API_KEY / auth settings)"
            raise TTSClientError(
                "TTS HTTP error {0}: {1}{2}".format(exc.code, detail or exc.reason, hint)
            ) from exc
        except urllib.error.URLError as exc:
            raise TTSClientError("TTS network error: {0}".format(exc.reason)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise TTSClientError("TTS request timed out.") from exc

    def _iter_sse_audio_chunks(self, response, stream_lock: threading.Lock) -> Iterator[bytes]:
        saw_audio = False
        try:
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
                    saw_audio = True
                    yield maybe_audio
        finally:
            with stream_lock:
                try:
                    response.close()
                except Exception:
                    pass

        if not saw_audio:
            raise TTSClientError("Streaming endpoint returned no audio chunks.")

    def _iter_raw_audio_chunks(self, response, stream_lock: threading.Lock, read_size: int = 4096) -> Iterator[bytes]:
        saw_data = False
        first_chunk = b""
        try:
            while True:
                chunk = response.read(read_size)
                if not chunk:
                    break

                if not saw_data:
                    first_chunk = chunk
                    _validate_audio_payload(first_chunk, response.headers.get("Content-Type", ""), "HTTP request")
                    saw_data = True

                yield chunk
        finally:
            with stream_lock:
                try:
                    response.close()
                except Exception:
                    pass

        if not saw_data:
            raise TTSClientError("HTTP request returned an empty body.")


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


def _extract_error_detail(error_body: str) -> str:
    if not error_body:
        return ""

    try:
        parsed = json.loads(error_body)
    except json.JSONDecodeError:
        return error_body.strip()

    if isinstance(parsed, dict):
        nested_error = parsed.get("error")
        if isinstance(nested_error, dict):
            message = nested_error.get("message") or nested_error.get("detail")
            if message:
                return str(message)

        for key in ("message", "detail"):
            if key in parsed and parsed[key]:
                return str(parsed[key])

    return error_body.strip()


def _validate_audio_payload(audio_bytes: bytes, content_type: str, request_label: str) -> None:
    normalized = (content_type or "").lower()

    if (
        not normalized
        or normalized.startswith("audio/")
        or "octet-stream" in normalized
        or "wav" in normalized
        or "mpeg" in normalized
        or "mp3" in normalized
        or "ogg" in normalized
        or "opus" in normalized
    ):
        return

    preview = audio_bytes[:300].decode("utf-8", errors="replace").strip()
    raise TTSClientError(
        "{0} returned non-audio content type '{1}'. Response preview: {2}".format(
            request_label,
            content_type or "<missing>",
            preview or "<empty>",
        )
    )


def _validate_streaming_content_type(content_type: str, request_label: str) -> None:
    normalized = (content_type or "").lower()
    if (
        not normalized
        or normalized.startswith("audio/")
        or "octet-stream" in normalized
        or "wav" in normalized
        or "mpeg" in normalized
        or "mp3" in normalized
        or "ogg" in normalized
        or "opus" in normalized
        or "text/event-stream" in normalized
    ):
        return

    raise TTSClientError(
        "{0} returned non-audio content type '{1}'.".format(
            request_label,
            content_type or "<missing>",
        )
    )


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
