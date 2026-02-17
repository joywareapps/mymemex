# M9.5: Structured Extraction & Aggregation Implementation

**Goal:** Extract structured data (amounts, dates, entities) from documents using LLM inference and enable aggregation queries across the library.

**Prerequisites:**
- ✅ M9 Auto-Tagging (LLM client, classification pipeline)
- ✅ M6.5 Service Layer
- ✅ M7 MCP Server

**Dependencies:**
- M9's `LLMClient` abstraction
- M9's classification worker pattern

---

## Overview

Build on M9's classification pipeline to extract structured metadata from documents and store it in a queryable format. This enables questions like:

- "How much tax did I pay from 2015-2025?"
- "What's my total insurance premium across all policies?"
- "Show me all medical expenses for 2024"

**Key features:**
1. **Typed metadata storage** — `document_fields` table with typed values
2. **LLM extraction pipeline** — Background task after document ready
3. **Aggregation tools** — MCP tools for summing amounts
4. **Graceful degradation** — Documents work without extraction

---

## Architecture (ADR-010)

### Storage Schema

**New table: `document_fields`**

```sql
CREATE TABLE document_fields (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,     -- 'total_tax', 'premium', 'invoice_total'
    field_type TEXT NOT NULL,     -- 'currency', 'date', 'string', 'number'
    value_text TEXT,              -- for string values
    value_number REAL,            -- for numeric/currency values
    value_date TEXT,              -- ISO 8601 date string
    currency TEXT,                -- 'EUR', 'USD', etc. (when field_type='currency')
    confidence REAL DEFAULT 1.0,  -- 0.0-1.0, extraction confidence
    source TEXT NOT NULL,         -- 'llm', 'regex', 'manual'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_doc_fields_document ON document_fields(document_id);
CREATE INDEX ix_doc_fields_name ON document_fields(field_name);
```

**New column on `documents`:**

```sql
ALTER TABLE documents ADD COLUMN document_date DATE;
ALTER TABLE documents ADD COLUMN category TEXT;
```

**Why typed table (not JSON):**
- Aggregation queries need `SUM()`, `GROUP BY` on typed values
- SQLite has no JSON indexes
- Full index support for fast filtering
- Standard SQL joins

### Extraction Flow

```
Document Ingestion
    │
    ▼
Text Extraction + Chunking → status="ready"
    │
    ▼
Enqueue EXTRACT_METADATA task
    │
    ▼
Extraction Worker
    │
    ├─► LLM Extraction Prompt
    │       │
    │       ▼
    │   Parse JSON response
    │       │
    │       ▼
    │   Store in document_fields
    │       │
    │       ▼
    │   Update category, document_date
    │
    ▼
Document ready with structured data
```

### Extraction Prompt

```
Extract structured metadata from this document.

Document content:
{content}

Extract:
1. Document type (tax_return, invoice, receipt, contract, insurance_policy, bank_statement, utility_bill, medical_record, other)
2. Document date (the date this document refers to, not when it was created)
3. Monetary amounts with labels (total_tax, premium, invoice_total, etc.)
4. Key entities (organizations, people, reference numbers)

Return JSON:
{
  "document_type": "tax_return",
  "document_date": "2023-12-31",
  "category": "tax",
  "amounts": [
    {"label": "total_tax", "value": 15234.56, "currency": "EUR"},
    {"label": "taxable_income", "value": 68000.00, "currency": "EUR"}
  ],
  "entities": [
    {"type": "organization", "name": "Finanzamt Fürth"},
    {"type": "reference", "value": "StNr. 123/456/78901"}
  ],
  "confidence": 0.92
}
```

---

## Implementation Steps

### Step 1: Add Database Models

**File:** `src/librarian/storage/models.py`

Add `DocumentField` model and update `Document`:

```python
class Document(Base):
    __tablename__ = "documents"

    # ... existing fields ...
    
    # New fields for M9.5
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Relationship
    extracted_fields: Mapped[list["DocumentField"]] = relationship(
        "DocumentField", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentField(Base):
    """Extracted structured field from a document."""
    
    __tablename__ = "document_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'currency', 'date', 'string', 'number'
    
    # Typed value storage (only one populated per field)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_date: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ISO date
    
    # For currency fields
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)  # 'EUR', 'USD'
    
    # Metadata
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'llm', 'regex', 'manual'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationship
    document: Mapped["Document"] = relationship("Document", back_populates="extracted_fields")

    __table_args__ = (
        Index("ix_doc_fields_document", "document_id"),
        Index("ix_doc_fields_name", "field_name"),
    )
```

---

### Step 2: Add Task Type

**File:** `src/librarian/core/queue.py`

Add new task type:

```python
class TaskType(str, Enum):
    INGEST = "ingest"
    EXTRACT_TEXT = "extract_text"
    OCR_PAGE = "ocr_page"
    CHUNK = "chunk"
    EMBED = "embed"
    CLASSIFY = "classify"
    EXTRACT_METADATA = "extract_metadata"  # NEW
    SUGGEST = "suggest"
```

---

### Step 3: Create DocumentFieldRepository

**File:** `src/librarian/storage/repositories.py`

Add repository for document fields:

```python
class DocumentFieldRepository:
    """Data access for extracted document fields."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document_id: int,
        field_name: str,
        field_type: str,
        value_text: str | None = None,
        value_number: float | None = None,
        value_date: str | None = None,
        currency: str | None = None,
        confidence: float = 1.0,
        source: str = "llm",
    ) -> DocumentField:
        """Create a new document field."""
        field = DocumentField(
            document_id=document_id,
            field_name=field_name,
            field_type=field_type,
            value_text=value_text,
            value_number=value_number,
            value_date=value_date,
            currency=currency,
            confidence=confidence,
            source=source,
        )
        self.session.add(field)
        await self.session.commit()
        await self.session.refresh(field)
        return field

    async def get_by_document(self, document_id: int) -> list[DocumentField]:
        """Get all fields for a document."""
        result = await self.session.execute(
            select(DocumentField).where(DocumentField.document_id == document_id)
        )
        return list(result.scalars().all())

    async def delete_for_document(self, document_id: int) -> int:
        """Delete all fields for a document (for re-extraction)."""
        result = await self.session.execute(
            delete(DocumentField).where(DocumentField.document_id == document_id)
        )
        await self.session.commit()
        return result.rowcount

    async def aggregate_amounts(
        self,
        field_name: str | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        currency: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict:
        """
        Aggregate monetary amounts across documents.
        
        Returns: {total, currency, count, breakdown_by_year}
        """
        query = (
            select(
                DocumentField.currency,
                func.sum(DocumentField.value_number).label("total"),
                func.count(DocumentField.id).label("count"),
            )
            .select_from(DocumentField)
            .join(Document)
            .where(DocumentField.field_type == "currency")
            .where(DocumentField.confidence >= min_confidence)
        )
        
        if field_name:
            query = query.where(DocumentField.field_name == field_name)
        if category:
            query = query.where(Document.category == category)
        if date_from:
            query = query.where(Document.document_date >= date_from)
        if date_to:
            query = query.where(Document.document_date <= date_to)
        if currency:
            query = query.where(DocumentField.currency == currency)
        
        query = query.group_by(DocumentField.currency)
        
        result = await self.session.execute(query)
        rows = result.all()
        
        return {
            "results": [
                {"currency": row.currency, "total": row.total, "count": row.count}
                for row in rows
            ]
        }

    async def get_yearly_breakdown(
        self,
        field_name: str | None = None,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        currency: str | None = None,
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """Get amounts grouped by year."""
        query = (
            select(
                func.strftime("%Y", Document.document_date).label("year"),
                DocumentField.currency,
                func.sum(DocumentField.value_number).label("total"),
                func.count(DocumentField.id).label("count"),
            )
            .select_from(DocumentField)
            .join(Document)
            .where(DocumentField.field_type == "currency")
            .where(DocumentField.confidence >= min_confidence)
            .where(Document.document_date.isnot(None))
        )
        
        if field_name:
            query = query.where(DocumentField.field_name == field_name)
        if category:
            query = query.where(Document.category == category)
        if date_from:
            query = query.where(Document.document_date >= date_from)
        if date_to:
            query = query.where(Document.document_date <= date_to)
        if currency:
            query = query.where(DocumentField.currency == currency)
        
        query = query.group_by("year", DocumentField.currency).order_by("year")
        
        result = await self.session.execute(query)
        return [
            {"year": int(row.year), "currency": row.currency, "total": row.total, "count": row.count}
            for row in result.all()
        ]

    async def list_document_types(self) -> list[dict]:
        """List all document categories with counts."""
        query = (
            select(
                Document.category,
                func.count(Document.id).label("count"),
            )
            .where(Document.category.isnot(None))
            .group_by(Document.category)
            .order_by(func.count(Document.id).desc())
        )
        
        result = await self.session.execute(query)
        return [
            {"category": row.category, "count": row.count}
            for row in result.all()
        ]
```

