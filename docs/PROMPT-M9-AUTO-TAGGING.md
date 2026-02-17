# M9: Auto-Tagging Implementation

**Goal:** Automatically classify and tag documents based on content using LLM inference.

**Prerequisites:**
- ✅ M1-M6: Core document processing, OCR, semantic search
- ✅ M6.5: Service layer
- ✅ M7: MCP Server
- ✅ `is_auto` flag exists in `document_tags` table
- ✅ `TaskType.CLASSIFY` exists in queue

---

## Overview

Add LLM-based document classification that automatically tags documents during ingestion. This is the foundation for M9.5 (Structured Extraction) which extends classification to extract structured data.

**Key features:**
1. **Classification pipeline** — LLM categorizes documents on ingest
2. **Auto-tagging** — Apply tags with `is_auto=True` flag
3. **Confidence thresholds** — Only apply tags above configurable threshold
4. **Bulk re-tag** — Re-classify existing documents

---

## Architecture

### Flow

```
Document Ingestion
    │
    ▼
Text Extraction + Chunking
    │
    ▼
Enqueue CLASSIFY task
    │
    ▼
Classification Worker
    │
    ├─► LLM Classify (Ollama/OpenAI/Anthropic)
    │       │
    │       ▼
    │   Extract tags + confidence
    │       │
    │       ▼
    │   Apply tags with is_auto=True
    │
    ▼
Document ready with auto-tags
```

---

## Implementation Steps

### Step 1: Add Classification Config

**File:** `src/librarian/config.py`

Add classification configuration to `LLMConfig` or create new `ClassificationConfig`:

```python
class ClassificationConfig(BaseModel):
    """Document classification configuration."""

    enabled: bool = True
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tags: int = Field(default=5, ge=1, le=20)
    model: str = ""  # Override LLM model for classification
    prompt_template: str = ""  # Custom classification prompt
```

Update `AppConfig`:
```python
class AppConfig(BaseSettings):
    # ... existing fields ...
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
```

**Config file example:**
```yaml
llm:
  provider: ollama
  model: llama2:7b-chat
  api_base: http://office-pc:11434

classification:
  enabled: true
  confidence_threshold: 0.7
  max_tags: 5
```

---

### Step 2: Create LLM Client Abstraction

**File:** `src/librarian/intelligence/llm_client.py`

Abstract LLM interface supporting multiple providers:

```python
"""LLM client abstraction for classification and extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from ..config import LLMConfig

log = structlog.get_logger()


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text completion."""
        ...

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON completion."""
        ...


class OllamaClient(LLMClient):
    """Ollama LLM client."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.api_base
        self.model = config.model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text via Ollama API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        response = await self._client.post(
            f"{self.base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON via Ollama API."""
        import json

        text = await self.generate(prompt, system=system, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse LLM JSON", error=str(e), text=text[:200])
            raise ValueError(f"Invalid JSON from LLM: {e}")


class OpenAIClient(LLMClient):
    """OpenAI LLM client."""

    def __init__(self, config: LLMConfig, api_key: str):
        self.config = config
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Generate text via OpenAI API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model or "gpt-4o-mini",
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate JSON via OpenAI API."""
        import json

        text = await self.generate(prompt, system=system, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.error("Failed to parse OpenAI JSON", error=str(e))
            raise ValueError(f"Invalid JSON from OpenAI: {e}")


def create_llm_client(config: LLMConfig, api_key: str | None = None) -> LLMClient:
    """Create LLM client based on config."""
    if config.provider == "ollama":
        return OllamaClient(config)
    elif config.provider == "openai":
        if not api_key:
            raise ValueError("OpenAI API key required")
        return OpenAIClient(config, api_key)
    elif config.provider == "anthropic":
        # TODO: Implement Anthropic client
        raise NotImplementedError("Anthropic client not yet implemented")
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")
```

---

### Step 3: Create Classifier

**File:** `src/librarian/intelligence/classifier.py`

Document classification logic:

