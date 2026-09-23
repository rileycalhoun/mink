"""Typed decision providers for Mink.

A decision provider evaluates *state* against *typed questions* and returns
structured, probabilistic judgments — no generated prose. Jev (TypeSafe
SystemOne) is the backend. This sits *beside* the generative LLM seam in
``mink.llm``: the LLM writes summaries, the decision provider verifies them
(faithfulness gate, action-item checks) and classifies things the UI can
branch on.

Like ``mink.llm.providers``, this speaks plain HTTP to the vendor endpoint —
no vendor SDKs. One class implementing :class:`DecisionProvider` adds a new
decision backend.
"""

from .evaluate import (
    SummaryVerdict,
    evaluate_session,
    evaluate_summary,
)
from .factory import decision_status, get_decision_provider
from .providers import (
    Choice,
    ChoiceAnswer,
    DecisionNotConfigured,
    DecisionProvider,
    JevProvider,
    Noul,
    NoulAnswer,
    Question,
    Score,
    ScoreAnswer,
    SystemOneAnswer,
    SystemOneResponse,
)

__all__ = [
    "Choice",
    "ChoiceAnswer",
    "DecisionNotConfigured",
    "DecisionProvider",
    "JevProvider",
    "Noul",
    "NoulAnswer",
    "Question",
    "Score",
    "ScoreAnswer",
    "SummaryVerdict",
    "SystemOneAnswer",
    "SystemOneResponse",
    "decision_status",
    "evaluate_session",
    "evaluate_summary",
    "get_decision_provider",
]
