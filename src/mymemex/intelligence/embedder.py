"""Vector embeddings via Ollama or an OpenAI-compatible server (LM Studio)."""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


# Providers that speak the OpenAI embeddings API rather than Ollama's.
_OPENAI_COMPATIBLE = {"lmstudio", "openai"}


class Embedder:
    """Generate embeddings via Ollama or an OpenAI-compatible server.

    `provider` selects the wire format: "ollama" uses /api/tags and
    /api/embeddings, while "lmstudio"/"openai" use /v1/models and
    /v1/embeddings.
    """

    def __init__(
        self,
        api_base: str,
        embedding_model: str,
        timeout: float = 60.0,
        provider: str = "ollama",
    ):
        self.provider = provider
        self.embedding_model = embedding_model
        self.timeout = timeout
        self._model_available: Optional[bool] = None

        base = (api_base or "").rstrip("/")
        if self.openai_style and base and not base.endswith("/v1"):
            base = f"{base}/v1"
        self.api_base = base

    @property
    def openai_style(self) -> bool:
        return self.provider in _OPENAI_COMPATIBLE

    async def is_available(self) -> bool:
        """Check the backend is reachable and the embedding model is present."""
        if self._model_available is not None:
            return self._model_available

        listing = "/v1/models" if self.openai_style else "/api/tags"
        base = self.api_base[: -len("/v1")] if self.openai_style else self.api_base

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base}{listing}")
                if resp.status_code != 200:
                    self._model_available = False
                    return False

                body = resp.json()
                if self.openai_style:
                    model_names = [m["id"] for m in body.get("data", [])]
                else:
                    # LM Studio answers /api/tags with 200 and an error body,
                    # so treat a missing "models" key as "not this backend".
                    model_names = [m["name"] for m in body.get("models", [])]

                # Model might be "nomic-embed-text" or "nomic-embed-text:latest"
                model_base = self.embedding_model.split(":")[0]
                self._model_available = any(m.startswith(model_base) for m in model_names)

                if not self._model_available:
                    log.warning(
                        "Embedding model not found",
                        provider=self.provider,
                        model=self.embedding_model,
                        available=model_names,
                    )

                return self._model_available

        except Exception as e:
            log.warning(
                "Embedding backend not reachable", provider=self.provider, error=str(e)
            )
            self._model_available = False
            return False

    def reset_availability(self) -> None:
        """Reset cached availability (re-check on next call)."""
        self._model_available = None

    async def embed(self, text: str) -> Optional[list[float]]:
        """
        Generate embedding for text.

        Returns:
            Embedding vector, or None if unavailable.
        """
        if not await self.is_available():
            return None

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._embed_sync, text)
        except Exception as e:
            log.error("Embedding failed", error=str(e), text_preview=text[:50])
            return None

    def _embed_sync(self, text: str) -> Optional[list[float]]:
        """Synchronous embedding call (runs in thread pool)."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                if self.openai_style:
                    resp = client.post(
                        f"{self.api_base}/embeddings",
                        json={"model": self.embedding_model, "input": text},
                    )
                    resp.raise_for_status()
                    data = resp.json().get("data") or []
                    return data[0].get("embedding") if data else None

                resp = client.post(
                    f"{self.api_base}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text},
                )
                resp.raise_for_status()
                return resp.json().get("embedding")
        except Exception as e:
            log.error("Sync embedding failed", provider=self.provider, error=str(e))
            return None

    async def embed_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """Generate embeddings for multiple texts sequentially."""
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results
