"""LLM provider implementations.

Each provider speaks plain HTTP to a chat API. No vendor SDKs — adding a new
model host means writing one small class that implements :class:`LLMProvider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMNotConfigured(RuntimeError):
    """Raised when an LLM feature is used but no provider is configured."""


class LLMProvider(Protocol):
    """The interface every LLM backend implements."""

    name: str

    def complete(
        self,
        messages: list[Message],
        *,
        json_mode: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        """Return the assistant's reply text for a chat conversation."""
        ...

    def available(self) -> bool:
        """Cheap reachability check; never raises."""
        ...


class OllamaProvider:
    """Local models through Ollama's ``/api/chat`` endpoint."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(
        self,
        messages: list[Message],
        *,
        json_mode: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        return resp.json()["message"]["content"]

    def available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


class OpenAICompatibleProvider:
    """Any OpenAI-style ``/chat/completions`` endpoint (OpenAI, vLLM, LM Studio…)."""

    name = "openai"

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def complete(
        self,
        messages: list[Message],
        *,
        json_mode: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        return resp.json()["choices"][0]["message"]["content"]

    def available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=5.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
