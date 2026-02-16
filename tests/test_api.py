"""Tests for API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from librarian.app import create_app
from librarian.config import AppConfig


@pytest.fixture
def app(test_config):
    """Create test app."""
    return create_app(test_config)


@pytest.fixture
def client(app):
    """Create test client (sync, no lifespan)."""
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint(client):
    """Health endpoint should return ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_docs_endpoint(client):
    """OpenAPI docs should be accessible."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["info"]["title"] == "Librarian"
