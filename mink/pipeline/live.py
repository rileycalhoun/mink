"""Live transcription sessions.

The browser captures microphone audio as 16-bit PCM (mono, 16 kHz) and streams
it over a WebSocket. The backend accumulates the PCM, transcribes overlapping
windows through the engine, and emits partial transcripts with absolute
timestamps. When the session stops, a full diarized pass produces the final
transcript.

This chunked design works over the engine's stateless HTTP API — no gRPC or
streaming-protocol support required from nemo-speech.cpp.
"""

from __future__ import annotations

import io
import math
import struct
import threading
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from mink.config import settings
from mink.engine import EngineClient, TranscriptionResult

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # int16


def _pcm_to_wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


def _is_silence(pcm: bytes, threshold: float) -> bool:
    if not pcm:
        return True
    # RMS of little-endian int16 samples. (audioop.rms did this, but audioop
    # is deprecated since 3.11 and removed in 3.13.)
    n = len(pcm) // SAMPLE_WIDTH
    samples = struct.unpack(f"<{n}h", pcm[: n * SAMPLE_WIDTH])
    rms = math.sqrt(sum(s * s for s in samples) / n)
    return rms < threshold


@dataclass
class LivePartial:
    """One window's worth of transcript with absolute timestamps."""

    segments: list[dict] = field(default_factory=list)
    text: str = ""


class LiveSession:
    """One in-progress live transcription."""

    def __init__(self, title: str = "", course: str = "", model: str | None = None) -> None:
        self.id = uuid4().hex[:12]
        self.title = title
        self.course = course
        self.model = model or settings.live_model
        self.created_at = datetime.now(timezone.utc)
        self._pcm = bytearray()
        self._consumed_bytes = 0  # bytes already covered by transcribed windows
        self._lock = threading.Lock()
        self._client = EngineClient()
        self._window_count = 0

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    def push_pcm(self, chunk: bytes) -> LivePartial | None:
        """Append PCM; transcribe a window when enough new audio arrived.

        Returns a LivePartial when a window was transcribed, else None.
        Thread-safe; transcription itself blocks, so callers should run this
        in a worker thread.
        """
        with self._lock:
            self._pcm.extend(chunk)
            window_bytes = int(settings.live_window_seconds * SAMPLE_RATE * SAMPLE_WIDTH)
            step_bytes = int(
                (settings.live_window_seconds - settings.live_overlap_seconds)
                * SAMPLE_RATE
                * SAMPLE_WIDTH
            )
            if len(self._pcm) - self._consumed_bytes < window_bytes:
                return None
            start_byte = self._consumed_bytes
            window = bytes(self._pcm[start_byte : start_byte + window_bytes])
            self._consumed_bytes += step_bytes
            window_start_s = start_byte / (SAMPLE_RATE * SAMPLE_WIDTH)
            window_index = self._window_count
            self._window_count += 1

        if _is_silence(window, settings.live_silence_rms):
            return LivePartial()

        with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(_pcm_to_wav_bytes(window))
            tmp_path = Path(tmp.name)
        try:
            result = self._client.transcribe(tmp_path, model=self.model, diarize=False)
        finally:
            tmp_path.unlink(missing_ok=True)

        # Drop the overlapped head (except on the very first window) so
        # repeated audio isn't shown twice.
        cutoff = window_start_s + (settings.live_overlap_seconds if window_index > 0 else 0.0)
        segments = [
            {
                "start": round(window_start_s + s.start, 2),
                "end": round(window_start_s + s.end, 2),
                "text": s.text,
            }
            for s in result.segments
            if window_start_s + s.start >= cutoff - 0.05 and s.text.strip()
        ]
        return LivePartial(segments=segments, text=" ".join(s["text"] for s in segments))

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------
    def finalize(self) -> TranscriptionResult:
        """Write the full recording and run the final diarized pass."""
        from mink.pipeline.session import LectureSession

        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        stamp = self.created_at.strftime("%Y%m%dT%H%M%SZ")
        audio_path = settings.audio_dir / f"live-{stamp}-{self.id}.wav"
        with self._lock:
            pcm = bytes(self._pcm)
        audio_path.write_bytes(_pcm_to_wav_bytes(pcm))

        session = LectureSession(
            id=self.id, title=self.title, course=self.course, audio_path=audio_path
        )
        # Final pass with the default (higher-quality, punctuated) model + diarization.
        session.transcribe(diarize=True)
        session.save()
        return session.transcript

    @property
    def duration_seconds(self) -> float:
        with self._lock:
            return len(self._pcm) / (SAMPLE_RATE * SAMPLE_WIDTH)


class LiveSessionManager:
    """Tracks active live sessions by id."""

    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._lock = threading.Lock()

    def create(self, title: str = "", course: str = "", model: str | None = None) -> LiveSession:
        session = LiveSession(title=title, course=course, model=model)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> LiveSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
