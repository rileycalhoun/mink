"""Transcription engine: NVIDIA ASR models served by nemo-speech.cpp."""

from .client import EngineClient, TranscriptionResult, TranscriptionSegment
from .models import MODELS, ModelInfo, default_model, get_model

__all__ = [
    "MODELS",
    "EngineClient",
    "ModelInfo",
    "TranscriptionResult",
    "TranscriptionSegment",
    "default_model",
    "get_model",
]
