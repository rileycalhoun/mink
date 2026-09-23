"""Tests for the LLM layer: providers, factory, summarizer."""

import json

import pytest

from mink.llm import (
    LLMNotConfigured,
    Message,
    Summary,
    get_provider,
    provider_status,
    summarize_transcript,
)


class FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, reply: dict):
        self._reply = reply
        self.seen_messages: list[Message] | None = None
        self.seen_json_mode: bool | None = None

    def complete(self, messages, *, json_mode=False, max_tokens=4096, temperature=0.2):
        self.seen_messages = messages
        self.seen_json_mode = json_mode
        return json.dumps(self._reply)

    def available(self) -> bool:
        return True


def _reply():
    return {
        "tldr": "Intro to recursion.",
        "chapters": [
            {
                "title": "What is recursion",
                "start": "00:00",
                "end": "05:00",
                "bullets": ["functions calling themselves"],
            },
        ],
        "key_points": ["base case first"],
        "action_items": ["read chapter 3"],
        "terms": [{"term": "base case", "definition": "the terminating condition"}],
    }


def test_summarize_transcript_parses_structured_summary():
    provider = FakeProvider(_reply())
    segments = [{"start": 0.0, "end": 4.5, "text": "hello class", "speaker": "SPEAKER_00"}]
    summary = summarize_transcript(segments, "hello class", provider, title="CS 101")
    assert summary.tldr == "Intro to recursion."
    assert summary.chapters[0].title == "What is recursion"
    assert summary.key_points == ["base case first"]
    assert summary.action_items == ["read chapter 3"]
    assert summary.terms[0].term == "base case"
    assert summary.model == "fake-1"
    assert provider.seen_json_mode is True
    # Prompt contains timestamped speaker lines.
    user_text = provider.seen_messages[1].content
    assert "[00:00-00:04] SPEAKER_00: hello class" in user_text


def test_summary_roundtrip():
    summary = Summary(tldr="x")
    assert Summary.from_dict(summary.to_dict()).tldr == "x"


def test_factory_none_raises(monkeypatch):
    monkeypatch.setenv("MINK_LLM_PROVIDER", "none")
    # Settings reads env at construction; factory reads global settings —
    # patch the settings object instead.
    from mink.llm import factory

    monkeypatch.setattr(factory.settings, "llm_provider", "none")
    with pytest.raises(LLMNotConfigured):
        get_provider()
    assert provider_status()["reachable"] is False


def test_provider_status_unknown_provider(monkeypatch):
    from mink.llm import factory

    monkeypatch.setattr(factory.settings, "llm_provider", "bogus")
    status = provider_status()
    assert status["reachable"] is False
    assert status["provider"] == "bogus"
