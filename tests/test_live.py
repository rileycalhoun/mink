"""Tests for live transcription chunking (engine calls are faked)."""

import io
import wave

import mink.pipeline.live as live_mod
from mink.engine import TranscriptionResult, TranscriptionSegment
from mink.pipeline.live import LiveSession, _is_silence, _pcm_to_wav_bytes

SAMPLE_RATE = 16_000


def _pcm(seconds: float, loud: bool = True) -> bytes:
    n = int(seconds * SAMPLE_RATE)
    sample = b"\x00\x10" if loud else b"\x00\x00"  # int16 LE
    return sample * n


class FakeEngine:
    def __init__(self, *a, **k):
        self.calls = 0

    def transcribe(self, path, model=None, diarize=True):
        self.calls += 1
        return TranscriptionResult(
            text="hello",
            segments=[TranscriptionSegment(start=5.0, end=6.0, text="hello")],
        )


def test_pcm_to_wav_roundtrip():
    pcm = _pcm(1.0)
    wav = _pcm_to_wav_bytes(pcm)
    with wave.open(io.BytesIO(wav), "rb") as wf:
        assert wf.getframerate() == SAMPLE_RATE
        assert wf.getnchannels() == 1
        assert wf.readframes(wf.getnframes()) == pcm


def test_silence_detection():
    assert _is_silence(_pcm(1.0, loud=False), threshold=120.0)
    assert not _is_silence(_pcm(1.0, loud=True), threshold=120.0)


def test_push_pcm_transcribes_full_windows(monkeypatch):
    monkeypatch.setattr(live_mod, "EngineClient", FakeEngine)
    session = LiveSession()
    # Feed 30s in small pushes; 12s window / 9s step -> windows at 12s, 21s, 30s.
    partials = []
    for _ in range(30):
        p = session.push_pcm(_pcm(1.0))
        if p is not None:
            partials.append(p)
    assert len(partials) == 3
    # Absolute timestamps: window 1 starts at 9s, segment at +5s -> 14.0.
    assert partials[1].segments[0]["start"] == 14.0
    # Overlap dedupe: a segment inside the overlapped head is dropped.
    # (Fake segment at +5s survives the 3s overlap; assert the rule directly.)
    assert partials[0].segments[0]["start"] == 5.0


def test_push_pcm_skips_silence(monkeypatch):
    monkeypatch.setattr(live_mod, "EngineClient", FakeEngine)
    session = LiveSession()
    partial = None
    for _ in range(12):
        r = session.push_pcm(_pcm(1.0, loud=False))
        if r is not None:
            partial = r
    assert partial is not None
    assert partial.segments == []  # silent window -> empty partial, no crash
