# Prompt: Structured Extraction & Aggregation Architecture Review

**Goal:** Review and update architecture documents to support structured data extraction and aggregation queries (e.g., "How much tax did I pay from 2015-2025?").

**Task:** Analyze the proposed feature, review existing architecture, and produce updated architecture documents with implementation recommendations.

---

## Context

Librarian currently has:
- ✅ M1-M6: Core document processing, OCR, semantic search
- ✅ M6.5: Service layer
- ✅ M7: MCP Server (8 tools)
- ✅ M8: Web UI

**Missing capability:** Users cannot query aggregated data across documents. Example queries that should work:
- "How much tax did I pay from 2015-2025?"
- "What's my total insurance premium across all policies?"
- "Show me all medical expenses for 2024"
- "Sum all invoice amounts from vendor X"

---

## Use Case Analysis

### Query: "How much tax did I pay 2015-2025?"

**Required capabilities:**
1. **Document classification** — Identify tax-related documents
2. **Entity extraction** — Extract tax amounts, tax year, tax type
3. **Date filtering** — Filter documents by date range
4. **Aggregation** — Sum amounts across matching documents
5. **Natural language interface** — Parse query and generate answer

**Current system:**
- ❌ No auto-classification (manual tagging only)
- ❌ No entity extraction
- ✅ Date filtering (document.created_at exists)
- ❌ No aggregation tools
- ⚠️ MCP can do basic queries, but not aggregation

---

## Proposed Solution

### Phase 1: Structured Extraction (During Ingestion)

**Extract from each document:**
```json
{
  "document_type": "tax_return",
  "date": "2023-12-31",
  "amounts": [
    {"label": "total_tax", "value": 15234.56, "currency": "EUR"},
    {"label": "taxable_income", "value": 68000.00, "currency": "EUR"}
  ],
  "entities": [
    {"type": "organization", "name": "Finanzamt Fürth"},
    {"type": "category", "name": "Einkommensteuer"}
  ],
  "confidence": 0.92
}
```

**Storage options:**

**Option A: JSON column on documents table**
```sql
ALTER TABLE documents ADD COLUMN extracted_metadata JSON;
```
- Pros: Simple, flexible schema
- Cons: Harder to query, no indexing

**Option B: Separate metadata table**
```sql
CREATE TABLE document_metadata (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    key TEXT NOT NULL,
    value_type TEXT NOT NULL,  -- 'string', 'number', 'date', 'currency'
    value_string TEXT,
    value_number REAL,
    value_date DATE,
    confidence REAL,
    source TEXT  -- 'llm', 'regex', 'heuristic'
);
```
- Pros: Queryable, indexable, typed values
- Cons: More complex, migration needed

**Option C: Hybrid (JSON + extracted columns)**
```sql
ALTER TABLE documents ADD COLUMN document_type TEXT;
ALTER TABLE documents ADD COLUMN document_date DATE;
ALTER TABLE documents ADD COLUMN primary_amount REAL;
ALTER TABLE documents ADD COLUMN currency TEXT;
ALTER TABLE documents ADD COLUMN raw_metadata JSON;
```
- Pros: Common fields indexed, flexible for rest
- Cons: Duplication, need to keep in sync

### Phase 2: Extraction Pipeline

**During ingestion (after OCR/chunking):**
```python
async def extract_metadata(document_id: int, chunks: list[str], config: AppConfig):
    """Extract structured metadata from document content."""
    if not config.llm.provider:
        return None

    # Use LLM to extract
    prompt = f"""
    Analyze this document and extract structured data.
    Document content: {chunks[0][:2000]}  # First chunk

    Extract:
    1. Document type (invoice, tax_return, receipt, contract, etc.)
    2. Primary date (document date, not creation date)
    3. Monetary amounts with labels
    4. Key entities (organizations, people, categories)

    Return JSON: {{"type": "...", "date": "...", "amounts": [...], "entities": [...]}}
    """

    result = await llm_client.generate(prompt)
    metadata = parse_json(result)

    # Store in database
    await doc_repo.update_metadata(document_id, metadata)

    # Auto-tag based on type
    if metadata.get("type"):
        await tag_service.add_tag(document_id, metadata["type"])
```

**LLM options:**
- Local: Ollama (gpt-oss:20b, llama2:7b-chat)
- Cloud: OpenAI, Anthropic (faster, more accurate)

### Phase 3: Aggregation Tools

**New MCP tools:**

```python
# MCP Tool: aggregate_amounts
@mcp.tool()
async def aggregate_amounts(
    document_type: str | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    amount_label: str | None = None,
) -> dict:
    """
    Aggregate monetary amounts across documents.

    Returns: {"total": 15234.56, "count": 5, "currency": "EUR", "documents": [...]}
    """
    ...

# MCP Tool: get_financial_summary
@mcp.tool()
async def get_financial_summary(
    category: str,  # "tax", "insurance", "medical", etc.
    year: int | None = None,
) -> dict:
    """
    Get financial summary for a category.

    Returns: {"total": 50000, "breakdown": {"2023": 15000, "2022": 14000, ...}}
    """
    ...

# MCP Tool: list_document_types
@mcp.tool()
async def list_document_types() -> list[dict]:
    """
    List all document types with counts.

    Returns: [{"type": "invoice", "count": 45}, {"type": "tax_return", "count": 11}]
    """
    ...
```

