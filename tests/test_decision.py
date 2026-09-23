"""Tests for the Jev decision layer: wire format, verdicts, factory gating."""

from __future__ import annotations

import json

import httpx
import pytest

from mink.config import settings
from mink.decision import (
    Choice,
    ChoiceAnswer,
    DecisionNotConfigured,
    JevProvider,
    Noul,
    NoulAnswer,
    Score,
    ScoreAnswer,
    SummaryVerdict,
    SystemOneResponse,
    decision_status,
    evaluate_summary,
    get_decision_provider,
)


def _jev_response() -> dict:
    return {
        "model": "jev-1.13.0",
        "answers": {
            "faithfulness": {
                "type": "choice",
                "choice": "faithful",
                "confidence": 0.91,
                "probabilities": {"faithful": 0.91, "minor_drift": 0.07, "unfaithful": 0.02},
            },
            "quality": {
                "type": "score",
                "score": 3.4,
                "confidence": 0.82,
                "legend": {
                    "0": "Poor",
                    "1": "Weak",
                    "2": "Adequate",
                    "3": "Good",
                    "4": "Excellent",
                },
                "probabilities": {"0": 0.0, "1": 0.0, "2": 0.1, "3": 0.4, "4": 0.5},
            },
            "action_items_real": {"type": "noul", "noul": 0.97},
        },
        "usage": {"input_tokens": 1200, "output_tokens": 12},
    }


def _provider_with(handler) -> JevProvider:
    provider = JevProvider(api_key="test-key", base_url="https://api.typesafe.ai")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))
    return provider


def test_wire_request_shape():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_jev_response())

    resp = _provider_with(handler).decide("some state", {"q": Noul(instructions="Yes?")})
    assert seen["path"] == "/v1/systemone"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["state"] == "some state"
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["questions"]["q"] == {"type": "noul", "instructions": "Yes?"}
    assert resp.model == "jev-1.13.0"
    assert resp.input_tokens == 1200


def test_question_wire_formats():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_jev_response())

    _provider_with(handler).decide(
        "state",
        {
            "c": Choice(instructions="Pick", criteria={"a": "option A", "b": "option B"}),
            "s": Score(instructions="Rate", criteria=["bad", "ok", "great"]),
        },
    )
    q = seen["body"]["questions"]
    assert q["c"]["type"] == "choice" and q["c"]["criteria"]["a"] == "option A"
    assert q["s"]["type"] == "score" and q["s"]["criteria"] == ["bad", "ok", "great"]


def test_answer_parsing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_jev_response())

    resp = _provider_with(handler).decide("state", {})
    faith = resp.answers["faithfulness"]
    assert isinstance(faith, ChoiceAnswer)
    assert faith.choice == "faithful"
    assert faith.confidence == pytest.approx(0.91)
    quality = resp.answers["quality"]
    assert quality.score == pytest.approx(3.4)
    assert quality.probabilities[4] == pytest.approx(0.5)
    items = resp.answers["action_items_real"]
    assert items.noul == pytest.approx(0.97)
    assert items.confidence is None  # noul answers may omit confidence


def test_http_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(RuntimeError, match="Jev request failed"):
        _provider_with(handler).decide("state", {})


def test_available_never_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    assert _provider_with(handler).available() is False


def test_factory_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "jev_api_key", None)
    with pytest.raises(DecisionNotConfigured):
        get_decision_provider()
    status = decision_status()
    assert status == {"provider": None, "model": None, "reachable": False}


def test_factory_builds_jev(monkeypatch):
    monkeypatch.setattr(settings, "jev_api_key", "sk-test")
    monkeypatch.setattr(settings, "jev_model", "jev-latest")
    provider = get_decision_provider()
    assert isinstance(provider, JevProvider)
    assert provider.model == "jev-latest"
    assert provider.base_url == "https://api.typesafe.ai"


class FakeDecisionProvider:
    name = "fake"

    def __init__(self, answers: dict):
        self._answers = answers
        self.seen_state: str | None = None

    def decide(self, state, questions):
        self.seen_state = state
        return SystemOneResponse(model="fake-1", answers=self._answers, input_tokens=10)

    def available(self) -> bool:
        return True


def _fake_answers(faithful: str = "faithful", quality: float = 3.4, items: float = 0.97):
    return {
        "faithfulness": ChoiceAnswer(
            choice=faithful,
            confidence=0.9,
            probabilities={"faithful": 0.9, "minor_drift": 0.08, "unfaithful": 0.02},
        ),
        "quality": ScoreAnswer(
            score=quality, confidence=0.8, probabilities={3: 0.6, 4: 0.4}, legend={}
        ),
        "action_items": NoulAnswer(noul=items),
    }


_SUMMARY = {
    "tldr": "Intro to recursion.",
    "chapters": [{"title": "What is recursion", "bullets": ["base case", "recursive case"]}],
    "key_points": ["recursion needs a base case"],
    "action_items": ["do homework 3"],
    "terms": [{"term": "base case", "definition": "the stopping condition"}],
}


def test_evaluate_summary_verdict():
    provider = FakeDecisionProvider(_fake_answers())
    verdict = evaluate_summary("a lecture about recursion", _SUMMARY, provider)
    assert verdict.faithfulness == "faithful"
    assert verdict.faithfulness_confidence == pytest.approx(0.9)
    assert verdict.quality_score == pytest.approx(3.4)
    assert verdict.action_items_probability == pytest.approx(0.97)
    assert verdict.review_recommended is False
    assert "TRANSCRIPT" in provider.seen_state and "SUMMARY UNDER REVIEW" in provider.seen_state
    # round-trips through JSON for session persistence
    restored = SummaryVerdict.from_dict(json.loads(json.dumps(verdict.to_dict())))
    assert restored.faithfulness == "faithful"
    assert restored.review_recommended is False


def test_evaluate_summary_recommends_review_when_unfaithful():
    provider = FakeDecisionProvider(_fake_answers(faithful="unfaithful"))
    verdict = evaluate_summary("transcript", _SUMMARY, provider)
    assert verdict.review_recommended is True


def test_evaluate_summary_recommends_review_on_low_quality():
    provider = FakeDecisionProvider(_fake_answers(quality=1.2))
    verdict = evaluate_summary("transcript", _SUMMARY, provider)
    assert verdict.review_recommended is True


def test_evaluate_summary_recommends_review_on_hallucinated_items():
    provider = FakeDecisionProvider(_fake_answers(items=0.1))
    verdict = evaluate_summary("transcript", _SUMMARY, provider)
    assert verdict.review_recommended is True


def test_evaluate_session_requires_transcript_and_summary():
    provider = FakeDecisionProvider(_fake_answers())

    class Session:
        transcript = None
        summary = None

    with pytest.raises(ValueError, match="no transcript"):
        from mink.decision import evaluate_session

        evaluate_session(Session(), provider)
