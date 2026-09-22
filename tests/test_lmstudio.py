"""LM Studio provider: client wiring, JSON mode, and embeddings."""

from __future__ import annotations

import json

import httpx
import pytest

from mymemex.config import LLMConfig
from mymemex.intelligence.embedder import Embedder
from mymemex.intelligence.llm_client import (
    LMStudioClient,
    OpenAIClient,
    create_llm_client,
)


def _cfg(**kw) -> LLMConfig:
    base = dict(provider="lmstudio", model="google/gemma-3-4b",
                api_base="http://box:1234", timeout=5.0)
    base.update(kw)
    return LLMConfig(**base)


# --- Factory / base URL ---


def test_factory_builds_lmstudio_client():
    client = create_llm_client(_cfg())
    assert isinstance(client.inner, LMStudioClient)


def test_lmstudio_needs_no_api_key():
    """LM Studio serves unauthenticated — no key should be required."""
    client = create_llm_client(_cfg(api_key=None))
    assert client.inner.api_key is None
    assert client.inner._headers() == {}


@pytest.mark.parametrize(
    "api_base,expected",
    [
        ("http://box:1234", "http://box:1234/v1"),
        ("http://box:1234/", "http://box:1234/v1"),
        ("http://box:1234/v1", "http://box:1234/v1"),
        ("http://box:1234/v1/", "http://box:1234/v1"),
    ],
)
def test_api_base_normalised_to_v1(api_base, expected):
    """A bare host and one already ending in /v1 both work."""
    assert LMStudioClient(_cfg(api_base=api_base)).base_url == expected


def test_openai_provider_still_uses_openai_com():
    """Switching OpenAIClient to api_base must not redirect real OpenAI calls."""
    client = OpenAIClient(
        LLMConfig(provider="openai", model="gpt-4o-mini", api_base="http://localhost:11434"),
        api_key="sk-test",
    )
    assert client.base_url == "https://api.openai.com/v1"
    assert client._headers() == {"Authorization": "Bearer sk-test"}


# --- JSON mode ---


def test_lmstudio_json_mode_uses_json_schema():
    """LM Studio rejects response_format=json_object, so we must send json_schema."""
    fmt = LMStudioClient(_cfg())._json_response_format()
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["schema"] == {"type": "object"}
    assert OpenAIClient(_cfg(provider="openai"))._json_response_format() == {
        "type": "json_object"
    }


@pytest.mark.asyncio
async def test_generate_json_posts_to_chat_completions():
    """Full request shape against a stub server."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"document_date": "2024-03-15"}'}}]},
        )

    client = LMStudioClient(_cfg())
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    result = await client.generate_json("extract the date")

    assert result == {"document_date": "2024-03-15"}
    assert seen["url"] == "http://box:1234/v1/chat/completions"
    assert seen["body"]["model"] == "google/gemma-3-4b"
    assert seen["body"]["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_generate_json_raises_on_non_json():
    client = LMStudioClient(_cfg())
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        )
    )
    with pytest.raises(ValueError, match="Invalid JSON from LM Studio"):
        await client.generate_json("x")


# --- Embeddings ---


def test_embedder_openai_style_for_lmstudio():
    e = Embedder(api_base="http://box:1234", embedding_model="text-embedding-nomic-embed-text-v1.5",
                 provider="lmstudio")
    assert e.openai_style is True
    assert e.api_base == "http://box:1234/v1"

    o = Embedder(api_base="http://box:11434", embedding_model="nomic-embed-text", provider="ollama")
    assert o.openai_style is False
    assert o.api_base == "http://box:11434"


@pytest.mark.asyncio
async def test_embedder_lists_models_from_v1_models(monkeypatch):
    """Availability check reads OpenAI's {"data": [{"id": ...}]} shape."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://box:1234/v1/models"
        return httpx.Response(200, json={"data": [{"id": "text-embedding-nomic-embed-text-v1.5"}]})

    e = Embedder(api_base="http://box:1234", embedding_model="text-embedding-nomic-embed-text-v1.5",
                 provider="lmstudio")
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler)),
    )
    assert await e.is_available() is True


@pytest.mark.asyncio
async def test_embedder_handles_lmstudio_error_body_on_ollama_path(monkeypatch):
    """LM Studio answers /api/tags with HTTP 200 and an error body, not a model list."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "Unexpected endpoint or method. (GET /api/tags)"})

    e = Embedder(api_base="http://box:1234", embedding_model="nomic-embed-text", provider="ollama")
    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler)),
    )
    # Must not raise KeyError on the missing "models" key.
    assert await e.is_available() is False


def test_embed_sync_parses_openai_embedding_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://box:1234/v1/embeddings"
        assert json.loads(request.content)["input"] == "hello"
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    e = Embedder(api_base="http://box:1234", embedding_model="m", provider="lmstudio")
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
    assert e._embed_sync("hello") == [0.1, 0.2, 0.3]


def test_embed_sync_parses_ollama_embedding_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://box:11434/api/embeddings"
        assert json.loads(request.content)["prompt"] == "hello"
        return httpx.Response(200, json={"embedding": [0.4, 0.5]})

    e = Embedder(api_base="http://box:11434", embedding_model="m", provider="ollama")
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler)))
    assert e._embed_sync("hello") == [0.4, 0.5]