---

### Step 4: Create Extraction Service

**File:** `src/librarian/services/extraction.py`

```python
"""Extraction and aggregation service."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import structlog

from ..config import AppConfig
from ..intelligence.llm_client import LLMClient, create_llm_client
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentFieldRepository, DocumentRepository

log = structlog.get_logger()

# Default extraction prompt
DEFAULT_EXTRACTION_PROMPT = """Extract structured metadata from this document.

Document content:
{content}

Extract:
1. Document type (tax_return, invoice, receipt, contract, insurance_policy, bank_statement, utility_bill, medical_record, other)
2. Document date (the date this document refers to, not when it was created or scanned)
3. Category (tax, financial, medical, insurance, legal, personal, work, utility, other)
4. Monetary amounts with labels (e.g., total_tax, premium, invoice_total)
5. Key entities (organizations, people, reference numbers)

Return JSON only:
{{
  "document_type": "tax_return",
  "document_date": "2023-12-31",
  "category": "tax",
  "amounts": [
    {{"label": "total_tax", "value": 15234.56, "currency": "EUR"}},
    {{"label": "taxable_income", "value": 68000.00, "currency": "EUR"}}
  ],
  "entities": [
    {{"type": "organization", "name": "Finanzamt Fürth"}},
    {{"type": "reference", "value": "StNr. 123/456/78901"}}
  ],
  "confidence": 0.92
}}
"""


class ExtractionResult:
    """Result of document extraction."""

    def __init__(
        self,
        document_type: str | None = None,
        document_date: str | None = None,
        category: str | None = None,
        amounts: list[dict] | None = None,
        entities: list[dict] | None = None,
        confidence: float = 1.0,
    ):
        self.document_type = document_type
        self.document_date = document_date
        self.category = category
        self.amounts = amounts or []
        self.entities = entities or []
        self.confidence = confidence

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionResult:
        """Create from LLM response dict."""
        return cls(
            document_type=data.get("document_type"),
            document_date=data.get("document_date"),
            category=data.get("category"),
            amounts=data.get("amounts", []),
            entities=data.get("entities", []),
            confidence=data.get("confidence", 1.0),
        )


class ExtractionService:
    """Service for extracting and aggregating document metadata."""

    def __init__(self, config: AppConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client

    def _get_llm_client(self) -> LLMClient | None:
        """Get or create LLM client."""
        if self.llm:
            return self.llm
        if not self.config.llm.provider or self.config.llm.provider == "none":
            return None
        return create_llm_client(self.config.llm)

    async def extract_document(self, document_id: int) -> ExtractionResult | None:
        """
        Extract structured metadata from a document.
        
        Args:
            document_id: Document to extract
            
        Returns:
            ExtractionResult or None if extraction failed
        """
        llm = self._get_llm_client()
        if not llm:
            log.debug("No LLM configured for extraction", document_id=document_id)
            return None

        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)
            field_repo = DocumentFieldRepository(session)

            # Get document
            doc = await doc_repo.get_by_id(document_id)
            if not doc:
                log.warning("Document not found", document_id=document_id)
                return None

            # Get content (first few chunks)
            chunks = await chunk_repo.get_by_document(document_id, limit=5)
            if not chunks:
                log.warning("No chunks found", document_id=document_id)
                return None

            content = "\n\n".join(chunk.text for chunk in chunks)

            try:
                # Extract via LLM
                prompt = DEFAULT_EXTRACTION_PROMPT.format(content=content[:4000])
                response = await llm.generate_json(prompt)
                
                result = ExtractionResult.from_dict(response)

                # Delete old fields (for re-extraction)
                await field_repo.delete_for_document(document_id)

                # Store extracted fields
                for amount in result.amounts:
                    await field_repo.create(
                        document_id=document_id,
                        field_name=amount.get("label", "amount"),
                        field_type="currency",
                        value_number=amount.get("value"),
                        currency=amount.get("currency", "EUR"),
                        confidence=result.confidence,
                        source="llm",
                    )

                for entity in result.entities:
                    entity_type = entity.get("type", "unknown")
                    entity_value = entity.get("name") or entity.get("value", "")
                    if entity_value:
                        await field_repo.create(
                            document_id=document_id,
                            field_name=entity_type,
                            field_type="string",
                            value_text=str(entity_value),
                            confidence=result.confidence,
                            source="llm",
                        )

                # Update document metadata
                if result.category:
                    doc.category = result.category
                if result.document_date:
                    try:
                        doc.document_date = date.fromisoformat(result.document_date)
                    except ValueError:
                        pass
                
                await session.commit()

                log.info(
                    "Document extracted",
                    document_id=document_id,
                    category=result.category,
                    amounts=len(result.amounts),
                    entities=len(result.entities),
                )

                return result

            except Exception as e:
                log.error("Extraction failed", document_id=document_id, error=str(e))
                return None

    async def aggregate_amounts(
        self,
        field_name: str | None = None,
        category: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        currency: str | None = None,
        min_confidence: float = 0.5,
    ) -> dict:
        """
        Aggregate monetary amounts across documents.
        
        Returns aggregated totals and yearly breakdown.
        """
        async with get_session() as session:
            field_repo = DocumentFieldRepository(session)

            # Parse dates
            from_date = date.fromisoformat(date_from) if date_from else None
            to_date = date.fromisoformat(date_to) if date_to else None

            # Get aggregation
            agg_result = await field_repo.aggregate_amounts(
                field_name=field_name,
                category=category,
                date_from=from_date,
                date_to=to_date,
                currency=currency,
                min_confidence=min_confidence,
            )

            # Get yearly breakdown
            breakdown = await field_repo.get_yearly_breakdown(
                field_name=field_name,
                category=category,
                date_from=from_date,
                date_to=to_date,
                currency=currency,
                min_confidence=min_confidence,
            )

            return {
                "aggregation": agg_result,
                "yearly_breakdown": breakdown,
            }

    async def get_document_fields(self, document_id: int) -> dict:
        """Get all extracted fields for a document."""
        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            field_repo = DocumentFieldRepository(session)

            doc = await doc_repo.get_by_id(document_id)
            if not doc:
                return {"error": "Document not found"}

            fields = await field_repo.get_by_document(document_id)

            return {
                "document_id": document_id,
                "title": doc.title or doc.filename,
                "category": doc.category,
                "document_date": str(doc.document_date) if doc.document_date else None,
                "fields": [
                    {
                        "name": f.field_name,
                        "type": f.field_type,
                        "value": f.value_number or f.value_text or f.value_date,
                        "currency": f.currency,
                        "confidence": f.confidence,
                        "source": f.source,
                    }
                    for f in fields
                ],
            }

    async def list_document_types(self) -> list[dict]:
        """List all document categories with counts."""
        async with get_session() as session:
            field_repo = DocumentFieldRepository(session)
            return await field_repo.list_document_types()

    async def reextract_all(self) -> int:
        """Re-extract all documents. Returns count of documents processed."""
        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            docs, total = await doc_repo.list_documents(limit=10000)
            
            count = 0
            for doc in docs:
                try:
                    result = await self.extract_document(doc.id)
                    if result:
                        count += 1
                except Exception as e:
                    log.error("Re-extraction failed", document_id=doc.id, error=str(e))

            log.info("Re-extraction complete", count=count, total=total)
            return count
```

