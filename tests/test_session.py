"""Tests for session persistence round-trips."""

from mink.config import settings
from mink.engine import TranscriptionResult, TranscriptionSegment
from mink.pipeline import LectureSession


def _session() -> LectureSession:
    s = LectureSession(title="Lecture 1", course="CS 101")
    s.transcript = TranscriptionResult(
        text="hello world",
        language="en",
        segments=[
            TranscriptionSegment(start=0.5, end=2.0, text="hello", speaker="SPEAKER_00"),
            TranscriptionSegment(start=2.5, end=4.0, text="world", speaker="SPEAKER_01"),
        ],
    )
    s.set_summary(
        {
            "tldr": "greetings",
            "chapters": [],
            "key_points": ["say hello"],
            "action_items": [],
            "glossary": [],
        }
    )
    return s


def test_save_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    original = _session()
    path = original.save()
    assert path.exists()

    loaded = LectureSession.load(original.id)
    assert loaded.id == original.id
    assert loaded.title == "Lecture 1"
    assert loaded.course == "CS 101"
    assert loaded.created_at == original.created_at

    # Segments must come back as TranscriptionSegment objects, not dicts.
    assert loaded.transcript is not None
    assert loaded.transcript.text == "hello world"
    assert loaded.transcript.language == "en"
    assert len(loaded.transcript.segments) == 2
    for seg in loaded.transcript.segments:
        assert isinstance(seg, TranscriptionSegment)
    assert loaded.transcript.segments[0].text == "hello"
    assert loaded.transcript.segments[0].start == 0.5
    assert loaded.transcript.segments[1].speaker == "SPEAKER_01"

    assert loaded.summary is not None
    assert loaded.summary["tldr"] == "greetings"


def test_load_session_without_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    original = LectureSession(title="Untranscribed")
    original.save()

    loaded = LectureSession.load(original.id)
    assert loaded.transcript is None
    assert loaded.title == "Untranscribed"
