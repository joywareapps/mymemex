"""Vector embeddings via Ollama HTTP API."""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx
import structlog

log = structlog.get_logger()


class Embedder:
    """Generate embeddings via Ollama HTTP API."""

    def __init__(self, api_base: str, embedding_model: str):
        self.api_base = api_base.rstrip("/")
        self.embedding_model = embedding_model
        self._model_available: Optional[bool] = None

    async def is_available(self) -> bool:
        """Check if Ollama is reachable and the embedding model is available."""
        if self._model_available is not None:
            return self._model_available

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.api_base}/api/tags")
                if resp.status_code != 200:
                    self._model_available = False
                    return False

                models = resp.json().get("models", [])
                model_names = [m["name"] for m in models]

                # Model might be "nomic-embed-text" or "nomic-embed-text:latest"
                model_base = self.embedding_model.split(":")[0]
                self._model_available = any(m.startswith(model_base) for m in model_names)

                if not self._model_available:
                    log.warning(
                        "Embedding model not found in Ollama",
                        model=self.embedding_model,
                        available=model_names,
                    )

                return self._model_available

        except Exception as e:
            log.warning("Ollama not reachable", error=str(e))
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
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.api_base}/api/embeddings",
                    json={"model": self.embedding_model, "prompt": text},
                )
                resp.raise_for_status()
                return resp.json().get("embedding")
        except Exception as e:
            log.error("Sync embedding failed", error=str(e))
            return None

    async def embed_batch(self, texts: list[str]) -> list[Optional[list[float]]]:
        """Generate embeddings for multiple texts sequentially."""
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results
