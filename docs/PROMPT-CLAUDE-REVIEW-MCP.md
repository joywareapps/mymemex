# Prompt: Claude Review of MCP-First Architecture Plan

## Your Task

Review the MCP-first architecture plan I created and provide critical feedback. Identify any issues, gaps, or improvements needed before we start implementation.

## Context

Librarian is a document intelligence platform with M1-M6 complete:
- File watching, deduplication, SQLite metadata
- PDF text extraction + OCR fallback (Tesseract)
- Semantic search (Ollama + ChromaDB)
- REST API (FastAPI) + CLI (Typer)
- 83 tests passing

User wants to prioritize MCP (Model Context Protocol) to get conversational access via Claude Desktop/OpenClaw without building a custom chat UI.

## Files to Review

1. **docs/MILESTONES.md** — Updated roadmap with MCP as M7
2. **docs/MCP-SPEC.md** — MCP tool/resource specifications
3. **docs/MULTI-USER-SPEC.md** — Shared library with ownership tracking
4. **docs/ARCHITECTURE.md** — Added ADR-007 for MCP-first

## Key Decisions Made

1. **M7 (MCP Server) first** — Expose capabilities via MCP before Web UI
2. **Chat UI deferred to M12** — Not needed if MCP works with external clients
3. **Upload via MCP included** — `upload_document` tool places files in inbox
4. **Multi-user (M10)** — Shared library, ownership tagging, NER detection

## Questions for Claude

### 1. MCP Architecture
- Is the tool set comprehensive enough? Missing anything critical?
- Should MCP be a separate process or integrated into main FastAPI?
- Is the `upload_document` via MCP approach sound (base64 to inbox)?
- Any issues with the transport strategy (stdio + HTTP/SSE)?

### 2. Roadmap Logic
- Is M7 → M8 → M9 → M10 → M11 → M12 → M13 the right order?
- Can any milestones be parallelized?
- Are effort estimates realistic (M7: 1 week, M8: 2-3 weeks)?
- Any missing dependencies between milestones?

### 3. Multi-User Design
- Is shared library + ownership tagging the right approach (vs separate libraries)?
- Is NER-based ownership detection worth pursuing or too complex?
- Should M10 come before or after Web UI (M8)?
- Is the privacy model adequate (shared by default, private opt-in)?

### 4. MCP Integration Details
- How should user context be passed from MCP clients (Claude Desktop, OpenClaw)?
- Should MCP tools support pagination the same way as REST API?
- Are error codes comprehensive enough?
- Any security concerns with the authentication model?

### 5. Implementation Gotchas
- What's the simplest path to get M7 working for initial testing?
- Should we start with stdio only, or implement both transports from day 1?
- Any known issues with the Python MCP SDK we should plan for?
- How should we handle graceful degradation when Ollama is unavailable?

### 6. Alternative Approaches
- Is MCP-first actually the best strategy, or should Web UI come first?
- Could we get conversational access another way (e.g., REST + custom client)?
- Are we over-engineering multi-user for a "family document library" use case?

## Expected Output

1. **Critical review** — What's wrong or missing?
2. **Suggested improvements** — Specific changes to the specs
3. **Risk identification** — What could go wrong?
4. **Implementation advice** — How to start M7 correctly
5. **Alternative perspectives** — What should we consider differently?

## Constraints

- Must work on consumer hardware (NAS, laptop, small server)
- Privacy-first: local processing default, cloud opt-in
- Simple deployment: `docker compose up` should work
- Backward compatible: single-user unaffected by multi-user features

## Format

Please structure your review as:
1. **Overall Assessment** (1-2 paragraphs)
2. **Critical Issues** (must fix before implementation)
3. **Suggested Improvements** (nice to have)
4. **Implementation Recommendations** (how to start)
5. **Alternative Approaches** (other options to consider)

Be direct and critical — I'd rather catch problems now than during implementation.