---

### Step 5: Add Task Worker Handler

**File:** `src/librarian/processing/pipeline.py` (modify)

Add extraction task handler:

```python
from ..core.queue import TaskType
from ..services.extraction import ExtractionService

async def task_worker(
    config: AppConfig,
    events: EventManager | None = None,
    worker_id: int = 0,
):
    """Background task worker."""
    log.info("Task worker started", worker_id=worker_id)

    while True:
        try:
            async with get_session() as session:
                queue = TaskQueue(session)

                tasks = await queue.dequeue(limit=1)
                if not tasks:
                    await asyncio.sleep(1)
                    continue

                task = tasks[0]
                log.debug("Processing task", task_id=task.id, type=task.task_type)

                try:
                    if task.task_type == TaskType.INGEST:
                        payload = json.loads(task.payload)
                        await run_ingest_pipeline(
                            document_id=payload["document_id"],
                            config=config,
                            events=events,
                        )

                    elif task.task_type == TaskType.CLASSIFY:
                        payload = json.loads(task.payload)
                        classification_service = ClassificationService(config)
                        await classification_service.classify_document(
                            document_id=payload["document_id"]
                        )

                    elif task.task_type == TaskType.EXTRACT_METADATA:
                        payload = json.loads(task.payload)
                        extraction_service = ExtractionService(config)
                        await extraction_service.extract_document(
                            document_id=payload["document_id"]
                        )

                    elif task.task_type == TaskType.EMBED:
                        # ... existing embedding logic ...

                    await queue.complete(task.id)

                except Exception as e:
                    log.error("Task failed", task_id=task.id, error=str(e))
                    await queue.fail(task.id, str(e))

        except Exception as e:
            log.error("Worker error", worker_id=worker_id, error=str(e))
            await asyncio.sleep(5)
```

