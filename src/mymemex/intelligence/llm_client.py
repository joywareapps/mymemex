"""LLM client abstraction for classification and extraction."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog
import asyncio

from ..config import LLMConfig

log = structlog.get_logger()

# Global semaphore for LLM concurrency control
_llm_semaphore: asyncio.Semaphore | None = None


def _get_llm_semaphore(max_concurrent: int) -> asyncio.Semaphore:
    """Get or create global LLM semaphore."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(max_concurrent)
    return _llm_semaphore


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


class ConcurrencyLimitedClient(LLMClient):
    """Wrapper that limits concurrent calls to an LLM client."""

    def __init__(self, inner: LLMClient, max_concurrent: int):
        self.inner = inner
        self.max_concurrent = max_concurrent

    async def generate(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        sem = _get_llm_semaphore(self.max_concurrent)
        async with sem:
            return await self.inner.generate(prompt, system, json_mode)

    async def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        sem = _get_llm_semaphore(self.max_concurrent)
        async with sem:
            return await self.inner.generate_json(prompt, system)


class OllamaClient(LLMClient):
    """Ollama LLM client."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.api_base.rstrip("/")
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


class AnthropicClient(LLMClient):
    """Anthropic LLM client."""

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
        """Generate text via Anthropic Messages API."""
        messages = [{"role": "user", "content": prompt}]

        payload: dict[str, Any] = {
            "model": self.config.model or "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            payload["system"] = system
        if json_mode:
            prompt_suffix = "\n\nReturn valid JSON only, no other text."
            payload["messages"] = [{"role": "user", "content": prompt + prompt_suffix}]

        response = await self._client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON via Anthropic API."""
        text = await self.generate(prompt, system=system, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse Anthropic JSON", error=str(e))
            raise ValueError(f"Invalid JSON from Anthropic: {e}")


class NoneClient(LLMClient):
    """Client that does nothing (for 'none' provider)."""

    async def generate(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        return ""

    async def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        return {}


def create_llm_client(config: LLMConfig) -> LLMClient:
    """Create LLM client based on config. Reads API keys from config or environment."""
    log.debug("Creating LLM client", provider=config.provider, model=config.model, base=config.api_base)
    
    client: LLMClient
    if config.provider == "ollama":
        client = OllamaClient(config)
    elif config.provider == "openai":
        api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key required (set llm.api_key or OPENAI_API_KEY env var)")
        client = OpenAIClient(config, api_key)
    elif config.provider == "anthropic":
        api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key required (set llm.api_key or ANTHROPIC_API_KEY env var)")
        client = AnthropicClient(config, api_key)
    elif config.provider == "none" or not config.provider:
        client = NoneClient()
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")

    # Wrap with concurrency limit
    return ConcurrencyLimitedClient(client, config.max_concurrent)
