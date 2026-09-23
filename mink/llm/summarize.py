"""Lecture summarization through the configured LLM provider.

Produces a structured study summary: TL;DR, timestamped chapters, key
points, action items, and a glossary. The summary is stored alongside the
session and rendered by the UI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from mink.llm.providers import LLMProvider, Message

# Keep prompts bounded; very long lectures are truncated with a note.
_MAX_TRANSCRIPT_CHARS = 24_000

_SYSTEM_PROMPT = """You are a teaching assistant summarizing a lecture transcript.
The transcript has [mm:ss] timestamps and speaker labels. Return ONLY valid JSON
(no markdown fences) with this exact shape:
{
  "tldr": "2-3 sentence summary of the whole lecture",
  "chapters": [
    {"title": "short chapter title", "start": "mm:ss", "end": "mm:ss",
     "bullets": ["key idea 1", "key idea 2"]}
  ],
  "key_points": ["most important takeaway 1", "..."],
  "action_items": ["homework / follow-up 1", "..."],
  "terms": [{"term": "jargon", "definition": "plain-English definition"}]
}
Chapters should follow the lecture's actual topic shifts (3-8 chapters).
Action items: only real assignments, deadlines, or follow-ups mentioned;
empty array if none. Terms: only non-obvious jargon actually defined or
used in the lecture."""


@dataclass
class Chapter:
    title: str
    start: str
    end: str
    bullets: list[str] = field(default_factory=list)


@dataclass
class Term:
    term: str
    definition: str


@dataclass
class Summary:
    tldr: str
    chapters: list[Chapter] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    terms: list[Term] = field(default_factory=list)
    model: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Summary:
        data = dict(data)
        data["chapters"] = [Chapter(**c) for c in data.get("chapters", [])]
        data["terms"] = [Term(**t) for t in data.get("terms", [])]
        return cls(**data)


def _format_transcript(segments: list, full_text: str) -> str:
    """Render segments as timestamped lines for the prompt."""
    lines: list[str] = []
    for seg in segments:
        start, end = seg.get("start", 0), seg.get("end", 0)
        speaker = seg.get("speaker") or "SPEAKER"
        text = seg.get("text", "").strip()

        def ts(s: float) -> str:
            return f"{int(s // 60):02d}:{int(s % 60):02d}"

        lines.append(f"[{ts(start)}-{ts(end)}] {speaker}: {text}")
    body = "\n".join(lines) or full_text
    if len(body) > _MAX_TRANSCRIPT_CHARS:
        body = body[:_MAX_TRANSCRIPT_CHARS] + "\n…[transcript truncated]"
    return body


def summarize_transcript(
    segments: list[dict],
    full_text: str,
    provider: LLMProvider,
    title: str = "",
) -> Summary:
    """Generate a structured summary; raises on provider errors."""
    transcript = _format_transcript(segments, full_text)
    header = f"Lecture: {title}\n\n" if title else ""
    reply = provider.complete(
        [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content=header + "Transcript:\n" + transcript),
        ],
        json_mode=True,
        max_tokens=4096,
    )
    data = json.loads(reply)
    summary = Summary(
        tldr=data.get("tldr", ""),
        chapters=[Chapter(**c) for c in data.get("chapters", [])],
        key_points=list(data.get("key_points", [])),
        action_items=list(data.get("action_items", [])),
        terms=[Term(**t) for t in data.get("terms", [])],
        model=getattr(provider, "model", provider.name),
    )
    return summary


def summarize_session(session, provider: LLMProvider | None = None) -> Summary:
    """Summarize a LectureSession; persists nothing (caller saves)."""
    from mink.llm.factory import get_provider as _get_provider

    provider = provider or _get_provider()
    if session.transcript is None:
        raise ValueError("Session has no transcript to summarize")
    segments = [
        {"start": s.start, "end": s.end, "text": s.text, "speaker": s.speaker}
        for s in session.transcript.segments
    ]
    return summarize_transcript(segments, session.transcript.text, provider, title=session.title)
