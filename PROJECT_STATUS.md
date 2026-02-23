# MyMemex - Project Status

**Last Updated:** 2026-02-23
**Phase:** M1-M12 Complete | Production Ready

## Current State

- M1-M12 complete (173+ tests passing)
- Pre-built Docker images (GHCR)
- Cloud LLM support (OpenAI, Anthropic)
- MCP Server with 13 tools
- Backup CLI for database + vectors
- Web UI for document browsing, search, tags, upload
- Admin Panel with full configuration management

## Completed Milestones

| Milestone | Description | Status |
|-----------|-------------|--------|
| **M1** | Project skeleton, config system, CLI | ✅ |
| **M2** | SQLite database, SQLAlchemy models | ✅ |
| **M3** | File watcher, deduplication (SHA-256), task queue | ✅ |
| **M4** | Text extraction (PyMuPDF), chunking, FTS5 search | ✅ |
| **M5** | OCR integration (Tesseract) for scanned PDFs | ✅ |
| **M6** | Vector embeddings + semantic search (Ollama + ChromaDB) | ✅ |
| **M6.5** | Service layer extraction | ✅ |
| **M7** | MCP Server (13 tools, 2 resources, 2 prompts) | ✅ |
| **M7.5** | OpenClaw skill for MyMemex | ✅ |
| **M8** | Web UI (document browser, search, tags, upload) | ✅ |
| **M9** | Auto-Tagging via LLM | ✅ |
| **M9.5** | Structured Extraction & Aggregation | ✅ |
| **M10** | Deployment & Distribution | ✅ |
| **M11** | Admin Panel, File Management & User Context | ✅ |
| **M12** | Multi-User Support with Authentication | ✅ |

## M12 Features

- **Authentication** — Optional JWT login (bcrypt passwords, Bearer token + cookie)
- **Auth enforcement** — `AuthMiddleware` protects admin + write ops; 401 JSON (API) / 302 redirect (UI)
- **Web UI login** — `/ui/login` page with Alpine.js form; nav shows username/sign-out or sign-in
- **User fields** — `password_hash`, `is_admin`, `is_default` on User model
- **Document ownership** — `uploaded_by_user_id`, `document_frequency`, `time_period` fields
- **User-aware AI** — Classification/extraction prompts receive known user names; auto-tags `user:Name`
- **CLI** — `mymemex users create/list`
- **MCP** — `user_filter` on `search_documents` and `list_documents`

## M11 Features

- **Admin Panel** — Settings editor with restart warnings, watch folder management
- **MCP Configuration** — HTTP transport, access tokens, IP whitelist
- **Backup Management** — Scheduled backups, retention policy, restore from UI
- **Post-Ingestion File Policies** — Rename/move/copy/delete after processing
- **User Profiles** — Family members with display name + aliases for LLM context
- **Task Queue UI** — Real-time queue management with cancel/retry
- **Activity & System Logs** — File operations log, system log with filters
- **First-Run Wizard** — Setup prompt when no users exist
- **Same-Origin Admin CORS** — Admin endpoints protected

## M10 Features

- **Pre-built Docker images** — `ghcr.io/joywareapps/mymemex:latest`
- **Cloud LLM support** — OpenAI, Anthropic (for users without Ollama)
- **API key configuration** — Environment variables (`.env` file)
- **Backup CLI** — `mymemex backup create/list/restore`
- **docker-compose.full.yml** — Full stack with Ollama
- **Installation docs** — `docs/INSTALLATION.md`

## Upcoming Milestones

| Milestone | Description |
|-----------|-------------|
| **M13** | Chat Interface |
| **M14** | Cloud OCR Fallback |

## Deployment Options

| Method | Command |
|--------|---------|
| Docker (standalone) | `docker pull ghcr.io/joywareapps/mymemex:latest` |
| Docker Compose | `docker-compose up -d` |
| Full Stack | `docker-compose -f docker-compose.full.yml up -d` |
| pip | `pip install mymemex[ocr,ai,mcp]` |

## MCP Tools Available

| Tool | Description |
|------|-------------|
| `search_documents` | Keyword/semantic/hybrid search |
| `get_document` | Retrieve document details |
| `get_document_text` | Get text by page range |
| `list_documents` | Paginated document listing |
| `add_tag` / `remove_tag` | Tag management |
| `upload_document` | File upload |
| `get_library_stats` | Library statistics |
| `aggregate_amounts` | Sum monetary values across documents |
| `get_extracted_fields` | View extracted metadata |
| `list_document_types` | List auto-classified types |
| `reextract_documents` | Re-run extraction |
| `classify_document` | Manual classification trigger |

## Blockers

None currently.

## Notes

- 173+ tests passing (unit + integration)
- Cloud LLM optional (OpenAI/Anthropic via env vars)
- Local-first: Ollama works offline
- Watch folders now stored in database (not config.yaml)
- Users stored in database with optional JWT authentication (M12)
- See [TODO.md](TODO.md) for known issues
- See [docs/MILESTONES.md](docs/MILESTONES.md) for full roadmap
- See [docs/INSTALLATION.md](docs/INSTALLATION.md) for setup guide
