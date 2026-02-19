"""Tests for ChromaDB vector store."""

from __future__ import annotations

import pytest

from mymemex.config import DatabaseConfig
from mymemex.storage.vector_store import CHROMADB_AVAILABLE, VectorStore


@pytest.fixture
def db_config(tmp_path):
    """DatabaseConfig with a temp path so ChromaDB persists to tmp."""
    return DatabaseConfig(path=str(tmp_path / "test.db"))


@pytest.fixture
def vector_store(db_config):
    if not CHROMADB_AVAILABLE:
        pytest.skip("chromadb not installed")
    return VectorStore(db_config)


def test_chromadb_available():
    """ChromaDB import flag should be True (installed in dev deps)."""
    assert CHROMADB_AVAILABLE is True


def test_vector_store_init(vector_store):
    """VectorStore initializes with zero count."""
    assert vector_store.count() == 0


def test_add_and_count(vector_store):
    """Adding a vector increments the count."""
    vector_id = vector_store.add(
        chunk_id=1,
        document_id=1,
        text="Test document about insurance policies",
        embedding=[0.1] * 768,
    )
    assert isinstance(vector_id, str)
    assert len(vector_id) == 36  # UUID
    assert vector_store.count() == 1


def test_search(vector_store):
    """Search returns relevant results sorted by distance."""
    # Add a few vectors
    vector_store.add(
        chunk_id=1, document_id=1,
        text="Insurance policy document",
        embedding=[0.1] * 768,
    )
    vector_store.add(
        chunk_id=2, document_id=1,
        text="Car maintenance guide",
        embedding=[0.9] * 768,
    )
    vector_store.add(
        chunk_id=3, document_id=2,
        text="Health coverage details",
        embedding=[0.15] * 768,
    )

    # Query with a vector close to chunk 1 and 3
    results = vector_store.search(
        query_embedding=[0.12] * 768,
        n_results=2,
    )

    assert len(results) == 2
    for r in results:
        assert "chunk_id" in r
        assert "document_id" in r
        assert "text" in r
        assert "distance" in r
        assert isinstance(r["distance"], float)


def test_search_with_where_filter(vector_store):
    """Search can filter by metadata."""
    vector_store.add(
        chunk_id=10, document_id=1,
        text="Doc one", embedding=[0.1] * 768,
    )
    vector_store.add(
        chunk_id=20, document_id=2,
        text="Doc two", embedding=[0.2] * 768,
    )

    results = vector_store.search(
        query_embedding=[0.15] * 768,
        n_results=10,
        where={"document_id": 2},
    )

    assert len(results) == 1
    assert results[0]["document_id"] == 2


def test_delete_by_document(vector_store):
    """delete_by_document removes all vectors for that document."""
    vector_store.add(
        chunk_id=1, document_id=100,
        text="First", embedding=[0.1] * 768,
    )
    vector_store.add(
        chunk_id=2, document_id=100,
        text="Second", embedding=[0.2] * 768,
    )
    vector_store.add(
        chunk_id=3, document_id=200,
        text="Other doc", embedding=[0.3] * 768,
    )

    assert vector_store.count() == 3

    vector_store.delete_by_document(100)

    assert vector_store.count() == 1
    results = vector_store.search(query_embedding=[0.1] * 768, n_results=10)
    assert len(results) == 1
    assert results[0]["document_id"] == 200


def test_search_empty_store(vector_store):
    """Searching an empty store returns no results."""
    results = vector_store.search(
        query_embedding=[0.1] * 768,
        n_results=5,
    )
    assert results == []
