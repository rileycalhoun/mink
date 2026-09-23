"""FastAPI service: browse sessions, view transcripts, search, upload audio.

Run with ``mink serve``. Serves a JSON API; the HTML UI is a future milestone
(see docs/architecture.md).
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from mink import __version__
from mink.config import settings
from mink.engine import EngineClient
from mink.pipeline import LectureSession, SessionStore

app = FastAPI(title="Mink", version=__version__)
store = SessionStore()


@app.get("/api/health")
def health() -> dict:
    engine = EngineClient()
    return {
        "status": "ok",
        "version": __version__,
        "engine_reachable": engine.health(),
        "engine_url": settings.engine_url,
    }


@app.get("/api/sessions")
def list_sessions() -> list[dict]:
    return [
        {
            "id": s.id,
            "title": s.title,
            "course": s.course,
            "created_at": s.created_at.isoformat(),
            "has_transcript": s.transcript is not None,
        }
        for s in store.list()
    ]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        return LectureSession.load(session_id).to_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None


@app.get("/api/search")
def search(q: str) -> list[dict]:
    return [
        {"id": s.id, "title": s.title, "course": s.course, "matches": lines}
        for s, lines in store.search(q)
    ]


@app.post("/api/transcribe")
def transcribe_upload(
    file: UploadFile = File(...),
    model: str | None = None,
    language: str | None = None,
    title: str = "",
    course: str = "",
) -> JSONResponse:
    """Upload an audio file, transcribe it, and save as a new session."""
    suffix = Path(file.filename or "upload").suffix or ".wav"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)

    session = LectureSession(title=title or file.filename or "", course=course)
    session.audio_path = tmp_path
    try:
        session.transcribe(model=model, language=language)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    path = session.save()
    return JSONResponse({"id": session.id, "path": str(path)})
