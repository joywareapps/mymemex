"""Tests for MCP server — tools, resources, and prompts."""

from __future__ import annotations

import base64
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from librarian.config import AppConfig
from librarian.mcp.server import create_mcp_server
from librarian.storage.database import get_session, init_database


# --- Fixtures ---


@pytest.fixture
def mcp_config(tmp_path):
    """Config for MCP tests with temp directories."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        watch={"directories": [str(watch_dir)]},
        database={"path": str(tmp_path / "test.db")},
        mcp={"security": {"allowed_parent_paths": [str(tmp_path)], "max_upload_size_mb": 1}},
    )


@pytest.fixture
def mcp_server(mcp_config):
    """Create MCP server instance."""
    return create_mcp_server(mcp_config)


@pytest_asyncio.fixture
async def db_ready(mcp_config):
    """Initialize database for MCP tests."""
    import librarian.storage.database as db_module

    await init_database(mcp_config.database.path)
    yield
    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest_asyncio.fixture
async def seeded_db(db_ready, mcp_config):
    """Seed database with test documents and chunks."""
    async with get_session() as session:
        from librarian.storage.repositories import ChunkRepository, DocumentRepository, TagRepository

        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        tag_repo = TagRepository(session)

        doc = await doc_repo.create(
            content_hash="abc123",
            quick_hash="qh123",
            file_size=1024,
            original_path="/test/sample.pdf",
            original_filename="sample.pdf",
            mime_type="application/pdf",
            file_modified_at=1700000000.0,
        )

        await chunk_repo.create(
            document_id=doc.id,
            chunk_index=0,
            text="Insurance policy coverage details for the year 2024.",
            char_count=51,
            page_number=1,
            extraction_method="native",
        )
        await chunk_repo.create(
            document_id=doc.id,
            chunk_index=1,
            text="Premium payment schedule and deductible information.",
            char_count=52,
            page_number=2,
            extraction_method="native",
        )
        await session.commit()

        await tag_repo.add_to_document(doc.id, "insurance")
        await tag_repo.add_to_document(doc.id, "policy")

    return doc.id


# --- MCP Server Creation ---


def test_create_mcp_server(mcp_server):
    """MCP server should be created with correct name."""
    assert mcp_server.name == "librarian"


# --- Tool: search_documents ---


@pytest.mark.asyncio
async def test_search_keyword(seeded_db, mcp_config):
    """Keyword search should return formatted results."""
    async with get_session() as session:
        from librarian.services.search import SearchService

        service = SearchService(session, mcp_config)
        results, total = await service.keyword_search("insurance")
        assert total >= 1
        assert any("insurance" in r["text"].lower() for r in results)


# --- Tool: get_document ---


@pytest.mark.asyncio
async def test_get_document_service(seeded_db):
    """get_document service method should return full details."""
    async with get_session() as session:
        from librarian.services.document import DocumentService

        service = DocumentService(session)
        data = await service.get_document(seeded_db)

        assert data["id"] == seeded_db
        assert data["original_filename"] == "sample.pdf"
        assert len(data["chunks"]) == 2
        assert "insurance" in data["tags"]


@pytest.mark.asyncio
async def test_get_document_not_found(seeded_db):
    """get_document should raise NotFoundError for invalid ID."""
    from librarian.services import NotFoundError
    from librarian.services.document import DocumentService

    async with get_session() as session:
        service = DocumentService(session)
        with pytest.raises(NotFoundError):
            await service.get_document(99999)


# --- Tool: get_document_text ---


@pytest.mark.asyncio
async def test_get_document_text_all_pages(seeded_db):
    """get_document_text should return all pages when no range specified."""
    async with get_session() as session:
        from librarian.services.document import DocumentService

        service = DocumentService(session)
        data = await service.get_document_text(seeded_db)

        assert data["document_id"] == seeded_db
        assert data["total_pages"] == 2
        assert data["page_start"] == 1
        assert data["page_end"] == 2
        assert len(data["pages"]) == 2
        assert "Insurance" in data["text"]
        assert "Premium" in data["text"]


@pytest.mark.asyncio
async def test_get_document_text_page_range(seeded_db):
    """get_document_text should filter by page range."""
    async with get_session() as session:
        from librarian.services.document import DocumentService

        service = DocumentService(session)
        data = await service.get_document_text(seeded_db, page_start=2, page_end=2)

        assert len(data["pages"]) == 1
        assert "Premium" in data["text"]
        assert "Insurance" not in data["text"]


@pytest.mark.asyncio
async def test_get_document_text_not_found(seeded_db):
    """get_document_text should raise NotFoundError for invalid ID."""
    from librarian.services import NotFoundError
    from librarian.services.document import DocumentService

    async with get_session() as session:
        service = DocumentService(session)
        with pytest.raises(NotFoundError):
            await service.get_document_text(99999)


# --- Tool: list_documents ---


@pytest.mark.asyncio
async def test_list_documents(seeded_db):
    """list_documents should return paginated results."""
    async with get_session() as session:
        from librarian.services.document import DocumentService

        service = DocumentService(session)
        items, total = await service.list_documents(page=1, per_page=50)

        assert total >= 1
        assert len(items) >= 1
        assert items[0]["original_filename"] == "sample.pdf"


# --- Tool: add_tag / remove_tag ---


@pytest.mark.asyncio
async def test_add_tag_to_document(seeded_db):
    """add_tag_to_document should add a new tag."""
    async with get_session() as session:
        from librarian.services.tag import TagService

        service = TagService(session)
        result = await service.add_tag_to_document(seeded_db, "financial")

        assert result["document_id"] == seeded_db
        assert result["tag"] == "financial"
        assert result["is_new"] is True


@pytest.mark.asyncio
async def test_add_existing_tag(seeded_db):
    """add_tag_to_document with existing tag should report is_new=False."""
    async with get_session() as session:
        from librarian.services.tag import TagService

        service = TagService(session)
        result = await service.add_tag_to_document(seeded_db, "insurance")

        assert result["is_new"] is False


@pytest.mark.asyncio
async def test_remove_tag_from_document(seeded_db):
    """remove_tag_from_document should remove tag."""
    async with get_session() as session:
        from librarian.services.tag import TagService

        service = TagService(session)
        result = await service.remove_tag_from_document(seeded_db, "policy")

        assert result["document_id"] == seeded_db
        assert result["tag"] == "policy"


@pytest.mark.asyncio
async def test_remove_nonexistent_tag(seeded_db):
    """remove_tag_from_document should raise NotFoundError for missing tag."""
    from librarian.services import NotFoundError
    from librarian.services.tag import TagService

    async with get_session() as session:
        service = TagService(session)
        with pytest.raises(NotFoundError):
            await service.remove_tag_from_document(seeded_db, "nonexistent")


@pytest.mark.asyncio
async def test_add_tag_invalid_document(seeded_db):
    """add_tag_to_document should raise NotFoundError for invalid doc ID."""
    from librarian.services import NotFoundError
    from librarian.services.tag import TagService

    async with get_session() as session:
        service = TagService(session)
        with pytest.raises(NotFoundError):
            await service.add_tag_to_document(99999, "test")


# --- Tool: upload_document ---


@pytest.mark.asyncio
async def test_upload_from_path(seeded_db, mcp_config, tmp_path):
    """upload_from_path should copy file to inbox."""
    # Create a test file
    test_file = tmp_path / "test_upload.pdf"
    test_file.write_bytes(b"%PDF-1.4 test content")

    async with get_session() as session:
        from librarian.services.ingest import IngestService

        service = IngestService(session, mcp_config)

        with patch("librarian.services.ingest.handle_new_file", new_callable=AsyncMock):
            result = await service.upload_from_path(
                str(test_file), "uploaded.pdf", allowed_paths=[str(tmp_path)]
            )

        assert result["filename"] == "uploaded.pdf"
        assert "inbox_path" in result
        assert result["size"] > 0
        assert Path(result["inbox_path"]).exists()


@pytest.mark.asyncio
async def test_upload_from_path_rejected(seeded_db, mcp_config, tmp_path):
    """upload_from_path should reject paths outside allowed boundaries."""
    from librarian.services import ServiceError
    from librarian.services.ingest import IngestService

    test_file = tmp_path / "secret.pdf"
    test_file.write_bytes(b"%PDF-1.4 secret")

    async with get_session() as session:
        service = IngestService(session, mcp_config)
        with pytest.raises(ServiceError, match="not allowed"):
            await service.upload_from_path(
                str(test_file), "secret.pdf", allowed_paths=["/some/other/path"]
            )


@pytest.mark.asyncio
async def test_upload_base64(seeded_db, mcp_config):
    """upload via base64 content should work for small files."""
    content = b"%PDF-1.4 test base64 upload"
    b64 = base64.b64encode(content).decode()

    async with get_session() as session:
        from librarian.services.ingest import IngestService

        service = IngestService(session, mcp_config)
        with patch("librarian.services.ingest.handle_new_file", new_callable=AsyncMock):
            result = await service.upload(content, "b64test.pdf")

        assert result["path"].endswith("b64test.pdf")
        assert result["size"] == len(content)


# --- Tool: get_library_stats ---


@pytest.mark.asyncio
async def test_get_library_stats(seeded_db, mcp_config):
    """get_library_stats should return aggregate statistics."""
    async with get_session() as session:
        from librarian.services.stats import StatsService

        service = StatsService(session, mcp_config)
        stats = await service.get_library_stats()

        assert stats["doc_stats"]["total"] >= 1
        assert stats["total_chunks"] >= 2
        assert "queue_stats" in stats
        assert "sqlite_size_mb" in stats


# --- Resources ---


@pytest.mark.asyncio
async def test_tags_resource(seeded_db):
    """Tags resource should return tag list."""
    import json

    async with get_session() as session:
        from librarian.services.tag import TagService

        service = TagService(session)
        tags = await service.list_tags()

    assert len(tags) >= 2
    names = [t["name"] for t in tags]
    assert "insurance" in names
    assert "policy" in names


@pytest.mark.asyncio
async def test_stats_resource(seeded_db, mcp_config):
    """Stats resource should return library stats."""
    async with get_session() as session:
        from librarian.services.stats import StatsService

        service = StatsService(session, mcp_config)
        stats = await service.get_library_stats()

    assert stats["doc_stats"]["total"] >= 1


# --- Prompts ---


@pytest.mark.asyncio
async def test_search_and_summarize_prompt():
    """search_and_summarize prompt should return formatted message."""
    from librarian.mcp.prompts import register
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    register(mcp)

    # Verify the prompt is registered by getting it
    prompt = await mcp.get_prompt("search_and_summarize", {"query": "insurance policies"})
    assert len(prompt.messages) == 1
    assert "insurance policies" in prompt.messages[0].content.text


@pytest.mark.asyncio
async def test_compare_documents_prompt():
    """compare_documents prompt should include document IDs."""
    from librarian.mcp.prompts import register
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("test")
    register(mcp)

    prompt = await mcp.get_prompt("compare_documents", {"document_ids": "1, 2, 3"})
    assert len(prompt.messages) == 1
    assert "1, 2, 3" in prompt.messages[0].content.text


# --- Formatting helpers ---


def test_format_keyword_results():
    """Keyword results formatting should produce readable output."""
    from librarian.mcp.tools import _format_keyword_results

    results = [
        {
            "document_id": 1,
            "title": "Insurance Doc",
            "original_filename": "ins.pdf",
            "page_number": 1,
            "snippet": "Found <mark>insurance</mark> policy...",
            "text": "Full text here",
            "rank": -1.5,
            "tags": ["insurance"],
            "category": None,
        }
    ]
    output = _format_keyword_results(results, 1, "insurance", "keyword")
    assert "Insurance Doc" in output
    assert "ID: 1" in output
    assert "insurance" in output


def test_format_document():
    """Document formatting should include metadata and chunks."""
    from librarian.mcp.tools import _format_document

    data = {
        "id": 1,
        "content_hash": "abc",
        "title": "Test Document",
        "original_filename": "test.pdf",
        "original_path": "/test/test.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024,
        "page_count": 2,
        "status": "processed",
        "category": "legal",
        "tags": ["insurance", "policy"],
        "ingested_at": "2024-01-15T10:30:00",
        "chunks": [
            {"page_number": 1, "text": "Page 1 text content"},
            {"page_number": 2, "text": "Page 2 text content"},
        ],
    }
    output = _format_document(data)
    assert "# Test Document" in output
    assert "ID:** 1" in output
    assert "Page 1 text content" in output
    assert "insurance, policy" in output


def test_format_stats():
    """Stats formatting should produce readable output."""
    from librarian.mcp.tools import _format_stats

    stats = {
        "doc_stats": {"total": 42, "by_status": {"processed": 38, "pending": 2, "error": 2}},
        "total_chunks": 500,
        "sqlite_size_mb": 12.5,
        "queue_stats": {"pending": 0, "running": 0},
    }
    output = _format_stats(stats)
    assert "Total: 42" in output
    assert "Processed: 38" in output
    assert "12.5 MB" in output
    assert "Total: 500" in output


# --- MCP Config ---


def test_mcp_config_defaults():
    """MCPConfig should have sensible defaults."""
    config = AppConfig()
    assert config.mcp.enabled is True
    assert config.mcp.security.max_upload_size_mb == 5
    assert config.mcp.security.allowed_parent_paths == []
