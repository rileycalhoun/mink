"""Decision provider implementations: typed questions, probabilistic answers.

Each provider evaluates *state* (plain text) against a set of typed
questions in a single parallel pass. Supported question kinds mirror the
TypeSafe SystemOne primitives:

- :class:`Choice` — pick one of several named options; answer carries the
  chosen option plus a full probability distribution.
- :class:`Score` — rate against an ordered rubric; answer carries the
  expected level (probability-weighted) plus the distribution.
- :class:`Noul` — a yes/no judgment; answer carries the probability of yes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

_SYSTEMONE_PATH = "/v1/systemone"


@dataclass
class Choice:
    """Select the best option for the state."""

    instructions: str
    criteria: dict[str, str]  # option id → description of what it means

    def to_wire(self) -> dict:
        return {
            "type": "choice",
            "instructions": self.instructions,
            "criteria": self.criteria,
        }


@dataclass
class Score:
    """Rate the state against an ordered rubric."""

    instructions: str
    criteria: list[str]  # ordered levels, index 0 .. n-1

    def to_wire(self) -> dict:
        return {
            "type": "score",
            "instructions": self.instructions,
            "criteria": self.criteria,
        }


@dataclass
class Noul:
    """A yes/no judgment about the state (probability of yes)."""

    instructions: str

    def to_wire(self) -> dict:
        return {"type": "noul", "instructions": self.instructions}


Question = Choice | Score | Noul


@dataclass
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass
class ScoreAnswer:
    score: float  # expected level: Σ level × P(level)
    confidence: float
    probabilities: dict[int, float]
    legend: dict[int, str]


@dataclass
class NoulAnswer:
    noul: float  # P(yes)
    confidence: float | None = None


SystemOneAnswer = ChoiceAnswer | ScoreAnswer | NoulAnswer


@dataclass
class SystemOneResponse:
    model: str
    answers: dict[str, SystemOneAnswer]
    input_tokens: int = 0
    output_tokens: int = 0


class DecisionNotConfigured(RuntimeError):
    """Raised when a decision feature is used but no provider is configured."""


class DecisionProvider(Protocol):
    """The interface every decision backend implements."""

    name: str

    def decide(self, state: str, questions: dict[str, Question]) -> SystemOneResponse:
        """Evaluate all questions against the state in one parallel pass."""
        ...

    def available(self) -> bool:
        """Cheap reachability check; never raises."""
        ...


def _parse_answer(raw: dict) -> SystemOneAnswer:
    kind = raw.get("type")
    if kind == "choice":
        return ChoiceAnswer(
            choice=raw["choice"],
            confidence=float(raw.get("confidence", 0.0)),
            probabilities={k: float(v) for k, v in raw.get("probabilities", {}).items()},
        )
    if kind == "score":
        probs = {int(k): float(v) for k, v in raw.get("probabilities", {}).items()}
        return ScoreAnswer(
            score=float(raw["score"]),
            confidence=float(raw.get("confidence", 0.0)),
            probabilities=probs,
            legend={int(k): v for k, v in raw.get("legend", {}).items()},
        )
    if kind == "noul":
        conf = raw.get("confidence")
        return NoulAnswer(
            noul=float(raw["noul"]),
            confidence=None if conf is None else float(conf),
        )
    raise ValueError(f"Unknown answer type {kind!r}")


class JevProvider:
    """TypeSafe's Jev model via the SystemOne API (``POST /v1/systemone``).

    Jev does not generate text: it evaluates typed questions against state
    and returns calibrated probabilities. Pricing is per input token; output
    is free.
    """

    name = "jev"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.typesafe.ai",
        model: str = "jev-latest",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def _client_for_request(self) -> httpx.Client:
        # trust_env=False keeps proxy env vars out of the API path, same as
        # the transcription engine client.
        if self._client is None:
            self._client = httpx.Client(trust_env=False, timeout=self.timeout)
        return self._client

    def decide(self, state: str, questions: dict[str, Question]) -> SystemOneResponse:
        payload = {
            "state": state,
            "model": self.model,
            "questions": {name: q.to_wire() for name, q in questions.items()},
        }
        try:
            resp = self._client_for_request().post(
                f"{self.base_url}{_SYSTEMONE_PATH}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Jev request failed: {exc}") from exc
        raw = resp.json()
        usage = raw.get("usage", {})
        return SystemOneResponse(
            model=raw.get("model", self.model),
            answers={name: _parse_answer(a) for name, a in raw["answers"].items()},
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )

    def available(self) -> bool:
        # SystemOne has no ping endpoint; a 401/403 from an authorized call
        # still proves the network path is alive. Never raises.
        try:
            resp = self._client_for_request().post(
                f"{self.base_url}{_SYSTEMONE_PATH}",
                json={
                    "state": "ping",
                    "model": self.model,
                    "questions": {"alive": {"type": "noul", "instructions": "Is this a ping?"}},
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0,
            )
            return resp.status_code in (200, 400, 401, 403)
        except httpx.HTTPError:
            return False
