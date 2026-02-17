"""Tests for document classification."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from librarian.config import AppConfig, ClassificationConfig, LLMConfig
from librarian.intelligence.classifier import (
    ClassificationResult,
    DocumentClassifier,
)
from librarian.intelligence.llm_client import LLMClient, create_llm_client
from librarian.services.classification import ClassificationService
from librarian.storage.database import get_session, init_database
from librarian.storage.repositories import (
    ChunkRepository,
    DocumentRepository,
    TagRepository,
)


# --- Unit tests: ClassificationResult ---


def test_classification_result_from_dict():
    """Test ClassificationResult parsing."""
    data = {
        "document_type": "invoice",
        "type_confidence": 0.95,
        "tags": [
            {"name": "financial", "confidence": 0.9},
        ],
        "summary": "Test invoice",
    }

    result = ClassificationResult.from_dict(data)

    assert result.document_type == "invoice"
    assert result.type_confidence == 0.95
    assert len(result.tags) == 1
    assert result.summary == "Test invoice"


def test_classification_result_from_dict_defaults():
    """Test ClassificationResult with missing fields."""
    result = ClassificationResult.from_dict({})

    assert result.document_type == "other"
    assert result.type_confidence == 0.0
    assert result.tags == []
    assert result.summary == ""


# --- Unit tests: DocumentClassifier ---


@pytest.fixture
def classification_config():
    return ClassificationConfig(
        enabled=True,
        confidence_threshold=0.7,
        max_tags=5,
    )


@pytest.fixture
def app_config_no_llm(classification_config):
    return AppConfig(
        classification=classification_config,
        llm=LLMConfig(provider="none", model=""),
    )


def test_filter_tags_by_confidence(app_config_no_llm):
    """Test filtering tags by confidence threshold."""
    # Need a mock LLM client since provider is "none" and _create_client would fail
    mock_llm = AsyncMock(spec=LLMClient)
    classifier = DocumentClassifier(app_config_no_llm, llm_client=mock_llm)

    tags = [
        {"name": "tax", "confidence": 0.9},
        {"name": "financial", "confidence": 0.8},
        {"name": "low_confidence", "confidence": 0.5},
    ]

    filtered = classifier.filter_tags_by_confidence(tags)

    assert "tax" in filtered
    assert "financial" in filtered
    assert "low_confidence" not in filtered


def test_max_tags_limit(app_config_no_llm):
    """Test max tags limit."""
    app_config_no_llm.classification.max_tags = 2
    mock_llm = AsyncMock(spec=LLMClient)
    classifier = DocumentClassifier(app_config_no_llm, llm_client=mock_llm)

    tags = [
        {"name": "tag1", "confidence": 0.9},
        {"name": "tag2", "confidence": 0.9},
        {"name": "tag3", "confidence": 0.9},
    ]

    filtered = classifier.filter_tags_by_confidence(tags)

    assert len(filtered) == 2


@pytest.mark.asyncio
async def test_classify_disabled(app_config_no_llm):
    """Test classification when disabled."""
    app_config_no_llm.classification.enabled = False
    mock_llm = AsyncMock(spec=LLMClient)
    classifier = DocumentClassifier(app_config_no_llm, llm_client=mock_llm)

    result = await classifier.classify("some content")

    assert result is None


@pytest.mark.asyncio
async def test_classify_no_llm(app_config_no_llm):
    """Test classification when no LLM configured."""
    mock_llm = AsyncMock(spec=LLMClient)
    classifier = DocumentClassifier(app_config_no_llm, llm_client=mock_llm)

    result = await classifier.classify("some content")

    assert result is None


@pytest.mark.asyncio
async def test_classify_success():
    """Test successful classification with mock LLM."""
    config = AppConfig(
        classification=ClassificationConfig(enabled=True, confidence_threshold=0.7),
        llm=LLMConfig(provider="ollama", model="test-model"),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_json.return_value = {
        "document_type": "invoice",
        "type_confidence": 0.95,
        "tags": [
            {"name": "financial", "confidence": 0.9},
            {"name": "business", "confidence": 0.8},
        ],
        "summary": "An invoice for services rendered",
    }

    classifier = DocumentClassifier(config, llm_client=mock_llm)
    result = await classifier.classify("Invoice #123\nAmount: $500")

    assert result is not None
    assert result.document_type == "invoice"
    assert result.type_confidence == 0.95
    assert len(result.tags) == 2
    mock_llm.generate_json.assert_called_once()


@pytest.mark.asyncio
async def test_classify_llm_error():
    """Test classification gracefully handles LLM errors."""
    config = AppConfig(
        classification=ClassificationConfig(enabled=True),
        llm=LLMConfig(provider="ollama", model="test-model"),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_json.side_effect = ValueError("Connection refused")

    classifier = DocumentClassifier(config, llm_client=mock_llm)
    result = await classifier.classify("some content")

    assert result is None


# --- Unit tests: LLM client factory ---


def test_create_llm_client_ollama():
    """Test creating Ollama client."""
    from librarian.intelligence.llm_client import OllamaClient

    config = LLMConfig(provider="ollama", model="llama2")
    client = create_llm_client(config)
    assert isinstance(client, OllamaClient)


def test_create_llm_client_openai():
    """Test creating OpenAI client."""
    from librarian.intelligence.llm_client import OpenAIClient

    config = LLMConfig(provider="openai", model="gpt-4o-mini")
    client = create_llm_client(config, api_key="test-key")
    assert isinstance(client, OpenAIClient)


def test_create_llm_client_openai_no_key():
    """Test OpenAI client requires API key."""
    config = LLMConfig(provider="openai", model="gpt-4o-mini")
    with pytest.raises(ValueError, match="API key required"):
        create_llm_client(config)


def test_create_llm_client_unknown():
    """Test unknown provider raises error."""
    config = LLMConfig(provider="ollama")  # will override below
    config.provider = "unknown"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client(config)


# --- Integration tests: ClassificationService with DB ---


@pytest_asyncio.fixture
async def db_session_for_classification(tmp_path):
    """Initialize test database for classification tests."""
    import librarian.storage.database as db_module

    db_path = tmp_path / "test_classify.db"
    await init_database(db_path)
    async with get_session() as session:
        yield session

    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest.mark.asyncio
async def test_classify_document_applies_tags(db_session_for_classification):
    """Test that classify_document applies auto-tags to a document."""
    session = db_session_for_classification
    doc_repo = DocumentRepository(session)
    chunk_repo = ChunkRepository(session)
    tag_repo = TagRepository(session)

    # Create a document
    doc = await doc_repo.create(
        content_hash="classify_test_hash",
        quick_hash="classify_quick",
        file_size=1000,
        original_path="/tmp/test_classify.pdf",
        original_filename="test_classify.pdf",
        mime_type="application/pdf",
        file_modified_at=1000000.0,
    )
    await doc_repo.update_status(doc, "ready")

    # Create chunks
    await chunk_repo.create(
        document_id=doc.id,
        chunk_index=0,
        text="Invoice #12345. Amount due: $1,500.00. Payment terms: Net 30.",
        char_count=60,
    )
    await session.commit()

    # Create service with mock LLM
    config = AppConfig(
        classification=ClassificationConfig(enabled=True, confidence_threshold=0.7),
        llm=LLMConfig(provider="ollama", model="test-model"),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_json.return_value = {
        "document_type": "invoice",
        "type_confidence": 0.95,
        "tags": [
            {"name": "financial", "confidence": 0.9},
            {"name": "business", "confidence": 0.85},
            {"name": "low_conf", "confidence": 0.3},
        ],
        "summary": "Invoice for services",
    }

    service = ClassificationService(config)
    service.classifier = DocumentClassifier(config, llm_client=mock_llm)

    result = await service.classify_document(doc.id)

    assert result is not None
    assert result.document_type == "invoice"

    # Verify tags were applied — need a fresh session to read
    async with get_session() as fresh_session:
        fresh_tag_repo = TagRepository(fresh_session)
        tags = await fresh_tag_repo.get_document_tags(doc.id)

    # Should have: financial, business, invoice (type tag) — but NOT low_conf
    assert "financial" in tags
    assert "business" in tags
    assert "invoice" in tags
    assert "low_conf" not in tags


@pytest.mark.asyncio
async def test_classify_document_no_chunks(db_session_for_classification):
    """Test classification with no chunks returns None."""
    session = db_session_for_classification
    doc_repo = DocumentRepository(session)

    doc = await doc_repo.create(
        content_hash="no_chunks_hash",
        quick_hash="no_chunks_quick",
        file_size=500,
        original_path="/tmp/no_chunks.pdf",
        original_filename="no_chunks.pdf",
        mime_type="application/pdf",
        file_modified_at=1000000.0,
    )

    config = AppConfig(
        classification=ClassificationConfig(enabled=True),
        llm=LLMConfig(provider="ollama", model="test-model"),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    service = ClassificationService(config)
    service.classifier = DocumentClassifier(config, llm_client=mock_llm)

    result = await service.classify_document(doc.id)

    assert result is None
    mock_llm.generate_json.assert_not_called()


@pytest.mark.asyncio
async def test_classify_document_not_found(db_session_for_classification):
    """Test classification with non-existent document returns None."""
    config = AppConfig(
        classification=ClassificationConfig(enabled=True),
        llm=LLMConfig(provider="ollama", model="test-model"),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    service = ClassificationService(config)
    service.classifier = DocumentClassifier(config, llm_client=mock_llm)

    result = await service.classify_document(99999)

    assert result is None
