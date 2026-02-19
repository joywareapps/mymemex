"""Tests for Web UI routes."""

from __future__ import annotations

import pytest
import pytest_asyncio

from fastapi.testclient import TestClient

from mymemex.app import create_app
from mymemex.config import AppConfig
from mymemex.storage.database import get_session, init_database


# --- Fixtures ---


@pytest.fixture
def web_config(tmp_path):
    """Config for web tests with temp directories."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        watch={},
        database={"path": str(tmp_path / "test.db")},
        server={"host": "127.0.0.1", "port": 0},
    )


@pytest_asyncio.fixture
async def web_db(web_config):
    """Initialize database for web tests."""
    import mymemex.storage.database as db_module

    await init_database(web_config.database.path)
    yield
    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest_asyncio.fixture
async def seeded_web_db(web_db):
    """Seed database with test data for web tests."""
    async with get_session() as session:
        from mymemex.storage.repositories import (
            ChunkRepository,
            DocumentRepository,
            TagRepository,
        )

        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        tag_repo = TagRepository(session)

        doc = await doc_repo.create(
            content_hash="webhash123",
            quick_hash="webqh123",
            file_size=2048,
            original_path="/test/web-test.pdf",
            original_filename="web-test.pdf",
            mime_type="application/pdf",
            file_modified_at=1700000000.0,
        )

        await chunk_repo.create(
            document_id=doc.id,
            chunk_index=0,
            text="Insurance policy coverage details for web testing.",
            char_count=50,
            page_number=1,
            extraction_method="native",
        )
        await session.commit()

        await tag_repo.add_to_document(doc.id, "test-tag")

    return doc.id


@pytest.fixture
def web_client(web_config, seeded_web_db):
    """TestClient with initialized + seeded database."""
    app = create_app(web_config)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def empty_client(web_config, web_db):
    """TestClient with initialized but empty database."""
    app = create_app(web_config)
    return TestClient(app, raise_server_exceptions=False)


# --- Document List ---


def test_document_list_returns_html(web_client):
    """GET /ui/ returns 200 with HTML content."""
    resp = web_client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Documents" in resp.text


def test_document_list_shows_documents(web_client):
    """Document list includes seeded document."""
    resp = web_client.get("/ui/")
    assert resp.status_code == 200
    assert "web-test.pdf" in resp.text


def test_document_list_empty_state(empty_client):
    """Empty document list shows empty state message."""
    resp = empty_client.get("/ui/")
    assert resp.status_code == 200
    assert "No documents yet" in resp.text


# --- Document Detail ---


def test_document_detail_valid(web_client, seeded_web_db):
    """GET /ui/document/{id} returns 200 for valid document."""
    doc_id = seeded_web_db
    resp = web_client.get(f"/ui/document/{doc_id}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "web-test.pdf" in resp.text


def test_document_detail_shows_chunks(web_client, seeded_web_db):
    """Document detail page shows chunk content."""
    doc_id = seeded_web_db
    resp = web_client.get(f"/ui/document/{doc_id}")
    assert "Insurance policy coverage" in resp.text


def test_document_detail_shows_tags(web_client, seeded_web_db):
    """Document detail page shows tags."""
    doc_id = seeded_web_db
    resp = web_client.get(f"/ui/document/{doc_id}")
    assert "test-tag" in resp.text


def test_document_detail_not_found(web_client):
    """GET /ui/document/{id} returns 404 for invalid ID."""
    resp = web_client.get("/ui/document/99999")
    assert resp.status_code == 404


# --- Search ---


def test_search_page_no_query(web_client):
    """GET /ui/search without query returns empty form."""
    resp = web_client.get("/ui/search")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Search your documents" in resp.text


def test_search_with_query(web_client):
    """GET /ui/search?q=insurance returns results."""
    resp = web_client.get("/ui/search?q=insurance")
    assert resp.status_code == 200
    assert "insurance" in resp.text.lower()


def test_search_no_results(web_client):
    """Search with no matching query shows no results message."""
    resp = web_client.get("/ui/search?q=xyznonexistent")
    assert resp.status_code == 200
    assert "No results found" in resp.text


# --- Tags ---


def test_tags_page(web_client):
    """GET /ui/tags returns 200 with tag data."""
    resp = web_client.get("/ui/tags")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "test-tag" in resp.text


def test_tags_page_empty(empty_client):
    """Tags page with no tags shows empty state."""
    resp = empty_client.get("/ui/tags")
    assert resp.status_code == 200
    assert "No tags yet" in resp.text


# --- Upload ---


def test_upload_page(web_client):
    """GET /ui/upload returns 200 with upload form."""
    resp = web_client.get("/ui/upload")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Upload" in resp.text


# --- Static Files ---


def test_static_css(web_client):
    """Static CSS file is served."""
    resp = web_client.get("/ui/static/css/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]


def test_static_htmx(web_client):
    """HTMX JS file is served."""
    resp = web_client.get("/ui/static/js/htmx.min.js")
    assert resp.status_code == 200
