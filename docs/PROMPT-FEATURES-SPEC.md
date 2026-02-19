# Prompt: Create Unified Features Specification

**Task:** Review all implemented milestones and create a unified specification document.

**Target File:** `docs/SPECIFICATION.md` (or `FEATURES.md`)

---

## Objective

Create a single, comprehensive specification document that:

1. Documents **all implemented features** from M1-M11
2. Serves as the **source of truth** for what MyMemex does
3. Can be given to new developers/AIs to understand the entire system
4. Is **updated alongside code** when new features are implemented

---

## Scope

### Milestones to Review

| Milestone | Key Artifacts to Review |
|-----------|------------------------|
| M1 | Project skeleton, config system, CLI |
| M2 | SQLite database, SQLAlchemy models |
| M3 | File watcher, deduplication, task queue |
| M4 | Text extraction, chunking, FTS5 search |
| M5 | OCR integration (Tesseract) |
| M6 | Vector embeddings, semantic search |
| M6.5 | Service layer architecture |
| M7 | MCP Server (tools, resources, prompts) |
| M8 | Web UI (pages, components) |
| M9 | Auto-tagging via LLM |
| M9.5 | Structured extraction, aggregation |
| M10 | Deployment, Docker, backup CLI |
| M11 | Admin panel, file policies, user context |

### Files to Analyze

```
# Core architecture
src/mymemex/config.py           # All config options
src/mymemex/storage/models.py   # All database models
src/mymemex/storage/repositories.py
src/mymemex/services/           # All service files
src/mymemex/core/               # Queue, watcher, events

# API & MCP
src/mymemex/api/                # All REST endpoints
src/mymemex/mcp/                # MCP tools, resources, prompts

# Processing
src/mymemex/processing/         # Extractor, chunker, pipeline
src/mymemex/intelligence/       # Classifier, embedder, LLM client

# CLI
src/mymemex/cli/                # All CLI commands

# Web UI
src/mymemex/web/                # Templates, routes

# Existing specs (for reference)
docs/MCP-SPEC.md
docs/M11-SPEC.md
docs/ARCHITECTURE.md
```

---

## Document Structure

The output document should follow this structure:

```markdown
# MyMemex Specification

**Version:** X.Y.Z
**Last Updated:** YYYY-MM-DD
**Test Coverage:** N tests passing

---

## Overview

[1-2 paragraph description of what MyMemex is]

---

## Core Concepts

[Key abstractions: Documents, Chunks, Tags, Users, etc.]

---

## Configuration

### Config File Structure
[All config sections and options]

### Environment Variables
[All supported env vars]

---

## Database Schema

### Tables
[All tables with columns and relationships]

### Key Constraints
[Unique indexes, foreign keys, etc.]

---

## REST API

### Endpoints
[All endpoints organized by domain: documents, search, tags, admin, etc.]

### Authentication
[Current state: none; planned for M12]

---

## MCP Server

### Tools
[All 13+ tools with parameters and return types]

### Resources
[library://tags, library://stats, etc.]

### Prompts
[search_and_summarize, compare_documents]

### Transport Options
[stdio vs HTTP, auth modes]

---

## CLI Commands

[All commands: init, serve, config, backup, mcp serve, etc.]

---

## Web UI

### Pages
[Documents, Search, Tags, Upload, Admin sections]

### Admin Panel
[Settings, Watch Folders, Backup, MCP, Users, Queue, Logs]

---

## Processing Pipeline

### Ingestion Flow
[File detection → extraction → chunking → embedding → classification → extraction]

### File Policies
[keep, rename, move, copy, delete with templates]

---

## LLM Integration

### Classification
[Auto-tagging, categories, confidence thresholds]

### Extraction
[Structured data: amounts, dates, entities]

### User Context
[Person tagging from user profiles]

---

## Search

### Types
[Keyword (FTS5), Semantic (vectors), Hybrid (RRF)]

### Query Syntax
[Supported query patterns]

---

## Deployment

### Docker
[Images, compose files, environment]

### Backup & Restore
[Format, scheduling, retention]

---

## Extensibility

### Adding New MCP Tools
[Pattern for adding tools]

### Adding New Services
[Service layer conventions]

---

## Testing

### Test Categories
[Unit, integration, E2E]

### Running Tests
[Commands and options]
```

---

## Requirements

1. **Exhaustive but readable** — Don't list every function, but document every user-facing feature and API endpoint
2. **Code-accurate** — Read actual code, don't rely on outdated specs
3. **Cross-referenced** — Link to relevant spec files (MCP-SPEC.md, M11-SPEC.md) for details
4. **Update-friendly** — Structure makes it easy to add new sections for M12+
5. **AI-friendly** — Another AI should be able to read this and understand the full system

---

## Process

1. **Read all source files** in scope (don't assume, verify)
2. **Extract actual features** from code, not from memory
3. **Consolidate duplicates** — Many things appear in multiple places (API + MCP + CLI)
4. **Document current state** — Not future plans (those stay in MILESTONES.md)
5. **Generate the document** following the structure above

---

## Output

Create `docs/SPECIFICATION.md` in the mymemex repository.

---

## Post-Creation

After creating the spec:

1. Review for accuracy against actual code
2. Commit with message: `docs: Add unified SPECIFICATION.md for M1-M11`
3. Add to TODO.md: "Keep SPECIFICATION.md updated when adding features"

---

## Future Updates

When implementing M12+:
1. Update SPECIFICATION.md alongside code changes
2. Add new sections for auth, ownership, chat, etc.
3. Keep "Last Updated" and version current
