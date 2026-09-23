"""A lecture session: record audio, transcribe it, persist the transcript.

A session is the unit Mink thinks in. Each session owns one audio file and
one transcript; the transcript keeps word/segment timestamps and speaker
labels so the UI can render a readable, searchable lecture record.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from mink.capture import AudioRecorder
from mink.config import settings
from mink.engine import EngineClient, TranscriptionResult, TranscriptionSegment


@dataclass
class LectureSession:
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    course: str = ""
    teacher: str = ""
    folder_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    audio_path: Path | None = None
    transcript: TranscriptionResult | None = None
    summary: dict | None = None
    """Structured summary dict (see mink.llm.Summary.to_dict()); None if not generated."""

    def set_summary(self, summary) -> None:
        """Attach a summary (mink.llm.Summary or plain dict)."""
        self.summary = summary.to_dict() if hasattr(summary, "to_dict") else summary

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def record(self, device: int | str | None = None) -> None:
        """Record from the microphone until interrupted (Ctrl-C)."""
        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        recorder = AudioRecorder(settings.audio_dir, device=device)
        recording = recorder.start()
        print(f"Recording {self.id} -> {recording.path} (Ctrl-C to stop)")
        try:
            while recorder.is_recording:
                recorder._stop.wait(1.0)
        except KeyboardInterrupt:
            pass
        finished = recorder.stop()
        self.audio_path = finished.path
        print(f"Saved {finished.path} ({finished.duration_seconds:.0f}s)")

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------
    def transcribe(
        self,
        model: str | None = None,
        language: str | None = None,
        diarize: bool = True,
    ) -> TranscriptionResult:
        """Send the session audio to the engine and keep the transcript."""
        if self.audio_path is None:
            raise RuntimeError("No audio recorded yet; call record() first")
        client = EngineClient()
        self.transcript = client.transcribe(
            self.audio_path, model=model, language=language, diarize=diarize
        )
        return self.transcript

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["audio_path"] = str(self.audio_path) if self.audio_path else None
        d["transcript"] = asdict(self.transcript) if self.transcript else None
        return d

    def save(self) -> Path:
        """Write the session (metadata + transcript) as JSON."""
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = settings.sessions_dir / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def load(cls, session_id: str) -> LectureSession:
        path = settings.sessions_dir / f"{session_id}.json"
        data = json.loads(path.read_text())
        # Tolerate sessions written before teacher/folder_id existed.
        data.setdefault("teacher", "")
        data.setdefault("folder_id", None)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["audio_path"] = Path(data["audio_path"]) if data["audio_path"] else None
        if data["transcript"]:
            t = data["transcript"]
            t["segments"] = [TranscriptionSegment(**s) for s in t.get("segments", [])]
            data["transcript"] = TranscriptionResult(**t)
        return cls(**data)