```python
"""Document classification using LLM."""

from __future__ import annotations

from typing import Any

import structlog

from ..config import AppConfig, ClassificationConfig, LLMConfig
from .llm_client import LLMClient, create_llm_client

log = structlog.get_logger()

# Default classification prompt
DEFAULT_CLASSIFICATION_PROMPT = """Analyze this document and classify it.

Document content:
{content}

Instructions:
1. Identify the document type (e.g., invoice, tax_return, receipt, contract, medical_record, insurance_policy, bank_statement, utility_bill, other)
2. Extract relevant tags (e.g., financial, legal, medical, personal, work, insurance, tax)
3. Assign confidence scores (0.0-1.0)

Return JSON:
{{
  "document_type": "type_here",
  "type_confidence": 0.95,
  "tags": [
    {{"name": "tag1", "confidence": 0.9}},
    {{"name": "tag2", "confidence": 0.8}}
  ],
  "summary": "Brief 1-2 sentence description"
}}
"""


class ClassificationResult:
    """Result of document classification."""

    def __init__(
        self,
        document_type: str,
        type_confidence: float,
        tags: list[dict[str, Any]],
        summary: str,
    ):
        self.document_type = document_type
        self.type_confidence = type_confidence
        self.tags = tags
        self.summary = summary

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassificationResult:
        """Create from LLM response dict."""
        return cls(
            document_type=data.get("document_type", "other"),
            type_confidence=data.get("type_confidence", 0.0),
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
        )


class DocumentClassifier:
    """Classify documents using LLM."""

    def __init__(self, config: AppConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.classification_config = config.classification
        self.llm = llm_client or self._create_client()

    def _create_client(self) -> LLMClient:
        """Create LLM client from config."""
        llm_config = LLMConfig(
            provider=self.config.llm.provider,
            model=self.classification_config.model or self.config.llm.model,
            api_base=self.config.llm.api_base,
        )
        return create_llm_client(llm_config)

    async def classify(self, content: str) -> ClassificationResult | None:
        """
        Classify document content.

        Args:
            content: Document text (first N chunks or summary)

        Returns:
            ClassificationResult or None if classification fails
        """
        if not self.classification_config.enabled:
            log.debug("Classification disabled")
            return None

        if not self.config.llm.provider or self.config.llm.provider == "none":
            log.debug("No LLM provider configured")
            return None

        try:
            # Prepare prompt
            prompt_template = (
                self.classification_config.prompt_template
                or DEFAULT_CLASSIFICATION_PROMPT
            )
            prompt = prompt_template.format(content=content[:3000])  # Limit content

            # Call LLM
            response = await self.llm.generate_json(prompt)

            result = ClassificationResult.from_dict(response)

            log.info(
                "Document classified",
                type=result.document_type,
                confidence=result.type_confidence,
                tags=len(result.tags),
            )

            return result

        except Exception as e:
            log.error("Classification failed", error=str(e))
            return None

    def filter_tags_by_confidence(
        self,
        tags: list[dict[str, Any]],
    ) -> list[str]:
        """
        Filter tags by confidence threshold.

        Returns list of tag names that meet the threshold.
        """
        threshold = self.classification_config.confidence_threshold
        max_tags = self.classification_config.max_tags

        filtered = [
            tag["name"]
            for tag in tags
            if tag.get("confidence", 0) >= threshold
        ]

        return filtered[:max_tags]
```

---

### Step 4: Create Classification Service

**File:** `src/librarian/services/classification.py`

Service layer for classification:

```python
"""Classification service."""

from __future__ import annotations

import structlog

from ..config import AppConfig
from ..intelligence.classifier import ClassificationResult, DocumentClassifier
from ..storage.database import get_session
from ..storage.repositories import ChunkRepository, DocumentRepository, TagRepository

log = structlog.get_logger()


class ClassificationService:
    """Service for document classification and auto-tagging."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.classifier = DocumentClassifier(config)

    async def classify_document(self, document_id: int) -> ClassificationResult | None:
        """
        Classify a document and apply auto-tags.

        Args:
            document_id: Document to classify

        Returns:
            ClassificationResult or None if classification failed
        """
        async with get_session() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)
            tag_repo = TagRepository(session)

            # Get document
            doc = await doc_repo.get_by_id(document_id)
            if not doc:
                log.warning("Document not found", document_id=document_id)
                return None

            # Get content (first few chunks)
            chunks = await chunk_repo.get_by_document(document_id, limit=3)
            if not chunks:
                log.warning("No chunks found", document_id=document_id)
                return None

            content = "\n\n".join(chunk.text for chunk in chunks)

            # Classify
            result = await self.classifier.classify(content)
            if not result:
                return None

            # Apply tags
            tags_to_apply = self.classifier.filter_tags_by_confidence(result.tags)

            for tag_name in tags_to_apply:
                try:
                    await tag_repo.add_to_document(
                        document_id,
                        tag_name,
                        is_auto=True,
                    )
                    log.debug(
                        "Auto-tag applied",
                        document_id=document_id,
                        tag=tag_name,
                    )
                except Exception as e:
                    log.error(
                        "Failed to apply tag",
                        document_id=document_id,
                        tag=tag_name,
                        error=str(e),
                    )

            # Also tag with document type
            if result.document_type and result.type_confidence >= self.classification_config.confidence_threshold:
                try:
                    await tag_repo.add_to_document(
                        document_id,
                        result.document_type,
                        is_auto=True,
                    )
                except Exception:
                    pass

            return result

    async def reclassify_all(self) -> int:
        """
        Re-classify all documents.

        Returns count of documents reclassified.
        """
        async with get_session() as session:
            doc_repo = DocumentRepository(session)

            # Get all documents
            docs, total = await doc_repo.list_documents(limit=10000)
            count = 0

            for doc in docs:
                try:
                    result = await self.classify_document(doc.id)
                    if result:
                        count += 1
                except Exception as e:
                    log.error(
                        "Reclassification failed",
                        document_id=doc.id,
                        error=str(e),
                    )

            log.info("Reclassification complete", count=count, total=total)
            return count
```

---

### Step 5: Add Classification Worker

**File:** `src/librarian/processing/pipeline.py` (modify)

Add classification task handler:

```python
from ..services.classification import ClassificationService

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

                # Get next task
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

                    elif task.task_type == TaskType.EMBED:
                        # ... existing embedding logic ...

                    # Mark completed
                    await queue.complete(task.id)

                except Exception as e:
                    log.error(
                        "Task failed",
                        task_id=task.id,
                        error=str(e),
                    )
                    await queue.fail(task.id, str(e))

        except Exception as e:
            log.error("Worker error", worker_id=worker_id, error=str(e))
            await asyncio.sleep(5)
```

Enqueue classification after ingestion:

```python
async def run_ingest_pipeline(
    document_id: int,
    config: AppConfig,
    events: EventManager | None = None,
):
    """Run full ingestion pipeline."""
    # ... existing code ...

    # After document is "ready", enqueue classification
    if config.classification.enabled:
        async with get_session() as session:
            queue = TaskQueue(session)
            await queue.enqueue(
                task_type=TaskType.CLASSIFY,
                payload={"document_id": document_id},
                document_id=document_id,
                priority=3,  # Lower priority than ingestion
            )
            log.info("Classification task enqueued", document_id=document_id)
```

---

### Step 6: Add MCP Tool for Reclassification

**File:** `src/librarian/mcp/tools.py` (modify)

Add reclassification tool:

```python
@mcp.tool()
async def reclassify_documents(
    document_ids: list[int] | None = None,
    all_documents: bool = False,
) -> str:
    """
    Re-classify documents to update auto-tags.

    Args:
        document_ids: Specific document IDs to reclassify
        all_documents: If true, reclassify all documents

    Returns:
        Summary of reclassification results
    """
    from ..services.classification import ClassificationService

    config = get_config()
    service = ClassificationService(config)

    if all_documents:
        count = await service.reclassify_all()
        return f"Reclassified {count} documents"
    elif document_ids:
        results = []
        for doc_id in document_ids:
            result = await service.classify_document(doc_id)
            if result:
                results.append(
                    f"Document {doc_id}: {result.document_type} "
                    f"(confidence: {result.type_confidence:.2f})"
                )
        return "\n".join(results) or "No documents classified"
    else:
        return "Specify document_ids or set all_documents=true"
```

---

### Step 7: Add Tests

**File:** `tests/test_classification.py`