Enqueue extraction after document is ready:

```python
async def run_ingest_pipeline(
    document_id: int,
    config: AppConfig,
    events: EventManager | None = None,
):
    """Run full ingestion pipeline."""
    # ... existing code ...

    # After document is "ready", enqueue extraction
    if config.llm.provider and config.llm.provider != "none":
        async with get_session() as session:
            queue = TaskQueue(session)
            await queue.enqueue(
                task_type=TaskType.EXTRACT_METADATA,
                payload={"document_id": document_id},
                document_id=document_id,
                priority=2,  # Lower priority than classification
            )
            log.info("Extraction task enqueued", document_id=document_id)
```

---

### Step 6: Add MCP Tools

**File:** `src/librarian/mcp/tools.py` (modify)

Add 3 new MCP tools:

```python
@mcp.tool()
async def aggregate_amounts(
    category: str | None = None,
    tag: str | None = None,
    field_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str | None = None,
    min_confidence: float = 0.5,
) -> str:
    """
    Aggregate monetary values across filtered documents.

    Use for queries like "How much tax did I pay from 2015-2025?"

    Args:
        category: Filter by document category (e.g., 'tax_return', 'invoice')
        tag: Filter by tag name
        field_name: Field to aggregate (e.g., 'total_tax', 'premium')
        date_from: ISO date, inclusive (e.g., '2015-01-01')
        date_to: ISO date, inclusive (e.g., '2025-12-31')
        currency: Filter by currency (e.g., 'EUR')
        min_confidence: Minimum extraction confidence (default: 0.5)

    Returns:
        Aggregation results with total, count, and yearly breakdown
    """
    from ..services.extraction import ExtractionService

    config = get_config()
    service = ExtractionService(config)

    result = await service.aggregate_amounts(
        field_name=field_name,
        category=category,
        date_from=date_from,
        date_to=date_to,
        currency=currency,
        min_confidence=min_confidence,
    )

    # Format response
    lines = ["# Amount Aggregation\n"]

    if result["aggregation"]["results"]:
        for agg in result["aggregation"]["results"]:
            lines.append(f"**Total:** {agg['currency']} {agg['total']:,.2f}")
            lines.append(f"**Documents:** {agg['count']}")
            lines.append("")

    if result["yearly_breakdown"]:
        lines.append("## Yearly Breakdown\n")
        lines.append("| Year | Currency | Total | Documents |")
        lines.append("|------|----------|-------|-----------|")
        for row in result["yearly_breakdown"]:
            lines.append(f"| {row['year']} | {row['currency']} | {row['total']:,.2f} | {row['count']} |")

    return "\n".join(lines) or "No amounts found matching the filters."


@mcp.tool()
async def get_extracted_fields(document_id: int) -> str:
    """
    View extracted structured fields for a document.

    Args:
        document_id: The document ID

    Returns:
        Document with all extracted fields (amounts, entities, dates)
    """
    from ..services.extraction import ExtractionService

    config = get_config()
    service = ExtractionService(config)

    result = await service.get_document_fields(document_id)

    if "error" in result:
        return f"Error: {result['error']}"

    lines = [
        f"# {result['title']}\n",
        f"**Document ID:** {result['document_id']}",
        f"**Category:** {result['category'] or 'Not classified'}",
        f"**Document Date:** {result['document_date'] or 'Unknown'}\n",
    ]

    if result["fields"]:
        lines.append("## Extracted Fields\n")
        lines.append("| Field | Type | Value | Confidence |")
        lines.append("|-------|------|-------|------------|")
        for f in result["fields"]:
            value = f["value"]
            if f["currency"]:
                value = f"{f['currency']} {value:,.2f}" if isinstance(value, (int, float)) else value
            lines.append(f"| {f['name']} | {f['type']} | {value} | {f['confidence']:.0%} |")
    else:
        lines.append("_No fields extracted yet._")

    return "\n".join(lines)


@mcp.tool()
async def list_document_types() -> str:
    """
    List all auto-classified document types with counts.

    Returns:
        Table of document categories and their counts
    """
    from ..services.extraction import ExtractionService

    config = get_config()
    service = ExtractionService(config)

    types = await service.list_document_types()

    if not types:
        return "No document types found. Upload and process documents first."

    lines = [
        "# Document Types\n",
        "| Category | Documents |",
        "|----------|-----------|",
    ]
    for t in types:
        lines.append(f"| {t['category']} | {t['count']} |")

    return "\n".join(lines)


@mcp.tool()
async def reextract_documents(
    document_ids: list[int] | None = None,
    all_documents: bool = False,
) -> str:
    """
    Re-extract structured metadata from documents.

    Args:
        document_ids: Specific document IDs to re-extract
        all_documents: If true, re-extract all documents

    Returns:
        Summary of re-extraction results
    """
    from ..services.extraction import ExtractionService

    config = get_config()
    service = ExtractionService(config)

    if all_documents:
        count = await service.reextract_all()
        return f"Re-extracted {count} documents"
    elif document_ids:
        results = []
        for doc_id in document_ids:
            result = await service.extract_document(doc_id)
            if result:
                results.append(
                    f"Document {doc_id}: {result.category or 'unknown'} "
                    f"({len(result.amounts)} amounts, {len(result.entities)} entities)"
                )
        return "\n".join(results) or "No documents extracted"
    else:
        return "Specify document_ids or set all_documents=true"
```

