"""Provider selection from settings."""

from __future__ import annotations

from mink.config import settings
from mink.decision.providers import DecisionNotConfigured, DecisionProvider, JevProvider


def get_decision_provider() -> DecisionProvider:
    """Build the configured provider, or raise :class:`DecisionNotConfigured`.

    Decision features are opt-in: they stay off until ``MINK_JEV_API_KEY`` is
    set. This keeps the default Mink install fully local and offline.
    """
    api_key = (settings.jev_api_key or "").strip()
    if not api_key:
        raise DecisionNotConfigured(
            "Jev decision features are disabled (no MINK_JEV_API_KEY). "
            "Set it to a TypeSafe API key to enable the faithfulness gate."
        )
    return JevProvider(
        api_key=api_key,
        base_url=settings.jev_base_url,
        model=settings.jev_model,
    )


def decision_status() -> dict:
    """Status dict for the health endpoint; never raises."""
    try:
        provider = get_decision_provider()
    except DecisionNotConfigured:
        return {"provider": None, "model": None, "reachable": False}
    try:
        return {
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "reachable": provider.available(),
        }
    except Exception:  # noqa: BLE001 — status must never raise
        return {
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "reachable": False,
        }
