"""HTTP client for the nemo-speech.cpp transcription server.

The server exposes an OpenAI-compatible API, so transcription is a plain
``POST /v1/audio/transcriptions`` multipart request. Diarization is requested
per-call; when the server was started with a diarizer companion model
(``--diar-model sortformer`` in scripts/setup-engine.sh), words carry speaker
labels.

Note on response shape: ``verbose_json`` returns word-level timings
(``words[]`` with ``word``/``start``/``end``/``confidence``/``speaker``) and
no ``segments`` array, so Mink groups words into readable timestamped
segments itself (see :func:`_segments_from_words`).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from mink.config import settings
from mink.engine.manager import engine_manager

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_S = 5.0

# Segment grouping: a new segment starts on a speaker change, at a sentence
# boundary after at least this many words, or unconditionally at the cap so
# long monologues stay navigable.
_MIN_WORDS_PER_SEGMENT = 6
_MAX_WORDS_PER_SEGMENT = 24
_SENTENCE_END = (".", "!", "?")
_SPEAKER_RE = re.compile(r"SPEAKER_\d+")


def _normalize_speaker(raw: object) -> str | None:
    """Canonicalize an engine speaker label to ``SPEAKER_XX`` (or ``None``).

    nemo-speech.cpp's diarization emits the speaker as a 1-based integer
    (``1`` for the first speaker); other engines may already emit
    ``SPEAKER_00``-style strings. The rest of Mink (exports, UI, tests)
    speaks the zero-based ``SPEAKER_XX`` string form, so normalize here —
    at the boundary — rather than scattering coercion through consumers.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        n = int(raw)
        if n < 1:
            return None
        return f"SPEAKER_{n - 1:02d}"
    text = str(raw).strip()
    if not text:
        return None
    if _SPEAKER_RE.fullmatch(text):
        return text
    if text.isdigit():
        n = int(text)
        return f"SPEAKER_{n - 1:02d}" if n >= 1 else None
    return text


def _segments_from_words(words: list[dict]) -> list[TranscriptionSegment]:
    """Group verbose_json word timings into readable timestamped segments.

    nemo-speech.cpp's ``verbose_json`` has no ``segments`` array — only
    ``words[]`` — so the grouping is Mink's own: speaker changes always break,
    sentence-ending punctuation breaks after a minimum run of words, and a
    hard cap keeps very long runs navigable.
    """
    segments: list[TranscriptionSegment] = []
    cur: list[str] = []
    cur_start = 0.0
    cur_end = 0.0
    cur_speaker: str | None = None

    def flush() -> None:
        nonlocal cur, cur_start, cur_end, cur_speaker
        text = " ".join(cur).strip()
        if text:
            segments.append(
                TranscriptionSegment(
                    start=cur_start,
                    end=cur_end,
                    text=text,
                    speaker=cur_speaker,
                )
            )
        cur = []
        cur_speaker = None

    for w in words:
        word = str(w.get("word") or w.get("text") or "").strip()
        if not word:
            continue
        speaker = _normalize_speaker(w.get("speaker"))
        start = float(w.get("start", cur_end or 0.0))
        end = float(w.get("end", start))
        if cur and speaker != cur_speaker:
            flush()
        if not cur:
            cur_start = start
            cur_speaker = speaker
        cur.append(word)
        cur_end = end
        sentence_end = word[-1] in _SENTENCE_END
        if len(cur) >= _MAX_WORDS_PER_SEGMENT or (
            sentence_end and len(cur) >= _MIN_WORDS_PER_SEGMENT
        ):
            flush()
    flush()
    return segments


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class TranscriptionResult:
    text: str
    language: str | None = None
    segments: list[TranscriptionSegment] = field(default_factory=list)


class EngineError(RuntimeError):
    """The transcription engine returned an error or is unreachable."""


class EngineClient:
    """Thin client over the nemo-speech.cpp transcription server.

    When the on-demand engine manager has a pod up, the base URL and bearer
    token come from it automatically; otherwise the static settings apply.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 600.0,
    ) -> None:
        self.base_url = (base_url or engine_manager.engine_url).rstrip("/")
        self.api_key = api_key or engine_manager.api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def health(self) -> bool:
        """Return True if the engine server is reachable."""
        try:
            # trust_env=False: the engine is local, so proxy env vars must
            # never apply (and must never break URL parsing).
            with httpx.Client(trust_env=False, timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/health", headers=self._headers())
                return resp.status_code < 500
        except Exception:  # noqa: BLE001 — any failure means "not reachable"
            return False

    def transcribe(
        self,
        audio: Path,
        model: str | None = None,
        language: str | None = None,
        diarize: bool = True,
    ) -> TranscriptionResult:
        """Transcribe an audio file; returns text plus timestamped segments."""
        engine_manager.touch()
        model = model or settings.default_model
        data: dict[str, str] = {
            "model": model,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language
        if diarize:
            # Off by default server-side; without it words carry no speakers
            # even when a diarizer model is loaded.
            data["diarization"] = "true"

        try:
            for attempt in range(_RETRY_ATTEMPTS):
                try:
                    with (
                        httpx.Client(trust_env=False, timeout=self.timeout) as client,
                        open(audio, "rb") as fh,
                    ):
                        files = {"file": (audio.name, fh, "audio/wav")}
                        resp = client.post(
                            f"{self.base_url}/v1/audio/transcriptions",
                            data=data,
                            files=files,
                            headers=self._headers(),
                        )
                    resp.raise_for_status()
                    break
                except httpx.HTTPStatusError as exc:
                    if (
                        exc.response.status_code in (502, 503, 504)
                        and attempt < _RETRY_ATTEMPTS - 1
                    ):
                        time.sleep(_RETRY_BACKOFF_S * (attempt + 1))
                        continue
                    raise
        except httpx.HTTPError as exc:
            raise EngineError(
                f"Transcription request failed (is the engine running? "
                f"see scripts/setup-engine.sh): {exc}"
            ) from exc

        payload = resp.json()
        # verbose_json carries words[], not segments — group them ourselves.
        segments = _segments_from_words(payload.get("words") or [])
        return TranscriptionResult(
            text=payload.get("text", ""),
            language=payload.get("language"),
            segments=segments,
        )
