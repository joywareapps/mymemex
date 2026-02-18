"""Tests for structured extraction (M9.5)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from librarian.config import AppConfig, ExtractionConfig, LLMConfig
from librarian.intelligence.llm_client import LLMClient
from librarian.services.extraction import ExtractionResult, ExtractionService
from librarian.storage.database import get_session, init_database
from librarian.storage.repositories import (
    ChunkRepository,
    DocumentFieldRepository,
    DocumentRepository,
)


# --- Unit tests: ExtractionResult ---


def test_extraction_result_from_dict():
    """Test ExtractionResult parsing."""
    data = {
        "document_type": "tax_return",
        "document_date": "2023-12-31",
        "category": "tax",
        "amounts": [
            {"label": "total_tax", "value": 15234.56, "currency": "EUR"},
        ],
        "entities": [
            {"type": "organization", "name": "Finanzamt"},
        ],
        "confidence": 0.92,
    }

    result = ExtractionResult.from_dict(data)

    assert result.document_type == "tax_return"
    assert result.document_date == "2023-12-31"
    assert result.category == "tax"
    assert len(result.amounts) == 1
    assert len(result.entities) == 1
    assert result.confidence == 0.92


def test_extraction_result_defaults():
    """Test ExtractionResult with missing fields."""
    result = ExtractionResult.from_dict({})

    assert result.document_type is None
    assert result.document_date is None
    assert result.category is None
    assert result.amounts == []
    assert result.entities == []
    assert result.confidence == 1.0


# --- Unit tests: ExtractionService without DB ---


@pytest.mark.asyncio
async def test_extract_without_llm():
    """Test extraction when no LLM configured."""
    config = AppConfig(
        llm=LLMConfig(provider="none"),
        extraction=ExtractionConfig(enabled=True),
    )

    service = ExtractionService(config)
    result = await service.extract_document(1)

    assert result is None


@pytest.mark.asyncio
async def test_extract_disabled():
    """Test extraction when disabled."""
    config = AppConfig(
        llm=LLMConfig(provider="ollama", model="test"),
        extraction=ExtractionConfig(enabled=False),
    )

    service = ExtractionService(config)
    result = await service.extract_document(1)

    assert result is None


# --- Integration tests with DB ---


@pytest_asyncio.fixture
async def db_session_for_extraction(tmp_path):
    """Initialize test database for extraction tests."""
    import librarian.storage.database as db_module

    db_path = tmp_path / "test_extraction.db"
    await init_database(db_path)
    async with get_session() as session:
        yield session

    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest_asyncio.fixture
async def sample_doc_with_chunks(db_session_for_extraction):
    """Create a document with chunks for testing."""
    session = db_session_for_extraction
    doc_repo = DocumentRepository(session)
    chunk_repo = ChunkRepository(session)

    doc = await doc_repo.create(
        content_hash="extraction_test_hash",
        quick_hash="extraction_quick",
        file_size=2000,
        original_path="/tmp/test_extract.pdf",
        original_filename="test_extract.pdf",
        mime_type="application/pdf",
        file_modified_at=1000000.0,
    )
    await doc_repo.update_status(doc, "ready")

    await chunk_repo.create(
        document_id=doc.id,
        chunk_index=0,
        text="Einkommensteuerbescheid 2023. Steuernummer: 123/456/78901. "
             "Zu versteuerndes Einkommen: 68.000,00 EUR. "
             "Festgesetzte Einkommensteuer: 15.234,56 EUR.",
        char_count=150,
    )
    await session.commit()

    return doc


@pytest.mark.asyncio
async def test_extract_document_stores_fields(db_session_for_extraction, sample_doc_with_chunks):
    """Test that extract_document stores fields in DB."""
    doc = sample_doc_with_chunks

    config = AppConfig(
        llm=LLMConfig(provider="ollama", model="test-model"),
        extraction=ExtractionConfig(enabled=True),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_json.return_value = {
        "document_type": "tax_return",
        "document_date": "2023-12-31",
        "category": "tax",
        "amounts": [
            {"label": "total_tax", "value": 15234.56, "currency": "EUR"},
            {"label": "taxable_income", "value": 68000.00, "currency": "EUR"},
        ],
        "entities": [
            {"type": "organization", "name": "Finanzamt"},
            {"type": "reference", "value": "123/456/78901"},
        ],
        "confidence": 0.92,
    }

    service = ExtractionService(config, llm_client=mock_llm)
    result = await service.extract_document(doc.id)

    assert result is not None
    assert result.document_type == "tax_return"
    assert result.category == "tax"
    assert len(result.amounts) == 2
    assert len(result.entities) == 2

    # Verify fields stored in DB
    async with get_session() as session:
        field_repo = DocumentFieldRepository(session)
        fields = await field_repo.get_by_document(doc.id)

    # 2 amounts + 2 entities = 4 fields
    assert len(fields) == 4

    currency_fields = [f for f in fields if f.field_type == "currency"]
    assert len(currency_fields) == 2
    assert any(f.field_name == "total_tax" and f.value_number == 15234.56 for f in currency_fields)

    string_fields = [f for f in fields if f.field_type == "string"]
    assert len(string_fields) == 2

    # Verify document metadata updated
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        updated_doc = await doc_repo.get_by_id(doc.id)

    assert updated_doc.category == "tax"
    assert updated_doc.document_date == date(2023, 12, 31)


@pytest.mark.asyncio
async def test_extract_document_no_chunks(db_session_for_extraction):
    """Test extraction with no chunks returns None."""
    session = db_session_for_extraction
    doc_repo = DocumentRepository(session)

    doc = await doc_repo.create(
        content_hash="no_chunks_extract",
        quick_hash="no_chunks_ext_q",
        file_size=500,
        original_path="/tmp/empty.pdf",
        original_filename="empty.pdf",
        mime_type="application/pdf",
        file_modified_at=1000000.0,
    )

    config = AppConfig(
        llm=LLMConfig(provider="ollama", model="test"),
        extraction=ExtractionConfig(enabled=True),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    service = ExtractionService(config, llm_client=mock_llm)

    result = await service.extract_document(doc.id)

    assert result is None
    mock_llm.generate_json.assert_not_called()


@pytest.mark.asyncio
async def test_extract_document_not_found(db_session_for_extraction):
    """Test extraction with non-existent document."""
    config = AppConfig(
        llm=LLMConfig(provider="ollama", model="test"),
        extraction=ExtractionConfig(enabled=True),
    )

    mock_llm = AsyncMock(spec=LLMClient)
    service = ExtractionService(config, llm_client=mock_llm)

    result = await service.extract_document(99999)

    assert result is None


@pytest.mark.asyncio
async def test_extract_reextract_clears_old_fields(db_session_for_extraction, sample_doc_with_chunks):
    """Test that re-extraction deletes old fields before inserting new ones."""
    doc = sample_doc_with_chunks

    config = AppConfig(
        llm=LLMConfig(provider="ollama", model="test"),
        extraction=ExtractionConfig(enabled=True),
    )

    # First extraction
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_json.return_value = {
        "document_type": "invoice",
        "category": "financial",
        "amounts": [{"label": "total", "value": 100.0, "currency": "USD"}],
        "entities": [],
        "confidence": 0.8,
    }

    service = ExtractionService(config, llm_client=mock_llm)
    await service.extract_document(doc.id)

    async with get_session() as session:
        field_repo = DocumentFieldRepository(session)
        fields_v1 = await field_repo.get_by_document(doc.id)
    assert len(fields_v1) == 1

    # Second extraction with different data
    mock_llm.generate_json.return_value = {
        "document_type": "tax_return",
        "category": "tax",
        "amounts": [
            {"label": "tax_a", "value": 200.0, "currency": "EUR"},
            {"label": "tax_b", "value": 300.0, "currency": "EUR"},
        ],
        "entities": [],
        "confidence": 0.9,
    }

    await service.extract_document(doc.id)

    async with get_session() as session:
        field_repo = DocumentFieldRepository(session)
        fields_v2 = await field_repo.get_by_document(doc.id)

    # Old field should be gone, only new ones
    assert len(fields_v2) == 2
    assert all(f.currency == "EUR" for f in fields_v2)


# --- Repository tests ---


@pytest.mark.asyncio
async def test_document_field_repository_create(db_session_for_extraction, sample_doc_with_chunks):
    """Test creating document fields."""
    doc = sample_doc_with_chunks

    async with get_session() as session:
        field_repo = DocumentFieldRepository(session)

        field = await field_repo.create(
            document_id=doc.id,
            field_name="total_tax",
            field_type="currency",
            value_number=15234.56,
            currency="EUR",
            confidence=0.92,
            source="llm",
        )

        assert field.id is not None
        assert field.field_name == "total_tax"
        assert field.value_number == 15234.56
        assert field.currency == "EUR"


@pytest.mark.asyncio
async def test_aggregate_amounts_empty(db_session_for_extraction):
    """Test aggregation with no matching documents."""
    config = AppConfig(
        llm=LLMConfig(provider="none"),
        extraction=ExtractionConfig(enabled=True),
    )

    service = ExtractionService(config)

    result = await service.aggregate_amounts(category="nonexistent")

    assert result["aggregation"]["results"] == []
    assert result["yearly_breakdown"] == []


@pytest.mark.asyncio
async def test_aggregate_amounts_with_data(db_session_for_extraction, sample_doc_with_chunks):
    """Test aggregation returns correct totals."""
    doc = sample_doc_with_chunks

    # Set document date and category
    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        d = await doc_repo.get_by_id(doc.id)
        await doc_repo.update(d, category="tax", document_date=date(2023, 12, 31))

    # Add some fields
    async with get_session() as session:
        field_repo = DocumentFieldRepository(session)
        await field_repo.create(
            document_id=doc.id,
            field_name="total_tax",
            field_type="currency",
            value_number=15234.56,
            currency="EUR",
            confidence=0.9,
        )
        await field_repo.create(
            document_id=doc.id,
            field_name="taxable_income",
            field_type="currency",
            value_number=68000.00,
            currency="EUR",
            confidence=0.9,
        )

    config = AppConfig(
        llm=LLMConfig(provider="none"),
        extraction=ExtractionConfig(enabled=True),
    )
    service = ExtractionService(config)

    result = await service.aggregate_amounts(category="tax", currency="EUR")

    assert len(result["aggregation"]["results"]) == 1
    agg = result["aggregation"]["results"][0]
    assert agg["currency"] == "EUR"
    assert agg["total"] == 15234.56 + 68000.00
    assert agg["count"] == 2


@pytest.mark.asyncio
async def test_get_document_fields(db_session_for_extraction, sample_doc_with_chunks):
    """Test getting extracted fields for a document."""
    doc = sample_doc_with_chunks

    async with get_session() as session:
        field_repo = DocumentFieldRepository(session)
        await field_repo.create(
            document_id=doc.id,
            field_name="total",
            field_type="currency",
            value_number=500.0,
            currency="USD",
            confidence=0.85,
        )

    config = AppConfig(
        llm=LLMConfig(provider="none"),
        extraction=ExtractionConfig(enabled=True),
    )
    service = ExtractionService(config)

    result = await service.get_document_fields(doc.id)

    assert result["document_id"] == doc.id
    assert len(result["fields"]) == 1
    assert result["fields"][0]["name"] == "total"
    assert result["fields"][0]["value"] == 500.0


@pytest.mark.asyncio
async def test_list_document_types(db_session_for_extraction, sample_doc_with_chunks):
    """Test listing document categories."""
    doc = sample_doc_with_chunks

    async with get_session() as session:
        doc_repo = DocumentRepository(session)
        d = await doc_repo.get_by_id(doc.id)
        await doc_repo.update(d, category="tax")

    config = AppConfig(
        llm=LLMConfig(provider="none"),
        extraction=ExtractionConfig(enabled=True),
    )
    service = ExtractionService(config)

    types = await service.list_document_types()

    assert len(types) >= 1
    assert any(t["category"] == "tax" for t in types)
