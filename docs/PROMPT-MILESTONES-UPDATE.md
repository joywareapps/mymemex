# Prompt: Update Librarian Milestones with MCP-First Architecture

**Task:** Evaluate proposed changes and update Librarian's roadmap and architecture documents.

---

## Background

Librarian has completed M1-M6:
- ✅ Core infrastructure (config, CLI, database)
- ✅ File watching and deduplication
- ✅ Text extraction (PyMuPDF + Tesseract OCR)
- ✅ Search (FTS5 keyword + ChromaDB semantic + hybrid)
- ✅ REST API (FastAPI)

We're now planning next milestones with a key architectural shift: **MCP-first approach**.

---

## Proposed Changes

### 1. MCP Server as M7 (Priority)

Build a Model Context Protocol (MCP) server that exposes Librarian's capabilities:

**MCP Tools:**
```
search_documents(query, mode="keyword|semantic|hybrid", limit=10)
  → Returns matching documents/chunks

get_document(document_id)
  → Returns document metadata + content chunks

list_documents(filter=None, tag=None, limit=50, offset=0)
  → Returns paginated document list

add_tag(document_id, tag)
  → Adds tag to document

remove_tag(document_id, tag)
  → Removes tag from document

upload_document(file_path_or_content, filename)
  → Places document in watched folder for processing
  → Returns document_id when processed

get_library_stats()
  → Returns document count, tags, storage usage

watch_directory(path)
  → Adds new directory to watch list
```

**MCP Resources:**
```
library://documents
  → All documents (streaming)

library://tags
  → All tags with counts

library://document/{id}
  → Specific document with chunks

library://stats
  → Library statistics
```

**MCP Prompts (optional):**
```
search_and_summarize
  → Search for query and summarize results

compare_documents
  → Compare two or more documents
```

### 2. Revised Milestone Order

```
M7  MCP Server — Expose Librarian via MCP (PRIORITY)
M8  Web UI — Browser-based interface (no built-in chat)
M9  Auto-Tagging — Background classification
M10 Multi-User Support — Shared library with ownership tags
M11 Cloud OCR — Fallback for difficult documents
M12 Chat Interface — Optional built-in chat (separate LLM)
M13 Deployment — Docker, docs, distribution
```

### 3. Multi-User Shared Library (M10)

**Concept:** Single library, multiple users, ownership tracking.

**Use Case:** Family or small team shares one library. Each person can:
- Query "my documents" vs "all documents"
- System auto-tags ownership based on:
  - Document metadata (addressee, recipient)
  - Upload source (who added it)
  - Manual tagging

**Implementation:**
```sql
-- New tables
users (id, name, email, created_at)
document_ownership (document_id, user_id, role, confidence)

-- Query filtering
SELECT * FROM documents d
JOIN document_ownership o ON d.id = o.document_id
WHERE o.user_id = :current_user
```

**Ownership Detection:**
- Named entity recognition for names
- Address field parsing
- Email recipient matching
- Manual assignment

### 4. Upload via MCP

**Simple implementation:** MCP `upload_document` tool:
1. Accepts file content or path
2. Writes to configured "inbox" folder (watched by Librarian)
3. File watcher picks it up, processes normally
4. Returns document_id when ready

**No special upload infrastructure needed.**

### 5. Chat Interface (M12 - Optional, Later)

**Not built into Web UI initially.** Users can:
- Use any MCP-compatible chatbot (Claude Desktop, OpenClaw, etc.)
- Or add M12 later for integrated chat experience

**Requires:**
- Separate LLM endpoint configuration (Ollama model for chat)
- Chat UI component
- Conversation history storage

---

## Your Tasks

### 1. Evaluate This Plan

Review the proposed architecture and identify:
- Missing pieces or dependencies
- Technical risks or challenges
- Better alternatives if you see them
- Estimated effort for each milestone

### 2. Update MILESTONES.md

Revise `/home/gorano/code/librarian/docs/MILESTONES.md`:

- Reorder milestones (MCP first)
- Add detailed descriptions for M7-M13
- Include effort estimates
- Document dependencies between milestones
- Add success criteria for each milestone

### 3. Create MCP-SPEC.md

Create `/home/gorano/code/librarian/docs/MCP-SPEC.md`:

- Full MCP tool definitions with parameters and return types
- MCP resource definitions
- Example requests/responses
- Error handling specification
- Authentication/authorization model (if needed)

### 4. Update ARCHITECTURE.md (if needed)

Add section on MCP architecture:
- How MCP server integrates with existing components
- Transport options (stdio, HTTP/SSE)
- Connection to external chatbots

### 5. Create MULTI-USER-SPEC.md (if appropriate)

If multi-user support is well-defined enough:
- User model
- Ownership detection strategies
- Privacy considerations
- Query filtering approach

---

## Technical Considerations

### MCP Implementation Options

**Python MCP SDK:**
```python
# Option 1: Official Python SDK
from mcp import MCPServer, tool, resource

server = MCPServer("librarian")

@tool
async def search_documents(query: str, mode: str = "hybrid") -> list[dict]:
    ...

# Option 2: FastAPI + MCP adapter
# Use existing FastAPI app, add MCP endpoint
```

**Transport:**
- `stdio` — For local chatbot integration (Claude Desktop)
- `HTTP/SSE` — For remote access (OpenClaw, web apps)

### Multi-User Design Questions

- Should users be authenticated or just named profiles?
- How to handle documents with multiple owners (joint accounts)?
- Can users see each other's documents by default?

### Dependency Graph

```
M7 (MCP) ──────────────────┬─────────────────────┐
                           │                     │
                           ▼                     ▼
M8 (Web UI)         M9 (Auto-Tag)        M10 (Multi-User)
     │                    │                     │
     └────────────────────┴─────────────────────┘
                          │
                          ▼
                   M11 (Cloud OCR)
                          │
                          ▼
                   M12 (Chat UI)
                          │
                          ▼
                   M13 (Deployment)
```

---

## Success Criteria

After your work, we should have:

1. ✅ Clear milestone roadmap with M7 (MCP) as priority
2. ✅ Complete MCP specification ready for implementation
3. ✅ Multi-user design documented (even if high-level)
4. ✅ Architecture updated to reflect MCP-first approach
5. ✅ Effort estimates for planning

---

## Constraints

- Keep existing M1-M6 implementation unchanged
- MCP server should be optional add-on (Librarian works without it)
- Multi-user should not complicate single-user deployments
- Focus on pragmatic, implementable solutions

---

## Files to Create/Update

```
docs/MILESTONES.md          — Update with new roadmap
docs/MCP-SPEC.md            — Create (MCP specification)
docs/ARCHITECTURE.md        — Update (add MCP section)
docs/MULTI-USER-SPEC.md     — Create (if appropriate)
```

---

Please evaluate, then implement. If you have concerns or better ideas, note them before proceeding.
