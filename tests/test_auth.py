"""Tests for authentication (M12)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from mymemex.config import AppConfig, AuthConfig, LLMConfig
from mymemex.services.auth import AuthService
from mymemex.storage.database import get_session, init_database
from mymemex.storage.repositories import UserRepository


# --- Unit tests: password hashing ---


def test_hash_password_returns_non_empty():
    """hash_password produces a non-empty string."""
    h = AuthService.hash_password("secret")
    assert h
    assert h != "secret"


def test_verify_password_correct():
    """verify_password succeeds with correct plaintext."""
    h = AuthService.hash_password("correct")
    assert AuthService.verify_password("correct", h) is True


def test_verify_password_wrong():
    """verify_password fails with wrong plaintext."""
    h = AuthService.hash_password("correct")
    assert AuthService.verify_password("wrong", h) is False


# --- Unit tests: JWT token ---


def test_create_and_decode_token():
    """Round-trip: create token, decode payload."""
    from mymemex.storage.models import User

    user = User()
    user.id = 42
    user.name = "Alice"
    user.is_admin = False

    secret = "test-secret-key-abc123"
    token = AuthService.create_access_token(user, secret=secret, expire_hours=1)

    assert isinstance(token, str)
    assert len(token) > 10

    payload = AuthService.decode_token(token, secret)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["name"] == "Alice"
    assert payload["is_admin"] is False


def test_decode_token_wrong_secret():
    """Decoding with wrong secret returns None."""
    from mymemex.storage.models import User

    user = User()
    user.id = 1
    user.name = "Bob"
    user.is_admin = False

    token = AuthService.create_access_token(user, secret="correct-secret")
    result = AuthService.decode_token(token, "wrong-secret")
    assert result is None


def test_decode_token_invalid_string():
    """Decoding garbage returns None."""
    result = AuthService.decode_token("not-a-jwt", "secret")
    assert result is None


def test_decode_token_empty_secret():
    """Decoding with empty secret returns None."""
    result = AuthService.decode_token("any.token.here", "")
    assert result is None


# --- Integration tests with DB ---


@pytest_asyncio.fixture
async def db_for_auth(tmp_path):
    """Initialize test database for auth tests."""
    import mymemex.storage.database as db_module

    db_path = tmp_path / "test_auth.db"
    await init_database(db_path)
    async with get_session() as session:
        yield session

    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest.mark.asyncio
async def test_authenticate_success(db_for_auth):
    """authenticate returns user on correct credentials."""
    session = db_for_auth
    repo = UserRepository(session)
    pw_hash = AuthService.hash_password("mysecret")
    await repo.create(name="Carol", password_hash=pw_hash)

    user = await AuthService.authenticate(session, "Carol", "mysecret")
    assert user is not None
    assert user.name == "Carol"


@pytest.mark.asyncio
async def test_authenticate_wrong_password(db_for_auth):
    """authenticate returns None on wrong password."""
    session = db_for_auth
    repo = UserRepository(session)
    pw_hash = AuthService.hash_password("correct")
    await repo.create(name="Dave", password_hash=pw_hash)

    user = await AuthService.authenticate(session, "Dave", "wrong")
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_no_password(db_for_auth):
    """authenticate returns None for users without a password."""
    session = db_for_auth
    repo = UserRepository(session)
    await repo.create(name="Eve")  # no password

    user = await AuthService.authenticate(session, "Eve", "anything")
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_unknown_user(db_for_auth):
    """authenticate returns None for unknown user names."""
    session = db_for_auth
    user = await AuthService.authenticate(session, "NoSuchUser", "pass")
    assert user is None


# --- API endpoint tests ---


@pytest_asyncio.fixture
async def auth_app(tmp_path):
    """Create a test FastAPI app with auth enabled."""
    import mymemex.storage.database as db_module

    db_path = tmp_path / "test_auth_api.db"
    await init_database(db_path)

    # Create a user with a password
    async with get_session() as session:
        repo = UserRepository(session)
        pw_hash = AuthService.hash_password("secret123")
        await repo.create(name="TestUser", password_hash=pw_hash, is_admin=True)

    from mymemex.app import create_app

    config = AppConfig(
        auth=AuthConfig(enabled=True, jwt_secret_key="test-jwt-secret", session_expiry_hours=1),
    )
    config.database.path = db_path
    app = create_app(config)

    yield app

    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest.mark.asyncio
async def test_login_success(auth_app):
    """POST /auth/login returns token on valid credentials."""
    with TestClient(auth_app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"name": "TestUser", "password": "secret123"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["name"] == "TestUser"


@pytest.mark.asyncio
async def test_login_wrong_password(auth_app):
    """POST /auth/login returns 401 on wrong password."""
    with TestClient(auth_app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"name": "TestUser", "password": "wrongpass"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_auth_disabled():
    """GET /auth/me returns auth_enabled=false when auth is disabled."""
    from mymemex.app import create_app

    config = AppConfig(auth=AuthConfig(enabled=False))
    app = create_app(config)

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["auth_enabled"] is False
    assert data["authenticated"] is False


@pytest.mark.asyncio
async def test_me_with_valid_token(auth_app):
    """GET /auth/me returns user info with valid Bearer token."""
    with TestClient(auth_app) as client:
        # First login
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"name": "TestUser", "password": "secret123"},
        )
        token = login_resp.json()["access_token"]

        # Then call /me
        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["authenticated"] is True
    assert data["name"] == "TestUser"


@pytest.mark.asyncio
async def test_me_without_token(auth_app):
    """GET /auth/me returns 401 when auth is enabled and no token provided."""
    with TestClient(auth_app) as client:
        response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
