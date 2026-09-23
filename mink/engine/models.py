"""Catalog of ASR models supported by the Mink transcription engine.

Mink transcribes with NVIDIA's Parakeet / Nemotron speech models, served
locally by ``nemo-speech.cpp`` (``nemo-speech serve``), which exposes an
OpenAI-compatible ``/v1/audio/transcriptions`` endpoint.

Model weights are published by NVIDIA under CC-BY-4.0. They are downloaded
at setup time, never redistributed with this repository.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelInfo:
    """A model Mink knows how to pull and serve."""

    name: str
    """Short name used with ``nemo-speech pull``."""
    hf_repo: str
    """Hugging Face repository id for the GGUF artifact."""
    description: str
    languages: str
    streaming: bool = False
    offline: bool = True
    notes: str = ""


MODELS: dict[str, ModelInfo] = {
    "parakeet-tdt-0.6b-v3": ModelInfo(
        name="parakeet-tdt-0.6b-v3",
        hf_repo="nvidia/parakeet-tdt-0.6b-v3",
        description="0.6B Token-and-Duration Transducer. Self-punctuating with "
        "word-level timestamps; the default for file transcription.",
        languages="25 European languages (strong English)",
        streaming=False,
        offline=True,
    ),
    "parakeet-ctc-1.1b": ModelInfo(
        name="parakeet-ctc-1.1b",
        hf_repo="nvidia/parakeet-ctc-1.1b",
        description="1.1B English FastConformer-CTC. Whole-file or overlapping "
        "buffered streaming; pair with the PnC companion for punctuation.",
        languages="English",
        streaming=True,
        offline=True,
        notes="Emits lowercase unpunctuated text; enable the PnC companion model.",
    ),
    "nemotron-speech-streaming-en-0.6b": ModelInfo(
        name="nemotron-speech-streaming-en-0.6b",
        hf_repo="nvidia/nemotron-speech-streaming-en-0.6b",
        description="0.6B cache-aware FastConformer-RNNT. The choice for live "
        "lecture transcription from the microphone.",
        languages="English",
        streaming=True,
        offline=True,
    ),
    "nemotron-3.5": ModelInfo(
        name="nemotron-3.5",
        hf_repo="nvidia/nemotron-3.5-asr-streaming-0.6b",
        description="0.6B prompt-conditioned RNNT across 40+ language locales. "
        "Whole-file, recorded streaming, and live microphone modes.",
        languages="40+ locales",
        streaming=True,
        offline=True,
    ),
}

DIARIZATION_MODELS: dict[str, str] = {
    # Sortformer v2: streaming speaker diarization, up to 4 speakers.
    "sortformer-v2": "nvidia/diar_streaming_sortformer_4spk-v2",
}


def default_model() -> ModelInfo:
    from mink.config import settings

    return MODELS[settings.default_model]


def get_model(name: str) -> ModelInfo:
    try:
        return MODELS[name]
    except KeyError:
        known = ", ".join(sorted(MODELS))
        raise ValueError(f"Unknown model {name!r}. Known models: {known}") from None
