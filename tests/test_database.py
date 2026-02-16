"""Tests for database initialization and repositories."""

from __future__ import annotations

import pytest

from librarian.storage.models import Document, Chunk, Tag
from librarian.storage.repositories import ChunkRepository, DocumentRepository, TagRepository


@pytest.mark.asyncio
async def test_init_database(db_session):
    """Database should initialize with all tables."""
    # If we got a session, init_database succeeded
    assert db_session is not None


@pytest.mark.asyncio
async def test_create_document(db_session):
    """Should create a document and file path."""
    repo = DocumentRepository(db_session)
    doc = await repo.create(
        content_hash="a" * 64,
        quick_hash="100:abcdef1234567890",
        file_size=1024,
        original_path="/tmp/test.pdf",
        original_filename="test.pdf",
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )
    assert doc.id is not None
    assert doc.content_hash == "a" * 64
    assert doc.status == "pending"
    assert doc.original_filename == "test.pdf"


@pytest.mark.asyncio
async def test_find_by_content_hash(db_session):
    """Should find document by content hash."""
    repo = DocumentRepository(db_session)
    doc = await repo.create(
        content_hash="b" * 64,
        quick_hash="200:1234567890abcdef",
        file_size=2048,
        original_path="/tmp/test2.pdf",
        original_filename="test2.pdf",
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )

    found = await repo.find_by_content_hash("b" * 64)
    assert found is not None
    assert found.id == doc.id


@pytest.mark.asyncio
async def test_find_by_content_hash_not_found(db_session):
    """Should return None for unknown hash."""
    repo = DocumentRepository(db_session)
    found = await repo.find_by_content_hash("z" * 64)
    assert found is None


@pytest.mark.asyncio
async def test_update_document_status(db_session):
    """Should update document status."""
    repo = DocumentRepository(db_session)
    doc = await repo.create(
        content_hash="c" * 64,
        quick_hash="300:fedcba0987654321",
        file_size=512,
        original_path="/tmp/test3.pdf",
        original_filename="test3.pdf",
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )

    await repo.update_status(doc, "processing")
    assert doc.status == "processing"

    await repo.update_status(doc, "failed", error="Something broke")
    assert doc.status == "failed"
    assert doc.last_error == "Something broke"
    assert doc.error_count == 1


@pytest.mark.asyncio
async def test_create_chunks_and_search(db_session):
    """Should create chunks and find them via FTS5."""
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)

    doc = await doc_repo.create(
        content_hash="d" * 64,
        quick_hash="400:0000000000000000",
        file_size=4096,
        original_path="/tmp/search_test.pdf",
        original_filename="search_test.pdf",
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )

    await chunk_repo.create(
        document_id=doc.id,
        chunk_index=0,
        text="The quick brown fox jumps over the lazy dog",
        char_count=43,
        page_number=0,
        extraction_method="pymupdf_native",
    )
    await chunk_repo.create(
        document_id=doc.id,
        chunk_index=1,
        text="Insurance policy coverage for automobile accidents and liability",
        char_count=65,
        page_number=1,
        extraction_method="pymupdf_native",
    )
    await db_session.commit()

    # FTS5 search
    results, total = await chunk_repo.fulltext_search("insurance")
    assert total >= 1
    assert any("insurance" in r["text"].lower() for r in results)

    # Search for different term
    results2, total2 = await chunk_repo.fulltext_search("fox")
    assert total2 >= 1
    assert any("fox" in r["text"].lower() for r in results2)


@pytest.mark.asyncio
async def test_tag_operations(db_session):
    """Should create, add, and remove tags."""
    doc_repo = DocumentRepository(db_session)
    tag_repo = TagRepository(db_session)

    doc = await doc_repo.create(
        content_hash="e" * 64,
        quick_hash="500:1111111111111111",
        file_size=1000,
        original_path="/tmp/tagged.pdf",
        original_filename="tagged.pdf",
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )

    # Create and add tag
    await tag_repo.add_to_document(doc.id, "important")
    tags = await tag_repo.get_document_tags(doc.id)
    assert "important" in tags

    # Add another tag
    await tag_repo.add_to_document(doc.id, "finance")
    tags = await tag_repo.get_document_tags(doc.id)
    assert len(tags) == 2

    # Remove tag
    removed = await tag_repo.remove_from_document(doc.id, "important")
    assert removed is True
    tags = await tag_repo.get_document_tags(doc.id)
    assert "important" not in tags
    assert "finance" in tags


@pytest.mark.asyncio
async def test_list_tags_with_counts(db_session):
    """list_with_counts should include document counts."""
    tag_repo = TagRepository(db_session)
    tags = await tag_repo.list_with_counts()
    assert isinstance(tags, list)
    for t in tags:
        assert "name" in t
        assert "document_count" in t


@pytest.mark.asyncio
async def test_document_delete(db_session):
    """Should delete document and cascade."""
    repo = DocumentRepository(db_session)

    doc = await repo.create(
        content_hash="f" * 64,
        quick_hash="600:2222222222222222",
        file_size=500,
        original_path="/tmp/delete_me.pdf",
        original_filename="delete_me.pdf",
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )

    deleted = await repo.delete(doc.id)
    assert deleted is True

    found = await repo.get_by_id(doc.id)
    assert found is None
