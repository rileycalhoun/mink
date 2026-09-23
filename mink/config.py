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

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


settings = Settings()
