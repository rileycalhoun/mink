"""Smoke tests for Mink configuration and model catalog."""

from mink.config import Settings
from mink.engine.models import MODELS, get_model


def test_settings_defaults():
    s = Settings()
    assert s.web_port == 8473
    assert s.default_model == "parakeet-tdt-0.6b-v3"


def test_model_catalog():
    assert "parakeet-tdt-0.6b-v3" in MODELS
    assert "parakeet-ctc-1.1b" in MODELS
    assert "nemotron-speech-streaming-en-0.6b" in MODELS
    info = get_model("parakeet-tdt-0.6b-v3")
    assert info.hf_repo == "nvidia/parakeet-tdt-0.6b-v3"


def test_unknown_model_raises():
    try:
        get_model("nope")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
