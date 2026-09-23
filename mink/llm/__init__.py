"""LLM integration for Mink.

This package is the single seam between Mink and language models. Everything
that needs an LLM (summaries today; Q&A, flashcards, quiz generation tomorrow)
goes through :class:`LLMProvider` — never a vendor SDK directly.

Providers are chosen in settings (``MINK_LLM_PROVIDER``):

- ``ollama`` — local models via Ollama (default; fully offline)
- ``openai`` — any OpenAI-compatible chat-completions endpoint
  (OpenAI, vLLM, LM Studio, …)
- ``none`` — LLM features disabled; calls raise :class:`LLMNotConfigured`
"""

from .factory import get_provider, provider_status
from .providers import (
    LLMNotConfigured,
    LLMProvider,
    Message,
    OllamaProvider,
    OpenAICompatibleProvider,
)
from .summarize import Chapter, Summary, Term, summarize_session, summarize_transcript

__all__ = [
    "Chapter",
    "LLMNotConfigured",
    "LLMProvider",
    "Message",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "Summary",
    "Term",
    "get_provider",
    "provider_status",
    "summarize_session",
    "summarize_transcript",
]
