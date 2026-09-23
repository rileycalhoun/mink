"""Transcript export: Markdown, SRT/VTT captions, plain text."""

from __future__ import annotations

from mink.pipeline.session import LectureSession


def _ts(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    ms = round((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_vtt(seconds: float) -> str:
    return _ts(seconds).replace(",", ".")


def export_txt(session: LectureSession) -> str:
    if not session.transcript:
        return ""
    return session.transcript.text


def export_srt(session: LectureSession) -> str:
    lines: list[str] = []
    for i, seg in enumerate((session.transcript.segments if session.transcript else []), 1):
        speaker = f"[{seg.speaker}] " if seg.speaker else ""
        lines += [str(i), f"{_ts(seg.start)} --> {_ts(seg.end)}", f"{speaker}{seg.text}", ""]
    return "\n".join(lines)


def export_vtt(session: LectureSession) -> str:
    lines = ["WEBVTT", ""]
    for seg in session.transcript.segments if session.transcript else []:
        speaker = f"<v {seg.speaker}>" if seg.speaker else ""
        closer = "</v>" if seg.speaker else ""
        lines += [
            f"{_ts_vtt(seg.start)} --> {_ts_vtt(seg.end)}",
            f"{speaker}{seg.text}{closer}",
            "",
        ]
    return "\n".join(lines)


def export_markdown(session: LectureSession) -> str:
    out: list[str] = [f"# {session.title or 'Untitled lecture'}", ""]
    if session.course:
        out += [f"*{session.course} — {session.created_at.strftime('%Y-%m-%d')}*", ""]
    summary = session.summary
    if summary:
        out += ["## Summary", "", summary.get("tldr", ""), ""]
        chapters = summary.get("chapters", [])
        if chapters:
            out += ["## Chapters", ""]
            for ch in chapters:
                out += [
                    f"### {ch.get('title', '')} ({ch.get('start', '')}–{ch.get('end', '')})",
                    "",
                ]
                out += [f"- {b}" for b in ch.get("bullets", [])] + [""]
        if summary.get("key_points"):
            out += ["## Key points", ""] + [f"- {p}" for p in summary["key_points"]] + [""]
        if summary.get("action_items"):
            out += ["## Action items", ""] + [f"- [ ] {a}" for a in summary["action_items"]] + [""]
        if summary.get("terms"):
            out += ["## Glossary", ""]
            out += [
                f"- **{t.get('term', '')}** — {t.get('definition', '')}" for t in summary["terms"]
            ] + [""]
    out += ["## Transcript", ""]
    for seg in session.transcript.segments if session.transcript else []:
        m, s = divmod(int(seg.start), 60)
        speaker = f"**{seg.speaker}**: " if seg.speaker else ""
        out += [f"[{m:02d}:{s:02d}] {speaker}{seg.text}", ""]
    return "\n".join(out).rstrip() + "\n"


EXPORTERS = {
    "txt": ("text/plain", export_txt),
    "srt": ("application/x-subrip", export_srt),
    "vtt": ("text/vtt", export_vtt),
    "md": ("text/markdown", export_markdown),
}
