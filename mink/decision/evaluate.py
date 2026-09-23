"""The faithfulness gate: Jev verifies an LLM summary against its transcript.

Flow: the generative LLM (``mink.llm``) writes a summary; this module asks
Jev typed questions about that summary *against the source transcript*, in
one parallel pass. The result is a :class:`SummaryVerdict` persisted with the
summary so the UI can show a faithfulness badge — or flag a summary for
human review.

Three questions, one call:

- ``faithfulness`` (Choice) — is every claim grounded in the transcript?
- ``quality`` (Score 0–4) — how good a study aid is the summary?
- ``action_items`` (Noul) — do the action items correspond to real
  assignments/follow-ups mentioned in the transcript?
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from mink.decision.providers import Choice, DecisionProvider, Noul, Score

# Jev charges per input token and decides in well under a second; keep the
# state bounded the same way the summarizer truncates its prompt.
_MAX_STATE_CHARS = 24_000

_QUALITY_RUBRIC = [
    "Poor: misses the lecture's substance or is mostly wrong",
    "Weak: covers only fragments, skips major topics",
    "Adequate: main points present but thin or disorganized",
    "Good: clear structure, captures the substance faithfully",
    "Excellent: complete, well-organized, ready to study from",
]

_REVIEW_QUALITY_BELOW = 2.0  # quality score below this → recommend review
_REVIEW_ACTION_ITEMS_BELOW = 0.5  # P(action items are real) below this → review


@dataclass
class SummaryVerdict:
    """Jev's judgment of one summary, stored under ``summary["verdict"]``."""

    faithfulness: str  # "faithful" | "minor_drift" | "unfaithful"
    faithfulness_confidence: float
    faithfulness_probabilities: dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0  # expected rubric level, 0–4
    quality_confidence: float = 0.0
    action_items_probability: float = 0.0  # P(action items are real)
    review_recommended: bool = False
    model: str = ""
    input_tokens: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SummaryVerdict:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _render_summary(summary: dict) -> str:
    """Serialize a summary dict to the text Jev judges."""
    lines = [f"TL;DR: {summary.get('tldr', '')}".strip()]
    key_points = summary.get("key_points") or []
    if key_points:
        lines.append("Key points:")
        lines += [f"- {p}" for p in key_points]
    chapters = summary.get("chapters") or []
    if chapters:
        lines.append("Chapters:")
        for c in chapters:
            title = c.get("title", "")
            bullets = "; ".join(c.get("bullets") or [])
            lines.append(f"- {title}: {bullets}".rstrip(": "))
    action_items = summary.get("action_items") or []
    if action_items:
        lines.append("Action items:")
        lines += [f"- {a}" for a in action_items]
    terms = summary.get("terms") or []
    if terms:
        lines.append("Glossary terms:")
        lines += [f"- {t.get('term')}: {t.get('definition')}" for t in terms]
    return "\n".join(lines)


def _build_state(transcript_text: str, summary: dict) -> str:
    state = (
        "TRANSCRIPT:\n" + transcript_text.strip() + "\n\n"
        "SUMMARY UNDER REVIEW:\n" + _render_summary(summary)
    )
    if len(state) > _MAX_STATE_CHARS:
        state = state[:_MAX_STATE_CHARS] + "\n…[state truncated]"
    return state


def _questions() -> dict[str, Choice | Score | Noul]:
    return {
        "faithfulness": Choice(
            instructions=(
                "How faithful is the SUMMARY UNDER REVIEW to the TRANSCRIPT? "
                "Judge only whether the summary's claims are grounded in the "
                "transcript — not how well-written it is."
            ),
            criteria={
                "faithful": (
                    "Every claim in the summary is grounded in the transcript; "
                    "no invented facts, dates, names, or assignments."
                ),
                "minor_drift": (
                    "Mostly grounded, but some details are reworded in ways "
                    "that shift meaning, or a minor claim lacks clear support."
                ),
                "unfaithful": (
                    "The summary invents facts, assignments, deadlines, or "
                    "topics not present in the transcript, or contradicts it."
                ),
            },
        ),
        "quality": Score(
            instructions=(
                "Rate the SUMMARY UNDER REVIEW as a study aid for the lecture "
                "covered by the TRANSCRIPT."
            ),
            criteria=_QUALITY_RUBRIC,
        ),
        "action_items": Noul(
            instructions=(
                "Every action item in the SUMMARY UNDER REVIEW corresponds to "
                "a real assignment, deadline, or follow-up mentioned in the "
                "TRANSCRIPT. (If the summary lists no action items, answer yes.)"
            ),
        ),
    }


def evaluate_summary(
    transcript_text: str,
    summary: dict,
    provider: DecisionProvider,
) -> SummaryVerdict:
    """Run the faithfulness gate; raises on provider errors."""
    state = _build_state(transcript_text, summary)
    response = provider.decide(state, _questions())

    faith = response.answers["faithfulness"]
    quality = response.answers["quality"]
    action_items = response.answers["action_items"]

    review = (
        faith.choice == "unfaithful"
        or quality.score < _REVIEW_QUALITY_BELOW
        or action_items.noul < _REVIEW_ACTION_ITEMS_BELOW
    )
    return SummaryVerdict(
        faithfulness=faith.choice,
        faithfulness_confidence=faith.confidence,
        faithfulness_probabilities=dict(faith.probabilities),
        quality_score=round(quality.score, 2),
        quality_confidence=quality.confidence,
        action_items_probability=round(action_items.noul, 3),
        review_recommended=review,
        model=response.model,
        input_tokens=response.input_tokens,
    )


def evaluate_session(session, provider: DecisionProvider | None = None) -> SummaryVerdict:
    """Run the gate on a session that already has a summary.

    Persists nothing (caller saves). Raises ``ValueError`` if the session
    has no transcript or no summary.
    """
    from mink.decision.factory import get_decision_provider as _get

    provider = provider or _get()
    if session.transcript is None:
        raise ValueError("Session has no transcript to verify against")
    if not session.summary:
        raise ValueError("Session has no summary to verify")
    text = session.transcript.text if hasattr(session.transcript, "text") else ""
    if not text:
        text = json.dumps(session.transcript, default=str)
    return evaluate_summary(text, session.summary, provider)
