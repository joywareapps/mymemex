"""End-to-end integration tests for semantic search pipeline.

Tests the full flow:
    Text → Embedder → Vector Store → Search → Results

Run with:
    export OLLAMA_API_BASE=http://office-pc:11434
    pytest tests/test_semantic_search_e2e.py -v --run-integration
"""

from __future__ import annotations

import os
import math
import pytest
import pytest_asyncio

from mymemex.config import LLMConfig, DatabaseConfig
from mymemex.intelligence.embedder import Embedder
from mymemex.storage.vector_store import VectorStore


pytestmark = pytest.mark.skipif(
    not os.environ.get("OLLAMA_API_BASE"),
    reason="Set OLLAMA_API_BASE to run integration tests",
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@pytest.fixture
def ollama_api_base():
    return os.environ.get("OLLAMA_API_BASE", "http://office-pc:11434")


@pytest.fixture
def llm_config(ollama_api_base):
    return LLMConfig(
        provider="ollama",
        model="nomic-embed-text",
        api_base=ollama_api_base,
    )


@pytest.fixture
def db_config(tmp_path):
    return DatabaseConfig(path=str(tmp_path / "test.db"))


@pytest_asyncio.fixture
async def embedder(llm_config):
    e = Embedder(llm_config)
    yield e
    # No close() needed - Embedder creates clients inline


@pytest.fixture
def vector_store(db_config):
    return VectorStore(db_config)


# =============================================================================
# E2E TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_index_and_search(embedder, vector_store):
    """Full flow: embed documents, store vectors, search, verify results."""

    # Skip if Ollama unavailable
    if not await embedder.is_available():
        pytest.skip("Ollama not available")

    # Test documents covering different topics
    documents = [
        (1, 1, "Python is a popular programming language for machine learning and data science."),
        (2, 1, "JavaScript is widely used for web development and frontend applications."),
        (3, 2, "Neural networks are inspired by biological neurons in the human brain."),
        (4, 2, "Deep learning models can achieve superhuman performance on specific tasks."),
        (5, 3, "The chef prepared a delicious meal with fresh ingredients from the market."),
        (6, 3, "Baking requires precise measurements and temperature control."),
    ]

    # Embed and index all documents
    print("\nIndexing documents...")
    for chunk_id, doc_id, text in documents:
        embedding = await embedder.embed(text)
        assert embedding is not None, f"Failed to embed: {text}"

        vector_store.add(
            chunk_id=chunk_id,
            document_id=doc_id,
            text=text,
            embedding=embedding,
            metadata={"topic": "programming" if doc_id == 1 else "AI" if doc_id == 2 else "cooking"},
        )

    assert vector_store.count() == 6
    print(f"Indexed {vector_store.count()} documents")

    # Search for ML/AI related content
    query = "artificial intelligence and deep learning"
    query_embedding = await embedder.embed(query)
    assert query_embedding is not None

    results = vector_store.search(query_embedding, n_results=3)

    print(f"\nQuery: '{query}'")
    print("Top 3 results:")
    for i, r in enumerate(results):
        print(f"  {i+1}. [chunk {r['chunk_id']}] {r['text'][:60]}... (dist: {r['distance']:.4f})")

    # Results should prioritize AI/neural network documents (chunks 3, 4)
    top_chunk_ids = [r["chunk_id"] for r in results]
    assert 3 in top_chunk_ids or 4 in top_chunk_ids, (
        f"Expected AI-related chunks (3, 4) in top results, got {top_chunk_ids}"
    )

    # Cooking documents (5, 6) should NOT be in top results
    assert 5 not in top_chunk_ids and 6 not in top_chunk_ids, (
        f"Cooking chunks (5, 6) should not appear in AI query results"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_metadata_filtering(embedder, vector_store):
    """Search with metadata filters."""

    if not await embedder.is_available():
        pytest.skip("Ollama not available")

    # Index documents with topic metadata
    documents = [
        (1, 1, "Python tutorial for beginners", {"topic": "programming", "level": "beginner"}),
        (2, 1, "Advanced Python decorators", {"topic": "programming", "level": "advanced"}),
        (3, 2, "Introduction to French cooking", {"topic": "cooking", "level": "beginner"}),
        (4, 2, "Sous vide techniques", {"topic": "cooking", "level": "advanced"}),
    ]

    for chunk_id, doc_id, text, metadata in documents:
        embedding = await embedder.embed(text)
        vector_store.add(chunk_id, doc_id, text, embedding, metadata)

    # Search for "beginner" content, filter by topic=programming
    query = "beginner tutorial"
    query_embedding = await embedder.embed(query)

    results = vector_store.search(
        query_embedding,
        n_results=10,
        where={"topic": "programming"},
    )

    # Should only return programming documents
    for r in results:
        assert r["document_id"] == 1, f"Expected only programming docs, got doc {r['document_id']}"

    print(f"\nFiltered search returned {len(results)} programming documents")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_document_deletion(embedder, vector_store):
    """Delete document and verify vectors are removed."""

    if not await embedder.is_available():
        pytest.skip("Ollama not available")

    # Index documents
    for i in range(1, 4):
        text = f"Document number {i} with some unique content."
        embedding = await embedder.embed(text)
        vector_store.add(i, 100, text, embedding)

    assert vector_store.count() == 3

    # Delete document 100
    vector_store.delete_by_document(100)

    assert vector_store.count() == 0

    # Search should return empty
    query_embedding = await embedder.embed("document")
    results = vector_store.search(query_embedding, n_results=10)
    assert results == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_semantic_vs_keyword(embedder, vector_store):
    """Demonstrate semantic understanding vs keyword matching."""

    if not await embedder.is_available():
        pytest.skip("Ollama not available")

    # Documents that DON'T contain the word "canine" but are about dogs
    documents = [
        (1, 1, "Dogs are loyal pets that love to play fetch."),
        (2, 1, "Puppies need training and socialization."),
        (3, 2, "Cats are independent animals that sleep a lot."),
        (4, 2, "Fish require clean water and proper feeding."),
    ]

    for chunk_id, doc_id, text in documents:
        embedding = await embedder.embed(text)
        vector_store.add(chunk_id, doc_id, text, embedding)

    # Search with word "canine" (not in any document)
    query = "canine behavior and training"
    query_embedding = await embedder.embed(query)

    results = vector_store.search(query_embedding, n_results=2)

    print(f"\nQuery: '{query}' (word 'canine' not in any document)")
    print("Results:")
    for r in results:
        print(f"  - {r['text']}")

    # Should return dog-related documents despite no keyword match
    top_ids = [r["chunk_id"] for r in results]
    assert 1 in top_ids or 2 in top_ids, (
        f"Expected dog documents (1, 2) for 'canine' query, got {top_ids}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_similarity_scoring(embedder, vector_store):
    """Verify distance scores are reasonable."""

    if not await embedder.is_available():
        pytest.skip("Ollama not available")

    # Identical text should have distance near 0
    text = "This is a unique test sentence."
    emb = await embedder.embed(text)

    vector_store.add(1, 1, text, emb)

    # Search with exact same embedding
    results = vector_store.search(emb, n_results=1)

    assert len(results) == 1
    distance = results[0]["distance"]

    print(f"\nIdentical text distance: {distance:.6f}")
    # Cosine distance should be very small (near 0) for identical vectors
    assert distance < 0.01, f"Expected distance < 0.01 for identical text, got {distance}"