---

### Step 7: Create Database Migration

**File:** `alembic/versions/xxx_add_document_fields.py`

```python
"""add document_fields table

Revision ID: xxx
Revises: yyy
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa

revision = 'xxx'
down_revision = 'yyy'

def upgrade():
    # Add columns to documents
    op.add_column('documents', sa.Column('document_date', sa.Date(), nullable=True))
    op.add_column('documents', sa.Column('category', sa.String(100), nullable=True))
    
    # Create document_fields table
    op.create_table(
        'document_fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('field_type', sa.String(20), nullable=False),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.Column('value_number', sa.Float(), nullable=True),
        sa.Column('value_date', sa.String(20), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True, server_default='1.0'),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_doc_fields_document', 'document_fields', ['document_id'])
    op.create_index('ix_doc_fields_name', 'document_fields', ['field_name'])


def downgrade():
    op.drop_index('ix_doc_fields_name')
    op.drop_index('ix_doc_fields_document')
    op.drop_table('document_fields')
    op.drop_column('documents', 'category')
    op.drop_column('documents', 'document_date')
```

---

### Step 8: Add Extraction Config

**File:** `src/librarian/config.py`

```python
class ExtractionConfig(BaseModel):
    """Structured extraction configuration (M9.5)."""

    enabled: bool = True
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    prompt_template: str = ""  # Custom extraction prompt


class AppConfig(BaseSettings):
    # ... existing fields ...
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
```

