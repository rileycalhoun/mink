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


def test_store_delete_removes_json_and_audio(tmp_path, monkeypatch):
    """SessionStore.delete removes the session file and its audio file."""
    from mink.pipeline.store import SessionStore

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.audio_dir.mkdir(parents=True)
    settings.sessions_dir.mkdir(parents=True)

    session = _session()
    audio_file = settings.audio_dir / "clip.wav"
    audio_file.write_bytes(b"fake-wav")
    session.audio_path = audio_file
    session.save()

    store = SessionStore()
    assert store.delete(session.id) is True
    assert not (settings.sessions_dir / f"{session.id}.json").exists()
    assert not audio_file.exists()


def test_store_delete_missing_returns_false(tmp_path, monkeypatch):
    from mink.pipeline.store import SessionStore

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.sessions_dir.mkdir(parents=True)

    store = SessionStore()
    assert store.delete("nope") is False


def test_store_delete_rejects_path_traversal(tmp_path, monkeypatch):
    from mink.pipeline.store import SessionStore

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.sessions_dir.mkdir(parents=True)

    store = SessionStore()
    assert store.delete("../../etc/passwd") is False


def test_session_new_fields_round_trip(tmp_path, monkeypatch):
    """teacher and folder_id persist through save/load."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    s = _session()
    s.teacher = "Dr. Alvarez"
    s.folder_id = "abc123"
    s.save()
    loaded = LectureSession.load(s.id)
    assert loaded.teacher == "Dr. Alvarez"
    assert loaded.folder_id == "abc123"


def test_session_load_tolerates_legacy_json(tmp_path, monkeypatch):
    """Sessions written before teacher/folder_id existed still load."""
    import json

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.sessions_dir.mkdir(parents=True)
    s = _session()
    data = s.to_dict()
    del data["teacher"]
    del data["folder_id"]
    (settings.sessions_dir / f"{s.id}.json").write_text(json.dumps(data))
    loaded = LectureSession.load(s.id)
    assert loaded.teacher == ""
    assert loaded.folder_id is None


def test_store_update_metadata(tmp_path, monkeypatch):
    from mink.pipeline.store import SessionStore

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    s = _session()
    s.save()

    store = SessionStore()
    updated = store.update(s.id, teacher="Dr. Alvarez", course="Anthropology C1001")
    assert updated is not None
    assert updated.teacher == "Dr. Alvarez"
    assert updated.course == "Anthropology C1001"
    # Persisted, and unknown fields are ignored.
    reloaded = LectureSession.load(s.id)
    assert reloaded.teacher == "Dr. Alvarez"
    assert store.update("missing", teacher="x") is None


def test_store_clear_folder(tmp_path, monkeypatch):
    from mink.pipeline.store import SessionStore

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    s1 = _session()
    s1.folder_id = "f1"
    s1.save()
    s2 = _session()
    s2.folder_id = "f1"
    s2.save()
    s3 = _session()
    s3.save()

    store = SessionStore()
    assert store.clear_folder("f1") == 2
    assert LectureSession.load(s1.id).folder_id is None
    assert LectureSession.load(s2.id).folder_id is None
    assert LectureSession.load(s3.id).folder_id is None
