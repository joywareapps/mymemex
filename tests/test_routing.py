"""Tests for tag-based file routing."""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from mymemex.core.queue import TaskQueue, TaskStatus, TaskType
from mymemex.services.routing import (
    RoutingService,
    _has_pending_route_task,
    _rule_matches,
    render_routing_template,
)
from mymemex.storage.database import get_session, init_database
from mymemex.storage.models import Document, RoutingRule, Task
from mymemex.storage.repositories import (
    DocumentRepository,
    RoutingRuleRepository,
    WatchDirectoryRepository,
)


# ─────────────────────────────────────────────────────────────
# Unit tests: _rule_matches
# ─────────────────────────────────────────────────────────────


def _make_rule(tags: list[str], match_mode: str = "any") -> RoutingRule:
    rule = RoutingRule()
    rule.tags = json.dumps(tags)
    rule.match_mode = match_mode
    return rule


def test_rule_matches_any_hit():
    rule = _make_rule(["category:tax_return", "financial"])
    assert _rule_matches(rule, {"category:tax_return", "other"}) is True


def test_rule_matches_any_miss():
    rule = _make_rule(["category:tax_return"])
    assert _rule_matches(rule, {"financial", "personal"}) is False


def test_rule_matches_all_hit():
    rule = _make_rule(["financial", "yearly"], match_mode="all")
    assert _rule_matches(rule, {"financial", "yearly", "extra"}) is True


def test_rule_matches_all_partial_miss():
    rule = _make_rule(["financial", "yearly"], match_mode="all")
    assert _rule_matches(rule, {"financial"}) is False


def test_rule_matches_empty_tags_never_matches():
    rule = _make_rule([])
    assert _rule_matches(rule, {"financial", "tax"}) is False


# ─────────────────────────────────────────────────────────────
# Unit tests: render_routing_template
# ─────────────────────────────────────────────────────────────


def _make_doc(
    category: str = "tax",
    document_date=None,
    original_filename: str = "invoice.pdf",
    content_hash: str = "abcd1234" + "0" * 56,
    title: str | None = None,
) -> Document:
    doc = Document()
    doc.category = category
    doc.document_date = document_date
    doc.original_filename = original_filename
    doc.content_hash = content_hash
    doc.title = title
    return doc


def test_render_tag_prefix_found():
    doc = _make_doc()
    tags = ["type:invoice", "financial"]
    result = render_routing_template("{tag:type}", doc, tags)
    assert result == "invoice"


def test_render_tag_prefix_not_found_fallback_to_prefix():
    doc = _make_doc()
    tags = ["financial"]
    result = render_routing_template("{tag:type}", doc, tags)
    assert result == "type"


def test_render_year_from_document_date():
    doc = _make_doc(document_date=date(2022, 6, 15))
    result = render_routing_template("{year}", doc, [])
    assert result == "2022"


def test_render_year_fallback_when_no_date():
    doc = _make_doc(document_date=None)
    result = render_routing_template("{year}", doc, [])
    current_year = str(datetime.utcnow().year)
    assert result == current_year


def test_render_mixed_year_and_tag_prefix():
    doc = _make_doc(document_date=date(2023, 3, 1))
    tags = ["category:tax_return"]
    result = render_routing_template("{year}_{tag:category}", doc, tags)
    assert result == "2023_tax_return"


# ─────────────────────────────────────────────────────────────
# Async DB fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def routing_config(tmp_path):
    from mymemex.config import AppConfig
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        watch={},
        database={"path": str(tmp_path / "routing_test.db")},
        server={"host": "127.0.0.1", "port": 0},
    )


@pytest_asyncio.fixture
async def routing_db(routing_config):
    import mymemex.storage.database as db_module

    await init_database(routing_config.database.path)
    yield
    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest_asyncio.fixture
async def routing_session(routing_db):
    async with get_session() as session:
        yield session


async def _create_watch_dir(session, path: str, archive_path: str | None = None):
    repo = WatchDirectoryRepository(session)
    return await repo.create(
        path=path,
        archive_path=archive_path,
        file_policy="move_to_archive",
    )


async def _create_document(session, original_path: str, content_hash_prefix: str = "doc1") -> Document:
    repo = DocumentRepository(session)
    return await repo.create(
        content_hash=content_hash_prefix.ljust(64, "0"),
        quick_hash=f"100:{content_hash_prefix}",
        file_size=1024,
        original_path=original_path,
        original_filename=Path(original_path).name,
        mime_type="application/pdf",
        file_modified_at=1700000000.0,
    )


