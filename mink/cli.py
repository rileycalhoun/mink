"""Mink command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mink import __version__
from mink.config import settings
from mink.engine import MODELS, EngineClient, get_model
from mink.pipeline import LectureSession, SessionStore

app = typer.Typer(help="Mink — open-source lecture recording and transcription.")
console = Console()


@app.command()
def version() -> None:
    """Print the Mink version."""
    console.print(f"mink {__version__}")


@app.command()
def models() -> None:
    """List available transcription models."""
    table = Table(title="Transcription models")
    table.add_column("Name")
    table.add_column("Languages")
    table.add_column("Streaming")
    table.add_column("Description")
    for name, info in MODELS.items():
        table.add_row(name, info.languages, "yes" if info.streaming else "no", info.description)
    console.print(table)


@app.command()
def engine_status() -> None:
    """Check whether the transcription engine is reachable."""
    client = EngineClient()
    if client.health():
        console.print(f"[green]Engine reachable[/green] at {client.base_url}")
    else:
        console.print(
            f"[red]Engine not reachable[/red] at {client.base_url}\n"
            "Start it with: scripts/setup-engine.sh"
        )
        raise typer.Exit(1)


@app.command()
def record(
    title: str = typer.Option("", help="Lecture title"),
    course: str = typer.Option("", help="Course name/code"),
    device: str | None = typer.Option(None, help="Input device index or name"),
) -> None:
    """Record a lecture from the microphone (Ctrl-C to stop)."""
    session = LectureSession(title=title, course=course)
    session.record(device=device)
    path = session.save()
    console.print(f"Session {session.id} saved to {path}")


@app.command()
def transcribe(
    audio: Path = typer.Argument(..., help="Audio file to transcribe"),
    model: str = typer.Option(None, help="Model name (see: mink models)"),
    language: str = typer.Option(None, help="Language code, e.g. en"),
    no_diarize: bool = typer.Option(False, help="Disable speaker diarization"),
    title: str = typer.Option("", help="Lecture title"),
    course: str = typer.Option("", help="Course name/code"),
) -> None:
    """Transcribe an audio file and save it as a session."""
    if model:
        get_model(model)  # validate early
    session = LectureSession(title=title or audio.stem, course=course)
    session.audio_path = audio
    with console.status("Transcribing..."):
        result = session.transcribe(model=model, language=language, diarize=not no_diarize)
    path = session.save()
    console.print(f"[green]Done.[/green] Session {session.id} -> {path}")
    console.print(f"{len(result.segments)} segments, {len(result.text)} chars")


@app.command()
def sessions() -> None:
    """List recorded lecture sessions."""
    rows = SessionStore().list()
    table = Table(title="Lecture sessions")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Course")
    table.add_column("Created")
    table.add_column("Transcript")
    for s in rows:
        table.add_row(
            s.id,
            s.title or "-",
            s.course or "-",
            s.created_at.strftime("%Y-%m-%d %H:%M"),
            "yes" if s.transcript else "no",
        )
    console.print(table)


@app.command()
def search(query: str = typer.Argument(..., help="Text to search for")) -> None:
    """Search all transcripts for text."""
    hits = SessionStore().search(query)
    if not hits:
        console.print("No matches.")
        return
    for session, lines in hits:
        console.print(
            f"\n[bold]{session.title or session.id}[/bold] ({session.course or 'no course'})"
        )
        for line in lines:
            console.print(f"  …{line.strip()}")


@app.command()
def show(session_id: str = typer.Argument(..., help="Session ID")) -> None:
    """Print a session's transcript with timestamps and speakers."""
    session = LectureSession.load(session_id)
    if not session.transcript:
        console.print("No transcript for this session yet.")
        raise typer.Exit(1)
    for seg in session.transcript.segments:
        speaker = f"[cyan]{seg.speaker}[/cyan] " if seg.speaker else ""
        stamp = f"{seg.start:7.1f}s"
        console.print(f"{stamp} {speaker}{seg.text}")


@app.command()
def summarize(session_id: str = typer.Argument(..., help="Session ID")) -> None:
    """Generate a structured summary (TL;DR, chapters, key points) via the LLM."""
    from mink.llm import get_provider, summarize_session
    from mink.llm.providers import LLMNotConfigured

    session = LectureSession.load(session_id)
    try:
        provider = get_provider()
    except LLMNotConfigured as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    with console.status("Summarizing..."):
        summary = summarize_session(session, provider)
    session.set_summary(summary)
    session.save()
    console.print(f"[green]Done.[/green] {summary.tldr}")


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session ID"),
    format: str = typer.Option("md", help="One of: md, txt, srt, vtt"),
    output: Path | None = typer.Option(None, help="Output file (default: stdout)"),
) -> None:
    """Export a session's transcript (md/txt/srt/vtt)."""
    from mink.pipeline import EXPORTERS

    try:
        _, exporter = EXPORTERS[format]
    except KeyError:
        console.print(f"[red]Unknown format {format!r}; choose from {', '.join(EXPORTERS)}[/red]")
        raise typer.Exit(1) from None
    session = LectureSession.load(session_id)
    if session.transcript is None:
        console.print("No transcript to export.")
        raise typer.Exit(1)
    body = exporter(session)
    if output:
        output.write_text(body)
        console.print(f"Wrote {output}")
    else:
        console.print(body)


@app.command()
def serve(
    host: str = typer.Option(None, help="Bind host"),
    port: int = typer.Option(None, help="Bind port"),
) -> None:
    """Start the Mink web API."""
    import uvicorn

    uvicorn.run(
        "mink.web.app:app",
        host=host or settings.web_host,
        port=port or settings.web_port,
    )


@app.command()
def devices() -> None:
    """List available audio input devices."""
    from mink.capture import AudioRecorder

    for d in AudioRecorder.list_devices():
        console.print(f"[{d['index']}] {d['name']} ({d['channels']}ch)")
