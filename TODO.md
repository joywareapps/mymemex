# MyMemex TODO

Bugs, issues, and improvements to address.

---

## Priority: High

- [ ] **Show warning message when running without config**
  - Currently silently uses defaults with empty watch directories
  - Should warn user: "No config file found. Using defaults. Run `mymemex init` to configure."
  - Applies to: `serve` and `mcp serve` commands

- [ ] **MCP: HTTP/SSE transport for OpenClaw integration**
  - Current: MCP only supports stdio (Claude Desktop)
  - Goal: Allow OpenClaw to query mymemex via MCP (aggregate_amounts, get_extracted_fields, etc.)
  - Options:
    - Add HTTP/SSE transport to mymemex MCP server
    - OR configure mcporter to expose mymemex MCP via HTTP
  - Required for: Tax queries, document aggregation, extracted field access
  - Depends on: Security hardening (localhost-only, auth)

---

## Documentation

- [ ] **Keep SPECIFICATION.md updated**
  - When adding new features, update `docs/SPECIFICATION.md`
  - Keep version and "Last Updated" current
  - Ensures new developers/AIs can understand the full system

---

## Priority: Medium

- [ ] **Alembic Migrations for Production**
  - **Current state:** No migrations; fresh DB on each reset during development
  - **When:** Add alongside or after user management/auth milestone
  - **Scope:**
    - M11 tables: `users`, `watch_directories`, `mcp_tokens`, `backups`, `file_operations_log`, `system_log`
    - M11 columns: `documents.current_path`, `documents.file_policy_applied`
    - Future: user auth tables, sessions, etc.
  - **Blocker:** Schema must be stable before writing migrations

- [ ] **Web UI: Show extracted title in document grid**
  - Display `doc.title` (extracted from content) instead of `original_filename`
  - Fall back to filename if no title extracted
  - Applies to: document list, search results, detail view
  - Depends on: title extraction prompt being implemented

- [ ] **Web UI: Empty state improvements**
  - Show setup instructions when no documents exist
  - Link to upload page
  - Show "Configure watch directory" prompt if empty

- [ ] **CLI: `mymemex init` should create config file**
  - Currently only shows config location
  - Should create default config with watch directory prompt

- [ ] **MCP: Better error messages**
  - Tool errors should be user-friendly, not stack traces
  - Include suggestion for common issues

---

## Priority: Low (Gemini-Suitable)

These tasks are good candidates for Gemini CLI delegation (large context, simple implementation):

- [ ] **Web UI: Keyboard shortcuts**
  - `/` to focus search
  - `?` to show help
  - `j/k` to navigate results

- [ ] **Search: Result highlighting**
  - Highlight matching terms in search results
  - Semantic matches show context

---

## Completed

- [x] **Joyware Apps Organization Website** (2026-02-18)
- [x] **Database lock & concurrency optimizations** (2026-02-18)
- [x] **Ollama endpoint configuration** (llm.api_base)
- [x] **Startup recovery for documents stuck in "processing"**
- [x] **Feature: Demo version of MyMemex** (mymemex.app)
- [x] **Feature: Delete document** (API/UI/MCP)
- [x] **Feature: Reprocess document** (API/MCP)
- [x] **Web UI: Dark mode** (Tailwind dark variants)
- [x] **Milestone M8:** Web UI basic implementation
- [x] **Milestone M7.5:** OpenClaw skill
- [x] **Milestone M7:** MCP Server
- [x] **Milestone M6.5:** Service Layer Extraction
- [x] **Milestones M1-M6:** Core features

---

## Notes

- Move completed items to "Completed" section
- Add priority labels: High/Medium/Low
- Link to GitHub issues when created
