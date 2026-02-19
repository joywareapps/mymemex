# MyMemex TODO

Bugs, issues, and improvements to address.

---

## Priority: High

- [x] **Joyware Apps Organization Website**
  - **Current state:** ✅ Deployed at https://joywareapps.com/
  - **Location:** `smb://server-tiny-1/joywareapps-htdocs/`
  - **Repo:** `~/code/joyware-website` (separate repo)
  - Completed: 2026-02-18

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
  - Should warn user: "No config file found. Using defaults. Run `mymemex init` to configure."
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

- [x] **Feature: Demo version of MyMemex** ✅ COMPLETE
  - **Live at:** https://mymemex.app/ui/
  - **Implementation:** `DEMO_MODE=true` environment variable
  - **Done:**
    - Demo middleware blocks write operations
    - Upload button hidden, demo banner shown
    - Read-only admin panel
    - Deployed to mymemex.app
    - Synthetic documents seeded (invoices, receipts, tax docs, etc.)
  
  **Remaining:**
  - [ ] Set up periodic demo reset (cron job)
    - "See how AI extracted the tax amounts"
    - "Filter by category: Receipts"
  - Pre-populated search examples (clickable chips)
  - Watermark demo documents: "SAMPLE DATA"
  
  **Security Considerations:**
  - Rate limiting (prevent abuse)
  - No MCP access (demo user can't access API)
  - Session timeout (15-30 min)
  - Block file downloads (view only)
  - No real user data ever (all synthetic)
  
  **Call-to-Action:**
  - Top banner with "Get Your Own" button
  - Link to GitHub repo + Docker instructions
  - Email signup for Mac app waitlist
  
  **Technical Approach:**
  - Feature flags: `DEMO_MODE=true`, `ALLOW_UPLOADS=false`
  - Demo user seeded in database
  - Sample data loaded on startup if empty
  - Cron job to reset database periodically
  - Separate Docker image: `ghcr.io/joywareapps/mymemex:demo`
  
  **Hosting Options:**
  - Cloudflare Workers (serverless, but needs DB)
  - Railway/Fly.io (easiest for Docker + persistent DB)
  - Your existing server-tiny-1
  
  **Metrics to Track:**
  - Demo page views
  - Search queries performed
  - Conversion to GitHub stars / email signups
  
  **Future Enhancements:**
  - Multiple demo personas (personal finance, small business, researcher)
  - Interactive onboarding quiz → personalized demo data
  - Export demo settings to user's own instance

- [ ] **Feature: Delete document**
  - API endpoint: `DELETE /api/v1/documents/{id}`
  - MCP tool: `delete_document`
  - Web UI: Delete button with confirmation
  - Should delete: document record, chunks, FTS entries, extracted fields
  - Keep file on disk (or add option to delete file too)

- [ ] **Feature: Reprocess document**
  - Re-run ingestion + classification + extraction pipeline
  - Useful when new features added (e.g., title extraction)
  - API endpoint: `POST /api/v1/documents/{id}/reprocess`
  - MCP tool: `reprocess_document`
  - Web UI: "Reprocess" button in document detail
  - Already exists in IngestService.reprocess() — needs API/MCP/UI exposure

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

- [ ] **Web UI: Dark mode**
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