---

### Step 9: Add Tests

**File:** `tests/test_extraction.py`

```python
"""Tests for document extraction."""

from __future__ import annotations

import pytest

from librarian.services.extraction import ExtractionResult, ExtractionService


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


@pytest.mark.asyncio
async def test_extract_without_llm(app_config):
    """Test extraction when no LLM configured."""
    app_config.llm.provider = "none"

    service = ExtractionService(app_config)
    result = await service.extract_document(1)

    assert result is None


@pytest.mark.asyncio
async def test_aggregate_amounts_empty(app_config, db_session):
    """Test aggregation with no matching documents."""
    service = ExtractionService(app_config)
    
    result = await service.aggregate_amounts(
        category="nonexistent",
    )

    assert result["aggregation"]["results"] == []
    assert result["yearly_breakdown"] == []
```

---

## Config Example

**File:** `~/.config/librarian/config.yaml`

```yaml
watch:
  directories:
    - ~/Documents/librarian-inbox

ocr:
  enabled: true
  language: eng+deu

llm:
  provider: ollama
  model: llama2:7b-chat  # Or gpt-oss:20b
  api_base: http://office-pc:11434

classification:
  enabled: true
  confidence_threshold: 0.7

extraction:
  enabled: true
  min_confidence: 0.5

ai:
  semantic_search_enabled: true
  embedding_model: nomic-embed-text
```

---

## Success Criteria

- [ ] `DocumentField` model created with typed columns
- [ ] `document_date` and `category` added to `Document`
- [ ] `ExtractionService` extracts and stores metadata
- [ ] Extraction task enqueued after ingestion
- [ ] Extraction worker processes tasks
- [ ] MCP tool `aggregate_amounts` works
- [ ] MCP tool `get_extracted_fields` works
- [ ] MCP tool `list_document_types` works
- [ ] "How much tax did I pay 2015-2025?" returns accurate answer
- [ ] Yearly breakdown included in aggregation
- [ ] Tests pass for extraction and aggregation
- [ ] Existing tests still pass

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/librarian/services/extraction.py` | Extraction + aggregation service |
| `tests/test_extraction.py` | Extraction tests |
| `alembic/versions/xxx_add_document_fields.py` | Database migration |

## Files to Modify

| File | Changes |
|------|---------|
| `src/librarian/storage/models.py` | Add `DocumentField`, update `Document` |
| `src/librarian/storage/repositories.py` | Add `DocumentFieldRepository` |
| `src/librarian/core/queue.py` | Add `TaskType.EXTRACT_METADATA` |
| `src/librarian/processing/pipeline.py` | Add extraction worker + enqueue |
| `src/librarian/mcp/tools.py` | Add 4 MCP tools |
| `src/librarian/config.py` | Add `ExtractionConfig` |

---

## Time Estimate

| Task | Time |
|------|------|
| Database models + migration | 2-3 hours |
| DocumentFieldRepository | 2 hours |
| ExtractionService | 4-5 hours |
| Task worker integration | 2 hours |
| MCP tools (4) | 3 hours |
| Tests | 3 hours |
| Documentation | 1 hour |

**Total: 17-21 hours (2-3 days)**

---

## Example Queries

After implementation:

```
User: "How much tax did I pay from 2015-2025?"

→ aggregate_amounts(category="tax", field_name="total_tax", date_from="2015-01-01", date_to="2025-12-31")

Response:
Total: EUR 142,567.00
Documents: 11

Yearly Breakdown:
| Year | Total | Documents |
|------|-------|-----------|
| 2025 | 16,200 | 1 |
| 2024 | 15,890 | 1 |
| 2023 | 15,234 | 1 |
| ... | ... | ... |
```

---

## Notes

- Reuses M9's `LLMClient` abstraction
- Runs as background task (doesn't block ingestion)
- Graceful degradation (document works without extraction)
- Confidence scores allow filtering unreliable extractions
- Can re-extract existing documents after config changes