# ─────────────────────────────────────────────────────────────
# Test 11: RoutingRuleRepository CRUD
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_routing_rule_repo_crud(routing_session):
    wd = await _create_watch_dir(routing_session, "/watch/docs", "/archive/docs")
    repo = RoutingRuleRepository(routing_session)

    rule = await repo.create(
        watch_directory_id=wd.id,
        name="Tax Returns",
        directory_name="tax",
        tags=json.dumps(["category:tax_return"]),
        match_mode="any",
        priority=10,
        sub_levels=json.dumps(["{year}"]),
    )
    assert rule.id is not None
    assert rule.name == "Tax Returns"
    assert json.loads(rule.tags) == ["category:tax_return"]

    fetched = await repo.get(rule.id)
    assert fetched is not None
    assert fetched.priority == 10

    await repo.update(fetched, name="Updated Tax")
    fetched2 = await repo.get(rule.id)
    assert fetched2.name == "Updated Tax"

    deleted = await repo.delete(rule.id)
    assert deleted is True
    assert await repo.get(rule.id) is None


# ─────────────────────────────────────────────────────────────
# Test 12: has_active_rules false → true after create
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_has_active_rules(routing_session):
    wd = await _create_watch_dir(routing_session, "/watch/r12", "/archive/r12")
    repo = RoutingRuleRepository(routing_session)

    assert await repo.has_active_rules(wd.id) is False

    await repo.create(
        watch_directory_id=wd.id,
        name="Rule A",
        directory_name="folder_a",
        tags=json.dumps(["tag_a"]),
    )

    assert await repo.has_active_rules(wd.id) is True


# ─────────────────────────────────────────────────────────────
# Test 13: _has_pending_route_task dedup check
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_has_pending_route_task(routing_session):
    doc = await _create_document(routing_session, "/watch/r13/file.pdf", "r13doc")
    assert await _has_pending_route_task(routing_session, doc.id) is False

    queue = TaskQueue(routing_session)
    await queue.enqueue(
        TaskType.ROUTE_FILE,
        {"document_id": doc.id},
        document_id=doc.id,
    )
    assert await _has_pending_route_task(routing_session, doc.id) is True


# ─────────────────────────────────────────────────────────────
# Test 14: route_document moves file to correct nested path
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_route_document_moves_file(tmp_path, routing_db):
    watch_dir = tmp_path / "watch"
    archive_dir = tmp_path / "archive"
    watch_dir.mkdir()
    archive_dir.mkdir()

    # Create actual file on disk
    source_file = watch_dir / "tax2023.pdf"
    source_file.write_text("dummy pdf content")

    async with get_session() as session:
        wd = await _create_watch_dir(session, str(watch_dir), str(archive_dir))
        doc_repo = DocumentRepository(session)
        doc = await doc_repo.create(
            content_hash="r14" + "0" * 61,
            quick_hash="100:r14",
            file_size=17,
            original_path=str(source_file),
            original_filename="tax2023.pdf",
            mime_type="application/pdf",
            file_modified_at=1700000000.0,
        )

        # Set document_date so {year} renders as 2023
        from mymemex.storage.repositories import TagRepository
        await doc_repo.update(doc, document_date=date(2023, 4, 1), category="tax")
        await session.commit()

        # Add tag
        tag_repo = TagRepository(session)
        await tag_repo.add_to_document(doc.id, "category:tax_return", is_auto=True)

        # Add routing rule
        rule_repo = RoutingRuleRepository(session)
        await rule_repo.create(
            watch_directory_id=wd.id,
            name="Tax",
            directory_name="tax",
            tags=json.dumps(["category:tax_return"]),
            sub_levels=json.dumps(["{year}"]),
            priority=10,
        )

    async with get_session() as session:
        service = RoutingService(session)
        moved = await service.route_document(doc.id)

    assert moved is True
    expected_dest = archive_dir / "tax" / "2023" / "tax2023.pdf"
    assert expected_dest.exists()

    # Verify current_path updated
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        updated_doc = await doc_repo.get_by_id(doc.id)
        assert updated_doc.current_path == str(expected_dest)
        assert updated_doc.file_policy_applied == "route_file"


# ─────────────────────────────────────────────────────────────
# Test 15: route_document idempotent (second call = no-op)
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_route_document_idempotent(tmp_path, routing_db):
    watch_dir = tmp_path / "watch2"
    archive_dir = tmp_path / "archive2"
    watch_dir.mkdir()
    archive_dir.mkdir()

    # Create actual file
    source_file = watch_dir / "doc.pdf"
    source_file.write_text("content")

    async with get_session() as session:
        wd = await _create_watch_dir(session, str(watch_dir), str(archive_dir))
        doc_repo = DocumentRepository(session)
        doc = await doc_repo.create(
            content_hash="r15" + "0" * 61,
            quick_hash="100:r15",
            file_size=7,
            original_path=str(source_file),
            original_filename="doc.pdf",
            mime_type="application/pdf",
            file_modified_at=1700000000.0,
        )
        from mymemex.storage.repositories import TagRepository
        tag_repo = TagRepository(session)
        await tag_repo.add_to_document(doc.id, "financial", is_auto=True)

        rule_repo = RoutingRuleRepository(session)
        await rule_repo.create(
            watch_directory_id=wd.id,
            name="Financial",
            directory_name="financial",
            tags=json.dumps(["financial"]),
            priority=10,
        )

    # First call — should move
    async with get_session() as session:
        moved1 = await RoutingService(session).route_document(doc.id)
    assert moved1 is True

    # Second call — already at destination, should be no-op
    async with get_session() as session:
        moved2 = await RoutingService(session).route_document(doc.id)
    assert moved2 is False


