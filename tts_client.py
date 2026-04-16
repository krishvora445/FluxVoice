import base64
import json
import os
import re
import socket
import tempfile
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
            _validate_audio_payload(audio_bytes, content_type, "Streaming request")

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
        _validate_audio_payload(audio_bytes, content_type, "Buffered request")

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