**New service layer methods:**

```python
class DocumentService:
    async def aggregate_amounts(
        self,
        filters: dict,
        amount_label: str | None = None,
    ) -> dict:
        """Aggregate amounts across filtered documents."""
        ...

    async def get_documents_by_type(
        self,
        doc_type: str,
        date_range: tuple[date, date] | None = None,
    ) -> list[Document]:
        """Get documents of a specific type."""
        ...
```

### Phase 4: RAG Agent (Optional, M12)

**Conversational interface:**
```
User: "How much tax did I pay 2015-2025?"

Agent:
1. Parse query → filters: {type: "tax_return", date: 2015-2025}
2. Call aggregate_amounts()
3. Result: {total: 142567.00, count: 11, currency: "EUR"}
4. Generate answer:
   "Based on 11 tax returns, you paid €142,567 in taxes from 2015-2025.
   Yearly breakdown:
   - 2023: €15,234
   - 2022: €14,890
   - ...
   Sources: [tax_return_2023.pdf, tax_return_2022.pdf, ...]"
```

---

## Architecture Questions

### 1. Storage Schema

Which option is best for metadata storage?
- A: JSON column
- B: Separate table with typed values
- C: Hybrid (extracted columns + JSON)

**Considerations:**
- Query performance (filtering, aggregation)
- Migration complexity
- Flexibility for future metadata types
- SQLite compatibility

### 2. Extraction Timing

When should extraction happen?
- **Option A:** During ingestion (adds latency)
- **Option B:** Background task after document is "ready"
- **Option C:** On-demand (only when user queries)

**Considerations:**
- Ingestion speed
- LLM API costs
- Immediate availability

### 3. LLM Provider

Which LLM for extraction?
- **Local (Ollama):** Private, no cost, slower, less accurate
- **Cloud (OpenAI/Anthropic):** Fast, accurate, costs money, data leaves machine

**Considerations:**
- Privacy requirements
- Cost per document
- Accuracy requirements

### 4. Fallback Strategy

What if LLM extraction fails?
- **Option A:** Retry with different LLM
- **Option B:** Use regex/heuristics for common patterns
- **Option C:** Leave unstructured (user can query via RAG)

### 5. Milestone Placement

Where does this fit in the roadmap?
- **M9 (Auto-Tagging):** Extend to include extraction
- **M10 (Multi-User):** Before or after?
- **New M10:** Dedicated milestone for structured extraction

---

## Existing Architecture Review

Please review these files and update as needed:
- `docs/ARCHITECTURE.md` — Add structured extraction component
- `docs/MILESTONES.md` — Add or update milestone for this feature
- `docs/MCP-SPEC.md` — Add new aggregation tools
- `src/librarian/storage/models.py` — Add metadata storage
- `src/librarian/services/document.py` — Add aggregation methods

---

## Deliverables

Please produce:

1. **Updated ARCHITECTURE.md**
   - Add "Structured Extraction" component to diagram
   - Document storage schema decision
   - Document extraction pipeline

2. **Updated MILESTONES.md**
   - Decide: Extend M9 or create new M10?
   - Define deliverables and success criteria

3. **Updated MCP-SPEC.md**
   - Add aggregation tool specifications
   - Document usage examples

4. **New ADR (Architecture Decision Record)**
   - Document decisions on:
     - Storage schema choice
     - Extraction timing
     - LLM provider strategy
     - Fallback approach

5. **Implementation recommendations**
   - Which files to modify
   - New files to create
   - Migration strategy for existing documents

---

## Constraints

- Must work with SQLite (no PostgreSQL-only features)
- Must support offline operation (Ollama fallback)
- Must not break existing functionality
- Should be optional (users can disable extraction)
- Must handle documents without extractable data

---

## Success Criteria

After implementation:
- [ ] Documents are auto-classified during ingestion
- [ ] Key entities (amounts, dates, organizations) are extracted
- [ ] Users can query aggregated data via MCP
- [ ] "How much tax did I pay 2015-2025?" returns accurate answer
- [ ] Extraction works offline with local Ollama
- [ ] Existing documents can be re-processed for extraction

---

## Example Queries to Support

1. **Tax aggregation:**
   - "How much tax did I pay from 2015-2025?"
   - "What was my taxable income in 2023?"

2. **Insurance:**
   - "What's my total insurance premium across all policies?"
   - "List all insurance policies with coverage amounts"

3. **Medical:**
   - "What were my total medical expenses in 2024?"
   - "Show all dental expenses"

4. **General:**
   - "Sum all amounts from vendor X"
   - "What's the total value of all contracts?"
   - "Show me all documents from organization Y"

---

## References

- Existing docs: `docs/ARCHITECTURE.md`, `docs/MILESTONES.md`, `docs/MCP-SPEC.md`
- Current models: `src/librarian/storage/models.py`
- Current services: `src/librarian/services/`
- MCP server: `src/librarian/mcp/`
