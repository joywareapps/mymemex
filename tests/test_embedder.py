"""Tests for the Ollama embedder."""

from __future__ import annotations

import pytest
import pytest_asyncio

from librarian.config import LLMConfig
from librarian.intelligence.embedder import Embedder


@pytest.fixture
def llm_config():
    """LLM config pointing at a non-existent Ollama instance."""
    return LLMConfig(
        provider="ollama",
        model="nomic-embed-text",
        api_base="http://localhost:99999",  # unreachable
    )


@pytest.fixture
def embedder(llm_config):
    return Embedder(llm_config)


@pytest.mark.asyncio
async def test_embedder_unavailable(embedder):
    """When Ollama is unreachable, is_available returns False."""
    available = await embedder.is_available()
    assert available is False


@pytest.mark.asyncio
async def test_embed_returns_none_when_unavailable(embedder):
    """embed() returns None when Ollama is unreachable."""
    result = await embedder.embed("some text")
    assert result is None


@pytest.mark.asyncio
async def test_embed_batch_returns_nones_when_unavailable(embedder):
    """embed_batch() returns Nones when Ollama is unreachable."""
    results = await embedder.embed_batch(["hello", "world"])
    assert results == [None, None]


@pytest.mark.asyncio
async def test_availability_cached(embedder):
    """Second call to is_available uses the cached result."""
    assert await embedder.is_available() is False
    # Cached as False — stays False
    assert await embedder.is_available() is False
    assert embedder._model_available is False


@pytest.mark.asyncio
async def test_reset_availability(embedder):
    """reset_availability clears cached result."""
    await embedder.is_available()
    assert embedder._model_available is False

    embedder.reset_availability()
    assert embedder._model_available is None


@pytest.mark.asyncio
async def test_embed_with_mock_ollama(llm_config):
    """When Ollama returns a proper embedding, embed() returns the vector."""
    from unittest.mock import AsyncMock, MagicMock, patch

    fake_embedding = [0.1] * 768

    # Mock the async availability check
    mock_tags_resp = MagicMock()
    mock_tags_resp.status_code = 200
    mock_tags_resp.json.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}

    # Mock the sync embedding call
    mock_embed_resp = MagicMock()
    mock_embed_resp.status_code = 200
    mock_embed_resp.raise_for_status = MagicMock()
    mock_embed_resp.json.return_value = {"embedding": fake_embedding}

    embedder = Embedder(llm_config)

    # Patch the async client for is_available
    with patch("httpx.AsyncClient") as mock_async:
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_tags_resp
        mock_async.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_async.return_value.__aexit__ = AsyncMock(return_value=False)

        available = await embedder.is_available()
        assert available is True

    # Patch the sync client for embed
    with patch("httpx.Client") as mock_sync:
        mock_sync_instance = MagicMock()
        mock_sync_instance.post.return_value = mock_embed_resp
        mock_sync.return_value.__enter__ = MagicMock(return_value=mock_sync_instance)
        mock_sync.return_value.__exit__ = MagicMock(return_value=False)

        result = await embedder.embed("hello world")
        assert result == fake_embedding
        assert len(result) == 768
