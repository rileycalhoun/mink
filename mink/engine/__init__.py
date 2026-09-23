"""Transcription engine: NVIDIA ASR models served by nemo-speech.cpp."""

from .client import EngineClient, TranscriptionResult, TranscriptionSegment
from .manager import EngineState, engine_manager
from .models import MODELS, ModelInfo, default_model, get_model

__all__ = [
    "MODELS",
    "EngineClient",
    "EngineState",
    "ModelInfo",
    "TranscriptionResult",
    "TranscriptionSegment",
    "default_model",
    "engine_manager",
    "get_model",
]
