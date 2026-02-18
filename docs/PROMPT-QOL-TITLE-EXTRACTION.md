# QOL: Extract Document Title from Content

## Problem

Documents currently display their original filename as the title in lists/views. PDF metadata (`doc.metadata.title`) is often empty or generic (e.g., "Microsoft Word - Document1").

Users want to see the **actual document title** inferred from content — e.g., "Tax Return 2023" instead of "scan_001.pdf".

## Goal

Extend the LLM extraction pipeline to extract a meaningful title from document content and save it to `document.title`.

## Current State

### Extraction Prompt (`src/librarian/services/extraction.py`)

```python
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
  "amounts": [...],
  "entities": [...],
  "confidence": 0.92
}}
"""
```

### ExtractionResult Class

```python
class ExtractionResult:
    def __init__(
        self,
        document_type: str | None = None,
        document_date: str | None = None,
        category: str | None = None,
        amounts: list[dict] | None = None,
        entities: list[dict] | None = None,
        confidence: float = 1.0,
    ):
        # No title field currently
```

### Where title is updated (`extract_document()` method)

```python
# Update document metadata
updates: dict[str, Any] = {}
if result.category:
    updates["category"] = result.category
if result.document_date:
    try:
        updates["document_date"] = date.fromisoformat(result.document_date)
    except ValueError:
        pass
if updates:
    await doc_repo.update(doc, **updates)
```

## Required Changes

### 1. Update the extraction prompt

Add title extraction to the prompt:

```
Extract:
1. **title** - A short, human-readable title for this document (max 100 chars). Infer from headers, subject lines, or content.
2. Document type ...
```

Add to JSON schema:
```json
{
  "title": "Tax Return 2023",
  "document_type": "tax_return",
  ...
}
```

### 2. Update ExtractionResult

Add `title` field:

```python
class ExtractionResult:
    def __init__(
        self,
        title: str | None = None,  # NEW
        document_type: str | None = None,
        ...
    ):
        self.title = title
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionResult:
        return cls(
            title=data.get("title"),  # NEW
            document_type=data.get("document_type"),
            ...
        )
```

### 3. Update extract_document() to save title

```python
# Update document metadata
updates: dict[str, Any] = {}
if result.title:  # NEW
    updates["title"] = result.title[:512]  # Truncate to column limit
if result.category:
    updates["category"] = result.category
...
```

### 4. Update tests

Add assertions to `tests/test_extraction.py`:
- Mock LLM response includes `"title": "Test Document Title"`
- Verify `doc.title` is updated after extraction

## Files to Modify

| File | Change |
|------|--------|
| `src/librarian/services/extraction.py` | Add title to prompt, ExtractionResult, and update logic |
| `tests/test_extraction.py` | Add title assertions |

## Constraints

1. **Backward compatible** — if LLM doesn't return title, nothing breaks
2. **Truncate** — title max 512 chars (column limit)
3. **Don't overwrite** — only update if `result.title` is non-empty
4. **Tests pass** — all 139+ tests should still pass

## Example

**Before:**
```
Document: "scan_20231215.pdf"
Title shown: "scan_20231215.pdf"
```

**After:**
```
Document: "scan_20231215.pdf"
Title shown: "Tax Return 2023 - Finanzamt Fürth"
```

## Commands

```bash
cd ~/code/librarian

# Run tests before and after
pytest tests/test_extraction.py -xvs

# Full test suite
pytest --tb=short
```

---

## Note on LLM Model

The LLM must be a **text generation model**, not an embedding model. Ensure config has:

```yaml
llm:
  provider: ollama
  model: llama3.2  # or mistral, qwen2.5, etc. (NOT nomic-embed-text)
  api_base: http://office-pc:11434
```
