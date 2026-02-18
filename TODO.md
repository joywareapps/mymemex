# Librarian TODO

Bugs, issues, and improvements to address.

---

## Priority: High

- [x] **Database lock on concurrent uploads**
  - Fixed: Increased `busy_timeout` from 5s to 30s
  - WAL mode already enabled
  - SQLite handles concurrent reads, but writes serialize

- [x] **Ollama endpoint configuration**
  - Fixed: Added `llm.api_base` to config.yaml
  - Default: `http://localhost:11434`
  - User configured: `http://office-pc:11434`

- [ ] **Show warning message when running without config**
  - Currently silently uses defaults with empty watch directories
  - Should warn user: "No config file found. Using defaults. Run `librarian init` to configure."
  - Applies to: `serve` and `mcp serve` commands

- [x] **Optimize database lock duration on uploads**
  - Done: Added semaphore for ingestion pipeline (2026-02-18)
  - `IngestionConfig.max_concurrent` (default 2, range 1-10)
  - Module-level semaphore limits concurrent SQLite writes
  - Tests: `test_concurrency.py` verifies limit respected

- [x] **Startup recovery for documents stuck in "processing" status**
  - Implemented: `find_stuck_processing()` in DocumentRepository
  - On startup: Find documents in "processing" without active task
  - Reset to "pending" and re-queue for processing
  - Test: `test_find_stuck_processing()` verifies behavior
  - Currently silently uses defaults with empty watch directories
  - Should warn user: "No config file found. Using defaults. Run `librarian init` to configure."
  - Applies to: `serve` and `mcp serve` commands

---

## Priority: Medium

- [x] **Feature: Delete document**
  - API endpoint: `DELETE /api/v1/documents/{id}`
  - MCP tool: `delete_document`
  - Web UI: Delete button with confirmation
  - Should delete: document record, chunks, FTS entries, extracted fields
  - Keep file on disk (or add option to delete file too)

- [x] **Feature: Reprocess document**
  - Re-run ingestion + classification + extraction pipeline
  - Useful when new features added (e.g., title extraction)
  - API endpoint: `POST /api/v1/documents/{id}/reprocess`
  - MCP tool: `reprocess_document`
  - Web UI: "Reprocess" button in document detail
  - Already exists in IngestService.reprocess() — needs API/MCP/UI exposure

- [x] **Web UI: Show extracted title in document grid**
  - Display `doc.title` (extracted from content) instead of `original_filename`
  - Fall back to filename if no title extracted
  - Applies to: document list, search results, detail view
  - Depends on: title extraction prompt being implemented

- [ ] **Web UI: Empty state improvements**
  - Show setup instructions when no documents exist
  - Link to upload page
  - Show "Configure watch directory" prompt if empty

- [ ] **CLI: `librarian init` should create config file**
  - Currently only shows config location
  - Should create default config with watch directory prompt

- [ ] **MCP: Better error messages**
  - Tool errors should be user-friendly, not stack traces
  - Include suggestion for common issues

---

## Priority: Low (Gemini-Suitable)

These tasks are good candidates for Gemini CLI delegation (large context, simple implementation):

- [x] **Web UI: Dark mode**
  - Tailwind dark: variant support
  - Toggle in settings
  - Run: `gemini "Add dark mode to the Web UI using Tailwind dark: variants"`

- [ ] **Web UI: Keyboard shortcuts**
  - `/` to focus search
  - `?` to show help
  - `j/k` to navigate results

- [ ] **Search: Result highlighting**
  - Highlight matching terms in search results
  - Semantic matches show context

---

## Completed

- [x] M8: Web UI basic implementation
- [x] M7.5: OpenClaw skill
- [x] M7: MCP Server
- [x] M6.5: Service Layer Extraction
- [x] M1-M6: Core features

---

## Notes

- Move completed items to "Completed" section
- Add priority labels: High/Medium/Low
- Link to GitHub issues when created
