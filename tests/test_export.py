"""Tests for transcript export formats."""

from mink.engine import TranscriptionResult, TranscriptionSegment
from mink.pipeline import LectureSession
from mink.pipeline.export import export_markdown, export_srt, export_txt, export_vtt


def _session() -> LectureSession:
    s = LectureSession(title="Lecture 1", course="CS 101")
    s.transcript = TranscriptionResult(
        text="hello world",
        segments=[
            TranscriptionSegment(start=0.5, end=2.0, text="hello", speaker="SPEAKER_00"),
            TranscriptionSegment(start=2.5, end=4.0, text="world", speaker="SPEAKER_01"),
        ],
    )
    return s


def test_export_txt():
    assert export_txt(_session()) == "hello world"


def test_export_srt_format():
    srt = export_srt(_session())
    assert "00:00:00,500 --> 00:00:02,000" in srt
    assert "[SPEAKER_00] hello" in srt
    assert srt.splitlines()[0] == "1"


def test_export_vtt_format():
    vtt = export_vtt(_session())
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.500 --> 00:00:02.000" in vtt
    assert "<v SPEAKER_00>hello</v>" in vtt


def test_export_markdown_structure():
    md = export_markdown(_session())
    assert md.startswith("# Lecture 1")
    assert "## Transcript" in md
    assert "[00:00] **SPEAKER_00**: hello" in md


def test_export_markdown_with_summary():
    s = _session()
    s.set_summary(
        {
            "tldr": "All about greetings.",
            "chapters": [{"title": "Intro", "start": "00:00", "end": "01:00", "bullets": ["hi"]}],
            "key_points": ["say hi"],
            "action_items": [],
            "terms": [],
        }
    )
    md = export_markdown(s)
    assert "## Summary" in md
    assert "All about greetings." in md
    assert "## Chapters" in md
