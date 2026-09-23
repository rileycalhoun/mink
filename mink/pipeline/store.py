"""Session store: list and search persisted lecture sessions."""

from __future__ import annotations

import json
from pathlib import Path

from mink.config import settings
from mink.pipeline.session import LectureSession


class SessionStore:
    def __init__(self, sessions_dir: Path | None = None) -> None:
        self.sessions_dir = sessions_dir or settings.sessions_dir

    def list(self) -> list[LectureSession]:
        sessions: list[LectureSession] = []
        if not self.sessions_dir.exists():
            return sessions
        for path in self.sessions_dir.glob("*.json"):
            try:
                sessions.append(LectureSession.load(path.stem))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def search(self, query: str) -> list[tuple[LectureSession, list[str]]]:
        """Full-text search over transcripts; returns (session, matching lines)."""
        query = query.lower()
        hits: list[tuple[LectureSession, list[str]]] = []
        for session in self.list():
            if not session.transcript:
                continue
            lines = [seg.text for seg in session.transcript.segments if query in seg.text.lower()]
            if lines or query in session.transcript.text.lower():
                hits.append((session, lines[:5]))
        return hits
