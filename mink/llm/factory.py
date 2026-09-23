"""Provider selection from settings."""

from __future__ import annotations

from mink.config import settings
from mink.llm.providers import (
    LLMNotConfigured,
    LLMProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)

_DEFAULT_BASE_URLS = {
    "ollama": "http://127.0.0.1:11434",
    "openai": "https://api.openai.com/v1",
}


def get_provider() -> LLMProvider:
    """Build the configured provider, or raise :class:`LLMNotConfigured`."""
    name = settings.llm_provider.lower()
    if name == "none":
        raise LLMNotConfigured(
            "LLM features are disabled (MINK_LLM_PROVIDER=none). "
            "Set it to 'ollama' or 'openai' to enable them."
        )
    base_url = settings.llm_base_url or _DEFAULT_BASE_URLS.get(name)
    if name == "ollama":
        return OllamaProvider(
            base_url=base_url or _DEFAULT_BASE_URLS["ollama"], model=settings.llm_model
        )
    if name == "openai":
        return OpenAICompatibleProvider(
            base_url=base_url or _DEFAULT_BASE_URLS["openai"],
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    raise LLMNotConfigured(
        f"Unknown LLM provider {name!r} (expected 'ollama', 'openai', or 'none')"
    )


def provider_status() -> dict:
    """Status dict for the health endpoint; never raises."""
    name = settings.llm_provider.lower()
    if name == "none":
        return {"provider": "none", "model": None, "reachable": False}
    try:
        provider = get_provider()
        model = getattr(provider, "model", None)
        return {"provider": name, "model": model, "reachable": provider.available()}
    except Exception:  # noqa: BLE001 — status must never raise
        return {"provider": name, "model": settings.llm_model, "reachable": False}
