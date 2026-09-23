"""FastAPI service: sessions, search, live transcription, summaries, exports.

Run with ``mink serve``. Serves the JSON API under ``/api/*`` and — when the
Svelte UI has been built (``mink/web/ui`` → ``npm run build``) — the web app
itself from ``/``.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from mink import __version__
from mink.config import settings
from mink.engine import EngineClient, engine_manager
from mink.llm import get_provider, provider_status, summarize_session
from mink.llm.providers import LLMNotConfigured
from mink.pipeline import EXPORTERS, LectureSession, LiveSessionManager, SessionStore

app = FastAPI(title="Mink", version=__version__)
store = SessionStore()
live_manager = LiveSessionManager()


@app.on_event("startup")
def _reconcile_engine() -> None:
    # Re-adopt a live on-demand pod after a restart, if we still hold its key.
    engine_manager.reconcile()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_session_or_404(session_id: str) -> LectureSession:
    try:
        return LectureSession.load(session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None


def _ensure_wav(src: Path) -> Path:
    """Convert uploads to 16 kHz mono WAV when they aren't already WAV.

    Falls back to the original file if ffmpeg is unavailable.
    """
    if src.suffix.lower() == ".wav":
        return src
    if shutil.which("ffmpeg") is None:
        return src
    out = src.with_suffix(".wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(src),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(out),
        ],
        check=True,
    )
    return out


# ---------------------------------------------------------------------------
# Health / sessions / search
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    engine = EngineClient()
    return {
        "status": "ok",
        "version": __version__,
        "engine_reachable": engine.health(),
        "engine_url": settings.engine_url,
        "llm": provider_status(),
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
            "has_summary": s.summary is not None,
            "has_audio": bool(s.audio_path and s.audio_path.exists()),
        }
        for s in store.list()
    ]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    return _load_session_or_404(session_id).to_dict()


@app.get("/api/search")
def search(q: str) -> list[dict]:
    return [
        {"id": s.id, "title": s.title, "course": s.course, "matches": lines}
        for s, lines in store.search(q)
    ]


# ---------------------------------------------------------------------------
# On-demand engine (RunPod GPU pod)
# ---------------------------------------------------------------------------


@app.get("/api/engine")
def engine_status() -> dict:
    return engine_manager.status()


@app.post("/api/engine/start")
def engine_start() -> JSONResponse:
    try:
        return JSONResponse(engine_manager.start())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/engine/stop")
def engine_stop() -> JSONResponse:
    return JSONResponse(engine_manager.stop())


@app.get("/api/engine/logs")
def engine_logs() -> dict:
    """Cached tail of the provisioning pod's boot log (empty when off)."""
    return engine_manager.boot_log()


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

    wav_path = _ensure_wav(tmp_path)
    session = LectureSession(title=title or file.filename or "", course=course)
    session.audio_path = wav_path
    try:
        session.transcribe(model=model, language=language)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    path = session.save()
    return JSONResponse({"id": session.id, "path": str(path)})


@app.get("/api/sessions/{session_id}/audio")
def get_audio(session_id: str) -> FileResponse:
    session = _load_session_or_404(session_id)
    if not session.audio_path or not session.audio_path.exists():
        raise HTTPException(status_code=404, detail="No audio for this session")
    return FileResponse(session.audio_path, media_type="audio/wav")


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


@app.get("/api/sessions/{session_id}/summary")
def get_summary(session_id: str) -> dict:
    session = _load_session_or_404(session_id)
    if not session.summary:
        raise HTTPException(status_code=404, detail="No summary yet")
    return session.summary


@app.post("/api/sessions/{session_id}/summary")
def generate_summary(session_id: str) -> JSONResponse:
    session = _load_session_or_404(session_id)
    try:
        provider = get_provider()
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        summary = summarize_session(session, provider)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Summarization failed: {exc}") from exc
    session.set_summary(summary)
    session.save()
    return JSONResponse(summary.to_dict())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str, format: str = "md") -> Response:
    session = _load_session_or_404(session_id)
    if session.transcript is None:
        raise HTTPException(status_code=404, detail="No transcript to export")
    try:
        media_type, exporter = EXPORTERS[format]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format {format!r}; choose from {', '.join(EXPORTERS)}",
        ) from None
    body = exporter(session)
    filename = f"{session.title or session.id}.{format}"
    if format == "md":
        return PlainTextResponse(
            body,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Live transcription (WebSocket)
# ---------------------------------------------------------------------------


@app.websocket("/api/live/ws")
async def live_ws(websocket: WebSocket) -> None:
    """Live transcription protocol (see docs/architecture.md).

    Client → server (text JSON):
      {"type": "start", "title": ?, "course": ?, "model": ?}
      {"type": "stop"}
    Client → server (binary): 16-bit PCM mono @ 16 kHz chunks.
    Server → client (text JSON):
      {"type": "started", "session_id"}
      {"type": "partial", "segments": [{start, end, text}], "text", "duration"}
      {"type": "finalizing"} / {"type": "done", "session_id"} / {"type": "error", "message"}
    """
    await websocket.accept()
    session = None
    try:
        while True:
            message = await websocket.receive()
            if "text" in message:
                data = json.loads(message["text"])
                kind = data.get("type")
                if kind == "start":
                    session = live_manager.create(
                        title=data.get("title", ""),
                        course=data.get("course", ""),
                        model=data.get("model"),
                    )
                    await websocket.send_json({"type": "started", "session_id": session.id})
                elif kind == "stop":
                    if session is None:
                        await websocket.send_json({"type": "error", "message": "no live session"})
                        continue
                    await websocket.send_json({"type": "finalizing"})
                    try:
                        # Full diarized pass over the whole recording.
                        await asyncio.to_thread(session.finalize)
                    except Exception as exc:  # noqa: BLE001 — report engine failures to client
                        await websocket.send_json({"type": "error", "message": str(exc)})
                        continue
                    live_manager.remove(session.id)
                    await websocket.send_json({"type": "done", "session_id": session.id})
                    return
            elif "bytes" in message:
                if session is None:
                    continue
                partial = await asyncio.to_thread(session.push_pcm, message["bytes"])
                if partial is not None:
                    await websocket.send_json(
                        {
                            "type": "partial",
                            "segments": partial.segments,
                            "text": partial.text,
                            "duration": round(session.duration_seconds, 1),
                        }
                    )
    except WebSocketDisconnect:
        pass
    finally:
        if session is not None:
            live_manager.remove(session.id)


# ---------------------------------------------------------------------------
# Web UI (Svelte build output)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"


class SPAStaticFiles(StaticFiles):
    """Serve the Svelte SPA, falling back to index.html for client routes."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


if STATIC_DIR.is_dir():
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True), name="ui")
else:

    @app.get("/")
    def ui_not_built() -> dict:
        return {
            "message": "Mink API is running, but the web UI has not been built yet.",
            "hint": "cd mink/web/ui && npm install && npm run build",
        }
