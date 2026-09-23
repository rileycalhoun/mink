"""Tests for EngineClient's words->segments grouping (all network mocked)."""

from mink.engine.client import _segments_from_words


def _word(text, start, end, speaker=None):
    w = {"word": text, "start": start, "end": end, "confidence": 0.99}
    if speaker is not None:
        w["speaker"] = speaker
    return w


def test_groups_at_sentence_boundaries():
    words = [
        _word("Hello", 0.0, 0.4),
        _word("world.", 0.4, 0.8),
        _word("How", 1.0, 1.2),
        _word("are", 1.2, 1.4),
        _word("you?", 1.4, 1.8),
        _word("Fine", 2.0, 2.3),
        _word("thanks.", 2.3, 2.7),
    ]
    # No sentence run reaches the 6-word minimum, so everything stays one segment.
    segs = _segments_from_words(words)
    assert len(segs) == 1
    assert segs[0].start == 0.0
    assert segs[0].end == 2.7
    assert segs[0].text == "Hello world. How are you? Fine thanks."


def test_sentence_break_after_minimum_words():
    words = [_word(w, i * 0.4, i * 0.4 + 0.3) for i, w in enumerate(
        ["This", "is", "a", "longer", "sentence", "here.", "And", "another", "one", "too.",
         "Yet", "more", "words", "now."]
    )]
    segs = _segments_from_words(words)
    assert len(segs) == 2
    assert segs[0].text == "This is a longer sentence here."
    assert segs[1].text == "And another one too. Yet more words now."


def test_speaker_change_breaks_segment():
    words = [
        _word("Hi", 0.0, 0.3, speaker="SPEAKER_00"),
        _word("there.", 0.3, 0.6, speaker="SPEAKER_00"),
        _word("Hello!", 1.0, 1.3, speaker="SPEAKER_01"),
    ]
    segs = _segments_from_words(words)
    assert len(segs) == 2
    assert segs[0].speaker == "SPEAKER_00"
    assert segs[0].text == "Hi there."
    assert segs[1].speaker == "SPEAKER_01"


def test_hard_cap_on_long_monologue():
    words = [_word(f"w{i}", i * 0.3, i * 0.3 + 0.2) for i in range(50)]
    segs = _segments_from_words(words)
    assert len(segs) == 3  # 24 + 24 + 2
    assert all(len(s.text.split()) <= 24 for s in segs)


def test_empty_words_gives_no_segments():
    assert _segments_from_words([]) == []
    assert _segments_from_words([{"word": "   ", "start": 0, "end": 1}]) == []


def test_missing_timings_default_sensibly():
    segs = _segments_from_words([{"word": "hello"}])
    assert len(segs) == 1
    assert segs[0].start == 0.0
    assert segs[0].text == "hello"
