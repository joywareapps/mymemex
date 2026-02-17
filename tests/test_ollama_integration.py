"""Integration tests for Ollama embedder — requires live Ollama instance.

These tests connect to a real Ollama server and generate actual embeddings.
Run with: pytest tests/test_ollama_integration.py -v --run-integration

Set OLLAMA_API_BASE environment variable to point to your Ollama instance:
    export OLLAMA_API_BASE=http://office-pc:11434
    pytest tests/test_ollama_integration.py -v --run-integration

If Ollama is not available, these tests will be skipped.
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

from librarian.config import LLMConfig
from librarian.intelligence.embedder import Embedder


# Skip all tests in this module unless --run-integration is passed
pytestmark = pytest.mark.skipif(
    not os.environ.get("OLLAMA_API_BASE"),
    reason="Set OLLAMA_API_BASE to run integration tests (e.g., http://office-pc:11434)",
)


@pytest.fixture
def ollama_api_base():
    """Get Ollama API base URL from environment."""
    base = os.environ.get("OLLAMA_API_BASE", "http://office-pc:11434")
    return base


@pytest.fixture
def llm_config(ollama_api_base):
    """LLM config pointing at real Ollama instance."""
    return LLMConfig(
        provider="ollama",
        model="nomic-embed-text",
        api_base=ollama_api_base,
    )


@pytest_asyncio.fixture
async def embedder(llm_config):
    """Create embedder instance."""
    e = Embedder(llm_config)
    yield e
    # No close() needed - Embedder creates clients inline


# =============================================================================
# AVAILABILITY TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_ollama_is_available(embedder):
    """Ollama server should be reachable and model should be available."""
    available = await embedder.is_available()
    assert available is True, (
        "Ollama not available. Ensure:\n"
        "  1. Ollama is running on office-pc\n"
        "  2. nomic-embed-text model is pulled: ollama pull nomic-embed-text\n"
        "  3. Network connectivity from this machine to office-pc:11434"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_availability_caching(embedder):
    """Second availability check should use cached result."""
    # First call
    available1 = await embedder.is_available()
    assert available1 is True

    # Second call should be instant (cached)
    import time
    start = time.time()
    available2 = await embedder.is_available()
    elapsed = time.time() - start

    assert available2 is True
    assert elapsed < 0.01, f"Second call took {elapsed}s — should be cached"


# =============================================================================
# EMBEDDING GENERATION TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_single_text(embedder):
    """Generate embedding for a single text."""
    text = "This is a test document about machine learning and artificial intelligence."
    embedding = await embedder.embed(text)

    assert embedding is not None, "Embedding should not be None"
    assert isinstance(embedding, list), "Embedding should be a list"
    assert len(embedding) == 768, f"Expected 768 dimensions, got {len(embedding)}"
    assert all(isinstance(x, float) for x in embedding), "All values should be floats"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_dimensions_consistent(embedder):
    """All embeddings should have the same dimensions (768 for nomic-embed-text)."""
    texts = [
        "Short text",
        "This is a longer document with multiple sentences. It discusses various topics.",
        "A" * 1000,  # Long repetitive text
        "Numbers: 123 456 789",
        "Special chars: @#$%^&*()",
    ]

    embeddings = []
    for text in texts:
        emb = await embedder.embed(text)
        assert emb is not None
        assert len(emb) == 768, f"All embeddings should be 768D, got {len(emb)}"
        embeddings.append(emb)

    # Verify all same length
    assert all(len(e) == 768 for e in embeddings)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_semantic_similarity(embedder):
    """Semantically similar texts should have similar embeddings."""
    import math

    # Similar texts
    text1 = "Machine learning is a subset of artificial intelligence."
    text2 = "AI and ML are related fields of computer science."

    # Different text
    text3 = "The recipe calls for two cups of flour and one egg."

    emb1 = await embedder.embed(text1)
    emb2 = await embedder.embed(text2)
    emb3 = await embedder.embed(text3)

    assert all(e is not None for e in [emb1, emb2, emb3])

    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * y for x, y in zip(b, b)))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    sim_1_2 = cosine_similarity(emb1, emb2)  # Similar texts
    sim_1_3 = cosine_similarity(emb1, emb3)  # Different texts

    print(f"\nSimilarity (ML vs AI): {sim_1_2:.4f}")
    print(f"Similarity (ML vs recipe): {sim_1_3:.4f}")

    # Similar texts should have higher similarity
    assert sim_1_2 > sim_1_3, (
        f"Expected ML/AI texts to be more similar than ML/recipe. "
        f"Got {sim_1_2:.4f} vs {sim_1_3:.4f}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_batch(embedder):
    """Generate embeddings for multiple texts."""
    texts = [
        "First document about technology",
        "Second document about science",
        "Third document about art",
    ]

    embeddings = await embedder.embed_batch(texts)

    assert len(embeddings) == 3
    for emb in embeddings:
        assert emb is not None
        assert len(emb) == 768


@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_empty_string(embedder):
    """Empty string should return a valid embedding (or empty list is acceptable)."""
    embedding = await embedder.embed("")
    # Ollama returns empty list for empty string - that's acceptable
    if embedding is not None and len(embedding) > 0:
        assert len(embedding) == 768
    # Empty list or None is also acceptable for empty input


@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_unicode(embedder):
    """Embedding should handle Unicode text."""
    texts = [
        "Привет мир",  # Russian
        "你好世界",    # Chinese
        "مرحبا بالعالم",  # Arabic
        "🎉🔥💯",      # Emojis
    ]

    for text in texts:
        emb = await embedder.embed(text)
        assert emb is not None, f"Failed to embed: {text}"
        assert len(emb) == 768


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_latency(embedder):
    """Single embedding should complete in reasonable time."""
    import time

    text = "Performance test for embedding generation latency."

    # Warm up
    await embedder.embed(text)

    # Measure
    start = time.time()
    embedding = await embedder.embed(text)
    elapsed = time.time() - start

    assert embedding is not None
    print(f"\nEmbedding latency: {elapsed*1000:.1f}ms")

    # Should be under 500ms for a single embedding
    assert elapsed < 0.5, f"Embedding took {elapsed}s — expected < 0.5s"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_embed_batch_throughput(embedder):
    """Batch embedding throughput test."""
    import time

    texts = [f"Document number {i} for batch testing" for i in range(10)]

    start = time.time()
    embeddings = await embedder.embed_batch(texts)
    elapsed = time.time() - start

    assert all(e is not None for e in embeddings)
    print(f"\nBatch (10 texts) latency: {elapsed*1000:.1f}ms ({elapsed*100:.1f}ms per text)")

    # Should be under 5 seconds for 10 embeddings
    assert elapsed < 5.0
