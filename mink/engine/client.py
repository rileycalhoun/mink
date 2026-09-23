"""HTTP client for the nemo-speech.cpp transcription server.

The server exposes an OpenAI-compatible API, so transcription is a plain
``POST /v1/audio/transcriptions`` multipart request. Diarization is enabled
server-side with the Sortformer companion model; when active, segments carry
speaker labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import httpx

from mink.config import settings


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
    """Thin client over the local nemo-speech.cpp server."""

    def __init__(self, base_url: str | None = None, timeout: float = 600.0) -> None:
        self.base_url = (base_url or settings.engine_url).rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        """Return True if the engine server is reachable."""
        try:
            # trust_env=False: the engine is local, so proxy env vars must
            # never apply (and must never break URL parsing).
            with httpx.Client(trust_env=False, timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/health")
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
        model = model or settings.default_model
        data: dict[str, str] = {
            "model": model,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language

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
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise EngineError(
                f"Transcription request failed (is the engine running? "
                f"see scripts/setup-engine.sh): {exc}"
            ) from exc

        payload = resp.json()
        segments = [
            TranscriptionSegment(
                start=float(s.get("start", 0.0)),
                end=float(s.get("end", 0.0)),
                text=s.get("text", "").strip(),
                speaker=s.get("speaker"),
            )
            for s in payload.get("segments", [])
        ]
        return TranscriptionResult(
            text=payload.get("text", ""),
            language=payload.get("language"),
            segments=segments,
        )
