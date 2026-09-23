"""HTTP client for the nemo-speech.cpp transcription server.

The server exposes an OpenAI-compatible API, so transcription is a plain
``POST /v1/audio/transcriptions`` multipart request. Diarization is enabled
server-side with the Sortformer companion model; when active, segments carry
speaker labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import time

import httpx

from mink.config import settings
from mink.engine.manager import engine_manager

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF_S = 5.0


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
