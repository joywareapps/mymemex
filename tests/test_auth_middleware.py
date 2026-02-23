"""Tests for AuthMiddleware — auth enforcement on protected paths."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from mymemex.config import AppConfig, AuthConfig
from mymemex.services.auth import AuthService
from mymemex.storage.database import get_session, init_database
from mymemex.storage.repositories import UserRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def disabled_app():
    """App with auth.enabled=False (default)."""
    from mymemex.app import create_app

    config = AppConfig(auth=AuthConfig(enabled=False))
    app = create_app(config)
    yield app


@pytest_asyncio.fixture
async def enabled_app(tmp_path):
    """App with auth.enabled=True and a test user."""
    import mymemex.storage.database as db_module

    db_path = tmp_path / "test_middleware.db"
    await init_database(db_path)

    async with get_session() as session:
        repo = UserRepository(session)
        pw_hash = AuthService.hash_password("pw123")
        await repo.create(name="Alice", password_hash=pw_hash, is_admin=True)

    from mymemex.app import create_app

    config = AppConfig(
        auth=AuthConfig(enabled=True, jwt_secret_key="test-secret-xyz", session_expiry_hours=1),
    )
    config.database.path = db_path
    app = create_app(config)

    yield app

    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


def _login(client: TestClient, name: str = "Alice", password: str = "pw123") -> str:
    """Helper: log in and return the JWT access token."""
    resp = client.post("/api/v1/auth/login", json={"name": name, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests: auth disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_disabled_admin_api_passes(disabled_app):
    """Auth disabled → admin API requests pass without any token."""
    with TestClient(disabled_app) as client:
        resp = client.get("/api/v1/admin/setup/status")
    # Not 401 — may be 200 or any non-401/302
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_auth_disabled_write_passes(disabled_app):
    """Auth disabled → POST to documents is not blocked by middleware (may fail for other reasons)."""
    with TestClient(disabled_app) as client:
        resp = client.post("/api/v1/documents/upload")
    # Middleware should not return 401 — the route itself may return 422 (missing body) or similar
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Tests: auth enabled, no token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_enabled_admin_api_no_token_returns_401(enabled_app):
    """Auth enabled + no token → admin API returns 401."""
    with TestClient(enabled_app, raise_server_exceptions=False) as client:
        resp = client.get("/api/v1/admin/settings", follow_redirects=False)
    assert resp.status_code == 401
    assert "Authentication required" in resp.text


@pytest.mark.asyncio
async def test_auth_enabled_ui_admin_no_token_redirects(enabled_app):
    """Auth enabled + no token → web admin page returns 302 to /ui/login."""
    with TestClient(enabled_app) as client:
        resp = client.get("/ui/admin/settings", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/ui/login?next=")


@pytest.mark.asyncio
async def test_auth_enabled_write_op_no_token_returns_401(enabled_app):
    """Auth enabled + no token → POST /api/v1/documents returns 401."""
    with TestClient(enabled_app, raise_server_exceptions=False) as client:
        resp = client.post("/api/v1/documents/upload")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_enabled_tags_post_no_token_returns_401(enabled_app):
    """Auth enabled + no token → POST /api/v1/tags returns 401."""
    with TestClient(enabled_app, raise_server_exceptions=False) as client:
        resp = client.post("/api/v1/tags", json={"name": "foo"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: auth enabled, valid credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_enabled_bearer_token_passes(enabled_app):
    """Auth enabled + valid Bearer token → request passes through."""
    with TestClient(enabled_app) as client:
        token = _login(client)
        resp = client.get(
            "/api/v1/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
    # Passes middleware — route may return 200 or something else but not 401
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_auth_enabled_cookie_passes(enabled_app):
    """Auth enabled + valid cookie set by login → request passes through."""
    with TestClient(enabled_app) as client:
        # Login sets the cookie
        client.post("/api/v1/auth/login", json={"name": "Alice", "password": "pw123"})
        # Cookie is now in the client's cookie jar
        resp = client.get("/api/v1/admin/settings")
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_auth_enabled_invalid_token_returns_401(enabled_app):
    """Auth enabled + invalid token → admin API returns 401."""
    with TestClient(enabled_app, raise_server_exceptions=False) as client:
        resp = client.get(
            "/api/v1/admin/settings",
            headers={"Authorization": "Bearer this.is.invalid"},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: exempt paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exempt_setup_status_no_token(enabled_app):
    """GET /api/v1/admin/setup/status is exempt — passes without token."""
    with TestClient(enabled_app) as client:
        resp = client.get("/api/v1/admin/setup/status")
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_exempt_login_page_no_token(enabled_app):
    """GET /ui/login is exempt — returns 200 without token."""
    with TestClient(enabled_app) as client:
        resp = client.get("/ui/login")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: read-only paths are NOT protected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_enabled_get_documents_no_token_passes(enabled_app):
    """Auth enabled + no token → GET /api/v1/documents passes (read-only)."""
    with TestClient(enabled_app) as client:
        resp = client.get("/api/v1/documents")
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_auth_enabled_get_tags_no_token_passes(enabled_app):
    """Auth enabled + no token → GET /api/v1/tags passes (read-only)."""
    with TestClient(enabled_app) as client:
        resp = client.get("/api/v1/tags")
    assert resp.status_code != 401
