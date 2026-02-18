"""Extraction and aggregation service."""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from ..config import AppConfig
from ..intelligence.llm_client import LLMClient, create_llm_client
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentFieldRepository, DocumentRepository

log = structlog.get_logger()

DEFAULT_EXTRACTION_PROMPT = """Extract structured metadata from this document.

Document content:
{content}

Extract:
1. **title** - A short, human-readable title for this document (max 100 chars). Infer from headers, subject lines, or content.
2. Document type (tax_return, invoice, receipt, contract, insurance_policy, bank_statement, utility_bill, medical_record, other)
3. Document date (the date this document refers to, not when it was created or scanned)
4. Category (tax, financial, medical, insurance, legal, personal, work, utility, other)
5. Monetary amounts with labels (e.g., total_tax, premium, invoice_total)
6. Key entities (organizations, people, reference numbers)

Return JSON only:
{{
  "title": "Tax Return 2023 - Finanzamt Fürth",
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
        title: str | None = None,
        document_type: str | None = None,
        document_date: str | None = None,
        category: str | None = None,
        amounts: list[dict] | None = None,
        entities: list[dict] | None = None,
        confidence: float = 1.0,
    ):
        self.title = title
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
            title=data.get("title"),
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
        if not self.config.extraction.enabled:
            log.debug("Extraction disabled")
            return None

        llm = self._get_llm_client()
        if not llm:
            log.debug("No LLM configured for extraction", document_id=document_id)
            return None

        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)
            field_repo = DocumentFieldRepository(session)

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
                prompt_template = (
                    self.config.extraction.prompt_template
                    or DEFAULT_EXTRACTION_PROMPT
                )
                prompt = prompt_template.format(content=content[:4000])
                response = await llm.generate_json(prompt)

                result = ExtractionResult.from_dict(response)

                # Delete old fields (for re-extraction)
                await field_repo.delete_for_document(document_id)

                # Store extracted amounts
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

                # Store extracted entities
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
                updates: dict[str, Any] = {}
                if result.title:
                    updates["title"] = result.title[:512]
                if result.category:
                    updates["category"] = result.category
                if result.document_date:
                    try:
                        updates["document_date"] = date.fromisoformat(result.document_date)
                    except ValueError:
                        pass
                if updates:
                    await doc_repo.update(doc, **updates)

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
        """Aggregate monetary amounts across documents."""
        async with get_session() as session:
            field_repo = DocumentFieldRepository(session)

            from_date = date.fromisoformat(date_from) if date_from else None
            to_date = date.fromisoformat(date_to) if date_to else None

            agg_result = await field_repo.aggregate_amounts(
                field_name=field_name,
                category=category,
                date_from=from_date,
                date_to=to_date,
                currency=currency,
                min_confidence=min_confidence,
            )

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
                "title": doc.title or doc.original_filename,
                "category": doc.category,
                "document_date": str(doc.document_date) if doc.document_date else None,
                "fields": [
                    {
                        "name": f.field_name,
                        "type": f.field_type,
                        "value": f.value_number if f.value_number is not None else (f.value_text or f.value_date),
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
        """Re-extract all ready documents. Returns count processed."""
        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            docs, total = await doc_repo.list_documents(
                status="ready", per_page=10000
            )

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