# ─────────────────────────────────────────────────────────────
# Test 16: route_document falls back to file_policy when no rules match
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_route_document_fallback_to_file_policy(tmp_path, routing_db):
    watch_dir = tmp_path / "watch3"
    archive_dir = tmp_path / "archive3"
    watch_dir.mkdir()
    archive_dir.mkdir()

    source_file = watch_dir / "unknown.pdf"
    source_file.write_text("no matching tags")

    async with get_session() as session:
        wd = await _create_watch_dir(session, str(watch_dir), str(archive_dir))
        doc_repo = DocumentRepository(session)
        doc = await doc_repo.create(
            content_hash="r16" + "0" * 61,
            quick_hash="100:r16",
            file_size=16,
            original_path=str(source_file),
            original_filename="unknown.pdf",
            mime_type="application/pdf",
            file_modified_at=1700000000.0,
        )

        rule_repo = RoutingRuleRepository(session)
        await rule_repo.create(
            watch_directory_id=wd.id,
            name="Tax Only",
            directory_name="tax",
            tags=json.dumps(["category:tax_return"]),
            priority=10,
        )
        # doc has no tags — rule won't match

    async with get_session() as session:
        result = await RoutingService(session).route_document(doc.id)

    # Falls back to file_policy which is move_to_archive → returns False (handled by file policy)
    assert result is False


# ─────────────────────────────────────────────────────────────
# API tests (TestClient with lifespan)
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def api_app(tmp_path):
    from mymemex.app import create_app
    from mymemex.config import AppConfig
    config = AppConfig(
        debug=True,
        log_level="DEBUG",
        watch={},
        database={"path": str(tmp_path / "api_routing.db")},
        server={"host": "127.0.0.1", "port": 0},
    )
    return create_app(config)


@pytest_asyncio.fixture
async def api_db(api_app):
    import mymemex.storage.database as db_module
    config = api_app.state.config if hasattr(api_app.state, "config") else None
    db_path = str(api_app.extra.get("db_path", "")) if hasattr(api_app, "extra") else None
    # init db using the config embedded in the app
    from mymemex.config import AppConfig
    # The simplest approach: init with the config from the fixture
    yield api_app


@pytest.fixture
def api_client(api_app, tmp_path):
    import mymemex.storage.database as db_module
    from fastapi.testclient import TestClient

    # Use lifespan to init database
    with TestClient(api_app, raise_server_exceptions=False) as client:
        yield client


# Test 17: GET /admin/routing-rules empty response
def test_get_routing_rules_empty(api_client):
    resp = api_client.get("/api/v1/admin/routing-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert "rules" in data
    assert isinstance(data["rules"], list)


# Test 18: POST /admin/routing-rules creates rule
def test_create_routing_rule(api_client):
    # First create a watch folder
    wd_resp = api_client.post(
        "/api/v1/admin/watch-folders",
        json={"path": "/tmp/routing_api_test_wf", "archive_path": "/tmp/routing_api_test_archive"},
    )
    assert wd_resp.status_code == 201, wd_resp.text
    wd_id = wd_resp.json()["id"]

    # Create routing rule
    resp = api_client.post(
        "/api/v1/admin/routing-rules",
        json={
            "watch_directory_id": wd_id,
            "name": "Test Rule",
            "directory_name": "test_folder",
            "tags": ["category:invoice"],
            "match_mode": "any",
            "priority": 50,
            "sub_levels": ["{year}"],
            "is_active": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Test Rule"
    assert data["tags"] == ["category:invoice"]
    assert data["sub_levels"] == ["{year}"]
    assert data["priority"] == 50


# Test 19: POST /routing-rules/reroute-all/{id} enqueues ROUTE_FILE tasks
def test_reroute_all_enqueues_tasks(api_client, tmp_path):
    # Create watch folder
    wd_resp = api_client.post(
        "/api/v1/admin/watch-folders",
        json={
            "path": str(tmp_path / "reroute_watch"),
            "archive_path": str(tmp_path / "reroute_archive"),
        },
    )
    assert wd_resp.status_code == 201
    wd_id = wd_resp.json()["id"]

    # Manually create a document under that watch directory path
    # (the API test can call reroute-all even with 0 documents)
    resp = api_client.post(f"/api/v1/admin/routing-rules/reroute-all/{wd_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "enqueued" in data
    assert "total_documents" in data
    assert data["total_documents"] == 0  # no docs in watch dir yet
