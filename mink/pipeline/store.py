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

    def delete(self, session_id: str) -> bool:
        """Delete a session's JSON and its audio file. Returns True if it existed.

        Paths are validated to stay inside the data directories, so a crafted
        id can never escape into the rest of the filesystem.
        """
        sessions_dir = self.sessions_dir.resolve()
        path = (sessions_dir / f"{session_id}.json").resolve()
        if path.parent != sessions_dir or not path.is_file():
            return False
        audio = LectureSession.load(session_id).audio_path
        path.unlink()
        if audio is not None:
            audio = audio.resolve()
            if audio.parent == settings.audio_dir.resolve() and audio.is_file():
                audio.unlink()
        return True

    _EDITABLE = ("title", "course", "teacher", "folder_id")

    def update(self, session_id: str, **fields) -> LectureSession | None:
        """Update editable metadata fields; returns the session, or None if missing."""
        path = (self.sessions_dir / f"{session_id}.json").resolve()
        if path.parent != self.sessions_dir.resolve() or not path.is_file():
            return None
        session = LectureSession.load(session_id)
        for key, value in fields.items():
            if key in self._EDITABLE:
                setattr(session, key, value)
        session.save()
        return session

    def clear_folder(self, folder_id: str) -> int:
        """Remove every session from a folder (used when the folder is deleted)."""
        cleared = 0
        for session in self.list():
            if session.folder_id == folder_id:
                session.folder_id = None
                session.save()
                cleared += 1
        return cleared
