"""LLM client abstraction for classification and extraction."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from ..config import LLMConfig

log = structlog.get_logger()


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text completion."""
        ...

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON completion."""
        ...


class OllamaClient(LLMClient):
    """Ollama LLM client."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.api_base
        self.model = config.model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text via Ollama API."""
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        response = await self._client.post(
            f"{self.base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON via Ollama API."""
        text = await self.generate(prompt, system=system, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse LLM JSON", error=str(e), text=text[:200])
            raise ValueError(f"Invalid JSON from LLM: {e}")


class OpenAIClient(LLMClient):
    """OpenAI-compatible LLM client."""

    def __init__(self, config: LLMConfig, api_key: str):
        self.config = config
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text via OpenAI API."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.config.model or "gpt-4o-mini",
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON via OpenAI API."""
        text = await self.generate(prompt, system=system, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse OpenAI JSON", error=str(e))
            raise ValueError(f"Invalid JSON from OpenAI: {e}")


def create_llm_client(config: LLMConfig, api_key: str | None = None) -> LLMClient:
    """Create LLM client based on config."""
    if config.provider == "ollama":
        return OllamaClient(config)
    elif config.provider == "openai":
        if not api_key:
            raise ValueError("OpenAI API key required")
        return OpenAIClient(config, api_key)
    elif config.provider == "anthropic":
        raise NotImplementedError("Anthropic client not yet implemented")
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