```python
"""Tests for document classification."""

from __future__ import annotations

import pytest

from librarian.config import AppConfig, ClassificationConfig, LLMConfig
from librarian.intelligence.classifier import DocumentClassifier, ClassificationResult
from librarian.services.classification import ClassificationService


@pytest.fixture
def classification_config():
    """Classification config for testing."""
    return ClassificationConfig(
        enabled=True,
        confidence_threshold=0.7,
        max_tags=5,
    )


@pytest.fixture
def app_config(classification_config):
    """App config for testing."""
    return AppConfig(
        classification=classification_config,
        llm=LLMConfig(
            provider="none",  # Disable actual LLM calls
            model="",
        ),
    )


def test_filter_tags_by_confidence(app_config):
    """Test filtering tags by confidence threshold."""
    classifier = DocumentClassifier(app_config)

    tags = [
        {"name": "tax", "confidence": 0.9},
        {"name": "financial", "confidence": 0.8},
        {"name": "low_confidence", "confidence": 0.5},
    ]

    filtered = classifier.filter_tags_by_confidence(tags)

    assert "tax" in filtered
    assert "financial" in filtered
    assert "low_confidence" not in filtered


def test_max_tags_limit(app_config):
    """Test max tags limit."""
    # Override max_tags
    app_config.classification.max_tags = 2

    classifier = DocumentClassifier(app_config)

    tags = [
        {"name": "tag1", "confidence": 0.9},
        {"name": "tag2", "confidence": 0.9},
        {"name": "tag3", "confidence": 0.9},
    ]

    filtered = classifier.filter_tags_by_confidence(tags)

    assert len(filtered) == 2


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


@pytest.mark.asyncio
async def test_classify_disabled(app_config):
    """Test classification when disabled."""
    app_config.classification.enabled = False

    classifier = DocumentClassifier(app_config)
    result = await classifier.classify("some content")

    assert result is None


@pytest.mark.asyncio
async def test_classify_no_llm(app_config):
    """Test classification when no LLM configured."""
    app_config.llm.provider = "none"

    classifier = DocumentClassifier(app_config)
    result = await classifier.classify("some content")

    assert result is None
```

---

### Step 8: Update Config Example

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
  max_tags: 5

ai:
  semantic_search_enabled: true
  embedding_model: nomic-embed-text
```

---

## Success Criteria

- [ ] Classification config added to `AppConfig`
- [ ] LLM client abstraction supports Ollama + OpenAI
- [ ] `DocumentClassifier` classifies documents and returns tags
- [ ] `ClassificationService` applies auto-tags with `is_auto=True`
- [ ] Classification task enqueued after document ingestion
- [ ] Classification worker processes tasks
- [ ] MCP tool `reclassify_documents` works
- [ ] Tests pass for classifier and service
- [ ] Classification works offline with local Ollama
- [ ] Confidence threshold configurable
- [ ] Existing tests still pass

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/librarian/intelligence/__init__.py` | Package init |
| `src/librarian/intelligence/llm_client.py` | LLM client abstraction |
| `src/librarian/intelligence/classifier.py` | Document classification |
| `src/librarian/services/classification.py` | Classification service |
| `tests/test_classification.py` | Classification tests |

## Files to Modify

| File | Changes |
|------|---------|
| `src/librarian/config.py` | Add `ClassificationConfig` |
| `src/librarian/core/queue.py` | Already has `TaskType.CLASSIFY` |
| `src/librarian/processing/pipeline.py` | Add classification worker + enqueue |
| `src/librarian/mcp/tools.py` | Add `reclassify_documents` tool |

---

## Time Estimate

| Task | Time |
|------|------|
| LLM client abstraction | 2-3 hours |
| Classifier implementation | 3-4 hours |
| Classification service | 2-3 hours |
| Worker integration | 2 hours |
| MCP tool | 1 hour |
| Tests | 2-3 hours |
| Documentation | 1 hour |

**Total: 13-18 hours (2-3 days)**

---

## Notes

- Uses existing `is_auto` flag in `document_tags` table
- Classification runs in background after document is "ready"
- Graceful degradation: if LLM unavailable, document still works
- Can be disabled via config: `classification.enabled: false`
- Foundation for M9.5 (Structured Extraction) which extends this pipeline
