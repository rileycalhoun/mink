"""Global configuration for Mink.

All settings can be overridden with environment variables prefixed ``MINK_``,
e.g. ``MINK_ENGINE_URL`` or ``MINK_DEFAULT_MODEL``.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MINK_", env_nested_delimiter="__")

    # Where the nemo-speech.cpp server listens (OpenAI-compatible API).
    engine_url: str = Field(default="http://127.0.0.1:8000")

    # Default transcription model; see mink.engine.models.MODELS.
    default_model: str = Field(default="parakeet-tdt-0.6b-v3")

    # Default diarization companion model (None disables speaker labels).
    diarization_model: str | None = Field(default="sortformer-v2")

    # Where sessions, audio, and transcripts are stored.
    data_dir: Path = Field(default=Path.home() / ".local" / "share" / "mink")

    # Web UI / API bind address.
    web_host: str = Field(default="127.0.0.1")
    web_port: int = Field(default=8473)

    # --- LLM (summaries and future LLM features) ---
    # Provider: "ollama" (local default), "openai" (any OpenAI-compatible
    # endpoint), or "none" (LLM features disabled).
    llm_provider: str = Field(default="ollama")
    llm_model: str = Field(default="llama3.1")
    llm_base_url: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None)

    # --- Live transcription ---
    live_model: str = Field(default="parakeet-ctc-1.1b")
    live_window_seconds: float = Field(default=12.0)
    live_overlap_seconds: float = Field(default=3.0)
    # Chunks quieter than this RMS are skipped (saves engine calls).
    live_silence_rms: float = Field(default=120.0)

    # --- On-demand cloud engine (RunPod) ---
    # API key for RunPod; when unset, the on-demand engine is disabled and
    # Mink uses the static engine_url above.
    runpod_api_key: str | None = Field(default=None)
    # Terminate the GPU pod after this many idle minutes (0 disables auto-stop).
    runpod_idle_minutes: int = Field(default=20)

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


settings = Settings()
