# MyMemex Specification

**Version:** M12
**Last Updated:** 2026-02-23
**Test Coverage:** 160+ tests passing, 15 skipped (integration tests requiring live Ollama)

---

## Overview

MyMemex is a self-hosted document intelligence platform. It watches designated folders for new files, automatically extracts and indexes their text, applies AI-powered classification and tagging, and makes everything searchable via full-text, semantic, and hybrid search.

The system exposes three interfaces: a REST/Web UI for humans, an MCP (Model Context Protocol) server for AI agents like Claude, and a CLI for administration. All data is stored locally — SQLite for structured data, ChromaDB (optional) for vector embeddings — with no cloud dependencies required to run.

---

## Core Concepts

**Document** — A unique file ingested into the library, identified by content hash (deduplication-safe). Tracks metadata, processing status, AI-extracted fields, and file path history.

**Chunk** — A 1,500-character (max) overlapping segment of a document's text. The unit of full-text and semantic search. Indexed in SQLite FTS5 and (optionally) ChromaDB.

**Tag** — A short label attached to documents. Tags are either manually applied or auto-applied by the LLM classifier. User tags use the `user:{name}` prefix (e.g. `user:Alice`).

**User (M11/M12)** — A named person with optional aliases, optional password (bcrypt), and admin/default flags. Used to inject identity context into LLM classification prompts and (when auth enabled) for login sessions.

**Watch Directory** — A filesystem path monitored by the file watcher. Stored in the database (not config file); each directory has an active/inactive flag and a file policy that determines what happens to source files after ingestion.

**Task** — A unit of background work in the task queue (ingest, classify, embed, extract, OCR). Tasks have priorities, retry logic with exponential backoff, and status tracking.

**File Policy** — What happens to the original file after ingestion: keep it in place, move it to an archive, copy it, rename it using a template, or delete it.

**MCP Token** — A bearer token for authenticating HTTP-transport MCP server requests. Tokens have a `mymemex_` prefix, are stored as SHA-256 hashes, and are shown in full only once on creation.

---

## Configuration

### Config File Search Order

1. Path passed via `--config` CLI flag
2. `MYMEMEX_CONFIG` environment variable
3. `./mymemex.yaml`
4. `./config/config.yaml`
5. `~/.config/mymemex/config.yaml`
6. Built-in defaults

### Environment Variable Overrides

All config fields are overridable via env vars with prefix `MYMEMEX_` and double-underscore nesting:

```
MYMEMEX_SERVER__PORT=9000
MYMEMEX_LLM__PROVIDER=ollama
MYMEMEX_DEBUG=true
```

### Config Sections

#### Top-level `AppConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `debug` | bool | `false` | Debug mode |
| `log_level` | enum | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `watch` | WatchConfig | see below | File watching settings |
| `database` | DatabaseConfig | see below | Database path |
| `server` | ServerConfig | see below | API server host/port |
| `ocr` | OCRConfig | see below | OCR via Tesseract |
| `llm` | LLMConfig | see below | LLM provider |
| `ai` | AIConfig | see below | Embeddings and semantic search |
| `mcp` | MCPConfig | see below | MCP server |
| `classification` | ClassificationConfig | see below | Auto-tagging |
| `extraction` | ExtractionConfig | see below | Structured field extraction |
| `ingestion` | IngestionConfig | see below | Concurrency limits |
| `backup` | BackupConfig | see below | Automated backups |

#### `WatchConfig`

| Field | Type | Default |
|-------|------|---------|
| `file_patterns` | list[str] | `["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif", "*.bmp", "*.webp"]` |
| `ignore_patterns` | list[str] | `["*/.*", "*/.Trash-*", "*/@eaDir/*", "*/#recycle/*"]` |
| `debounce_seconds` | float | `2.0` |
| `max_file_size_mb` | int | `100` |

> Note: Watched directories are managed via the database (Admin → Watch Folders), not this config section.

#### `DatabaseConfig`

| Field | Type | Default |
|-------|------|---------|
| `path` | Path | `./data/mymemex.db` |

#### `ServerConfig`

| Field | Type | Default |
|-------|------|---------|
| `host` | str | `0.0.0.0` |
| `port` | int | `8000` |

#### `OCRConfig`

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `false` |
| `language` | str | `eng` |
| `dpi` | int | `300` |
| `confidence_threshold` | float | `0.7` |

#### `LLMConfig`

| Field | Type | Default |
|-------|------|---------|
| `provider` | enum | `none` — options: `ollama`, `openai`, `anthropic`, `none` |
| `model` | str | `""` |
| `api_base` | str | `http://localhost:11434` |
| `api_key` | str or null | `null` |

#### `AIConfig`

| Field | Type | Default |
|-------|------|---------|
| `embedding_model` | str | `nomic-embed-text` |
| `embedding_dimension` | int | `768` |
| `embedding_batch_size` | int | `8` |
| `semantic_search_enabled` | bool | `false` |

#### `ClassificationConfig`

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | |
| `confidence_threshold` | float | `0.7` | 0.0–1.0 |
| `max_tags` | int | `5` | 1–20 |
| `model` | str | `""` | Override LLM model per-task |
| `prompt_template` | str | `""` | Custom classification prompt |

#### `ExtractionConfig`

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | |
| `min_confidence` | float | `0.5` | 0.0–1.0 |
| `prompt_template` | str | `""` | Custom extraction prompt |

#### `IngestionConfig`

| Field | Type | Default | Constraints |
|-------|------|---------|-------------|
| `max_concurrent` | int | `2` | 1–10 |

#### `MCPConfig`

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `true` |
| `transport` | enum | `stdio` — options: `stdio`, `http` |
| `http.host` | str | `0.0.0.0` |
| `http.port` | int | `8001` |
| `auth.mode` | enum | `none` — options: `none`, `token`, `ip_whitelist`, `both` |
| `auth.ip_whitelist` | list[str] | `[]` |
| `security.allowed_parent_paths` | list[str] | `[]` |
| `security.max_upload_size_mb` | int | `5` |

#### `BackupConfig`

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `false` |
| `schedule` | str (cron) | `0 3 * * *` (3am daily) |
| `retention_days` | int | `30` |
| `destination` | str | `""` |
| `include.database` | bool | `true` |
| `include.vectors` | bool | `true` |
| `include.config` | bool | `true` |
| `include.original_files` | bool | `false` |

#### `AuthConfig` (M12)

| Field | Type | Default |
|-------|------|---------|
| `enabled` | bool | `false` — when false, all endpoints are accessible without authentication |
| `jwt_secret_key` | str | `""` — auto-generated per-session if empty |
| `session_expiry_hours` | int | `24` |

---

## Database Schema

All tables use SQLite via SQLAlchemy 2.0 async ORM. The database file path defaults to `./data/mymemex.db`.

### Table: `documents`

Primary record for each unique file ingested.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `content_hash` | TEXT(64) | Unique; SHA-256 of full file content |
| `quick_hash` | TEXT(48) | xxhash of first 64KB for fast dedup |
| `file_size` | INTEGER | Bytes |
| `original_path` | TEXT(1024) | Path at time of ingestion |
| `original_filename` | TEXT(255) | |
| `mime_type` | TEXT(127) | |
| `status` | TEXT(32) | `pending`, `processing`, `processed`, `failed`, `waiting_llm`, `waiting_ocr` |
| `page_count` | INTEGER | Nullable |
| `language` | TEXT(10) | Nullable |
| `title` | TEXT(512) | Nullable; from PDF metadata or AI extraction |
| `author` | TEXT(255) | Nullable |
| `created_date` | DATETIME | Nullable; from PDF metadata |
| `summary` | TEXT | Nullable; AI-generated |
| `category` | TEXT(64) | Nullable; AI-classified |
| `document_date` | DATE | Nullable; AI-extracted |
| `has_embedding` | BOOLEAN | Default false |
| `embedding_model` | TEXT(64) | Nullable |
| `file_modified_at` | DATETIME | |
| `ingested_at` | DATETIME | Server default now |
| `processed_at` | DATETIME | Nullable |
| `updated_at` | DATETIME | Auto-updated |
| `current_path` | TEXT(1024) | Nullable; updated by file policy |
| `file_policy_applied` | TEXT(32) | Nullable; set once after policy applied |
| `uploaded_by_user_id` | INTEGER FK | Nullable; references `users.id`, SET NULL on delete (M12) |
| `document_frequency` | TEXT(32) | Nullable; `yearly`, `monthly`, `quarterly`, `one-time` (M12) |
| `time_period` | TEXT(20) | Nullable; e.g. `2024`, `2024-03`, `2024-Q1` (M12) |
| `error_count` | INTEGER | Default 0 |
| `last_error` | TEXT | Nullable |

Relationships: `file_paths` (all known paths for this file), `chunks` (text chunks), `tags` (via `document_tags`), `extracted_fields`

### Table: `file_paths`

All filesystem paths where this document's content hash has been seen.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `document_id` | INTEGER FK | CASCADE delete |
| `path` | TEXT(1024) | Unique, indexed |
| `is_primary` | BOOLEAN | Default false |
| `first_seen_at` | DATETIME | |
| `last_seen_at` | DATETIME | |

### Table: `chunks`

Text segments used for full-text and semantic search.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `document_id` | INTEGER FK | CASCADE delete |
| `chunk_index` | INTEGER | |
| `page_number` | INTEGER | Nullable |
| `text` | TEXT | |
| `char_count` | INTEGER | |
| `extraction_method` | TEXT(32) | `pymupdf_native` or `tesseract_ocr` |
| `has_embedding` | BOOLEAN | Default false |
| `vector_id` | TEXT(36) | Unique UUID; links to ChromaDB |

Index: `(document_id, chunk_index)`. FTS5 virtual table created separately for full-text search.

### Table: `tags`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | TEXT(64) | Unique |
| `color` | TEXT(7) | Nullable; hex color e.g. `#ff6b6b` |
| `created_at` | DATETIME | |

### Table: `document_tags` (association table)

| Column | Type | Notes |
|--------|------|-------|
| `document_id` | INTEGER FK PK | CASCADE delete |
| `tag_id` | INTEGER FK PK | CASCADE delete |
| `is_auto` | BOOLEAN | Default false; true = AI-applied |
| `created_at` | DATETIME | |

### Table: `document_fields`

Structured fields extracted by LLM from document content.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `document_id` | INTEGER FK | CASCADE delete |
| `field_name` | TEXT(100) | e.g. `amount`, `vendor`, `date` |
| `field_type` | TEXT(20) | `currency`, `date`, `string`, `number` |
| `value_text` | TEXT | Nullable |
| `value_number` | REAL | Nullable |
| `value_date` | TEXT(20) | Nullable; ISO date |
| `currency` | TEXT(3) | Nullable; e.g. `EUR`, `USD` |
| `confidence` | REAL | Default 1.0 |
| `source` | TEXT(20) | `llm`, `regex`, `manual` |
| `created_at` | DATETIME | |

### Table: `tasks`

Background task queue.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `task_type` | TEXT(64) | See TaskType enum |
| `payload` | TEXT | JSON string |
| `priority` | INTEGER | Higher = runs first |
| `status` | TEXT(32) | `pending`, `running`, `completed`, `failed`, `waiting_llm`, `cancelled` |
| `document_id` | INTEGER FK | Nullable; CASCADE delete |
| `attempt_count` | INTEGER | Default 0 |
| `max_attempts` | INTEGER | Default 3 |
| `error_message` | TEXT | Nullable |
| `created_at` | DATETIME | |
| `started_at` | DATETIME | Nullable |
| `completed_at` | DATETIME | Nullable |
| `next_retry_at` | DATETIME | Nullable; exponential backoff |

### Table: `users`

Known people for LLM context injection and authentication (M12).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | TEXT(255) | |
| `aliases` | TEXT | JSON array of strings |
| `password_hash` | TEXT | Nullable; `NULL` means no auth required for this user |
| `is_admin` | BOOLEAN | Default `false` |
| `is_default` | BOOLEAN | Default `false` |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | Auto-updated |

### Table: `watch_directories`

Filesystem folders to monitor, managed via DB (not config file).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `path` | TEXT(1024) | Unique |
| `patterns` | TEXT | JSON array; overrides global `watch.file_patterns` if set |
| `is_active` | BOOLEAN | Default true; false = paused |
| `file_policy` | TEXT(32) | Default `keep_original`; see FilePolicy enum |
| `archive_path` | TEXT(1024) | Nullable; used by `move_to_archive` / `copy_organized` |
| `rename_template` | TEXT(512) | Nullable; used by `rename_template` policy |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | Auto-updated |

### Table: `mcp_tokens`

API tokens for MCP HTTP transport authentication.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | TEXT(255) | Human-readable label |
| `token_hash` | TEXT(64) | Unique; SHA-256 of full token |
| `token_prefix` | TEXT(20) | Display-only prefix (e.g. `mymemex_abc12345`) |
| `created_at` | DATETIME | |
| `last_used_at` | DATETIME | Nullable |
| `is_active` | BOOLEAN | Default true |

### Table: `backups`

Backup run history.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `filename` | TEXT(255) | e.g. `mymemex-backup-2026-02-19-030000.tar.gz` |
| `path` | TEXT(1024) | Absolute path on disk |
| `size_bytes` | INTEGER | Nullable |
| `status` | TEXT(32) | `pending`, `success`, `failed` |
| `error_message` | TEXT | Nullable |
| `created_at` | DATETIME | |
| `completed_at` | DATETIME | Nullable |

### Table: `file_operation_logs`

Audit trail of file system operations from file policies.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `document_id` | INTEGER FK | Nullable; SET NULL on document delete |
| `operation` | TEXT(64) | e.g. `move`, `copy`, `delete`, `policy:keep_original` |
| `source_path` | TEXT(1024) | |
| `destination_path` | TEXT(1024) | Nullable |
| `status` | TEXT(32) | `success`, `failed` |
| `error_message` | TEXT | Nullable |
| `created_at` | DATETIME | |

### Table: `system_logs`

Application event log, capped at 10,000 entries.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `level` | TEXT(16) | `debug`, `info`, `warning`, `error` |
| `component` | TEXT(64) | e.g. `watcher`, `backup`, `pipeline` |
| `message` | TEXT | |
| `details` | TEXT | Nullable; JSON |
| `created_at` | DATETIME | |

### `FilePolicy` Enum

| Value | Behavior |
|-------|----------|
| `keep_original` | No-op; source file stays in place |
| `delete_original` | Source file deleted after ingestion |
| `move_to_archive` | Source moved to `archive_path` |
| `copy_organized` | Source copied to `archive_path` |
| `rename_template` | Source renamed in-place using `rename_template` |

**Template variables** (for `rename_template` and `copy_organized`): `{date}`, `{year}`, `{month}`, `{day}`, `{category}`, `{title}`, `{original_name}`, `{ext}`, `{hash}`

---

## REST API

Base path: `/api/v1`

### Authentication

Admin endpoints (`/api/v1/admin/*`) are protected by same-origin middleware: cross-origin requests (different `Origin` header) receive `403 Forbidden`.

**M12 Auth API** (`auth.enabled=true` required for login/me to enforce checks):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Accepts `{name, password}`, returns `{access_token, token_type, user}` and sets `access_token` cookie |
| `POST` | `/api/v1/auth/logout` | Clears the `access_token` cookie |
| `GET`  | `/api/v1/auth/me` | Returns current user or `{authenticated:false, auth_enabled:false}` when auth disabled |

When `auth.enabled=false` (default), all existing endpoints work without authentication.

### Documents — `/api/v1/documents`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/documents` | List documents with filtering and pagination |
| GET | `/documents/{id}` | Get document details with all chunks |
| PATCH | `/documents/{id}` | Update metadata (title, category, tags) |
| DELETE | `/documents/{id}` | Remove from index (source file untouched) |
| POST | `/documents/{id}/reprocess` | Re-run ingestion pipeline |
| POST | `/documents/upload` | Upload file (multipart/form-data) |

**GET /documents query parameters:**

| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number |
| `per_page` | `50` | Max 200 |
| `status` | — | Filter by status |
| `category` | — | Filter by AI category |
| `tag` | — | Filter by tag name |
| `q` | — | Keyword filter on title/filename |
| `sort_by` | `ingested_at` | Sort field |
| `sort_order` | `desc` | `asc` or `desc` |

**PATCH /documents/{id} body:**
```json
{
  "title": "string",
  "category": "string",
  "add_tags": ["string"],
  "remove_tags": ["string"]
}
```

### Search — `/api/v1/search`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search/keyword` | Full-text keyword search (SQLite FTS5) |
| GET | `/search/semantic` | Semantic vector search (requires Ollama + ChromaDB) |
| GET | `/search/hybrid` | Combined keyword + semantic with RRF merge |

**GET /search/keyword:** `q` (required), `page` (default 1), `per_page` (default 20, max 100)

**GET /search/semantic:** `q` (required), `limit` (default 10, max 100)

**GET /search/hybrid:** `q` (required), `limit` (default 10, max 100), `keyword_weight` (default 0.3, range 0.0–1.0)

Semantic and hybrid search raise `503 Service Unavailable` when disabled or Ollama is unreachable. Hybrid search falls back gracefully to keyword-only.

### Tags — `/api/v1/tags`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tags` | List all tags with document counts |
| POST | `/tags` | Create a tag |
| DELETE | `/tags/{id}` | Delete a tag (unlinks from all documents) |

**POST /tags body:** `{ "name": "string", "color": "#rrggbb" }`

### System — `/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Health, uptime, queue stats, storage stats |
| GET | `/queue` | Task queue counts by status |
| WS | `/ws` | WebSocket for real-time events |

**WebSocket events broadcast:** `document.discovered`, `document.processing`, `document.completed`, `document.error`, `document.duplicate`

### Admin — `/api/v1/admin`

All admin endpoints require same-origin requests (browser-initiated from the same host/port).

#### Setup

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/setup/status` | `{"needs_setup": bool}` — true when users table is empty |

#### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users` | List all users |
| POST | `/admin/users` | Create a user (201) |
| GET | `/admin/users/{id}` | Get a user |
| PATCH | `/admin/users/{id}` | Update a user |
| DELETE | `/admin/users/{id}` | Delete a user (204) |

**POST/PATCH body:** `{ "name": "string", "aliases": ["string"] }`

#### Watch Folders

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/watch-folders` | List all watch folders |
| POST | `/admin/watch-folders` | Create a watch folder (201) |
| GET | `/admin/watch-folders/{id}` | Get a watch folder |
| PATCH | `/admin/watch-folders/{id}` | Update a watch folder |
| DELETE | `/admin/watch-folders/{id}` | Delete a watch folder (204) |
| POST | `/admin/watch-folders/{id}/rescan` | Trigger rescan of all files in folder |

**POST body:** `{ "path": "string", "patterns": [], "is_active": true, "file_policy": "keep_original", "archive_path": null, "rename_template": null }`

Creating/deleting a watch folder dynamically updates the live watcher without restart.

#### MCP Tokens

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/mcp/tokens` | List all tokens (prefix only, never hash) |
| POST | `/admin/mcp/tokens` | Create a token — full token returned once (201) |
| DELETE | `/admin/mcp/tokens/{id}` | Revoke a token (204) |

**POST body:** `{ "name": "string" }`

#### Backup

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/backup/config` | Get backup configuration |
| GET | `/admin/backup/history` | List backup history (paginated) |
| POST | `/admin/backup/run` | Trigger immediate backup (202 Accepted) |
| GET | `/admin/backup/{id}/download` | Download a backup file (application/gzip) |
| POST | `/admin/backup/restore` | Validate and return restore instructions |

#### Config

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/config` | Get current full config as JSON |
| PATCH | `/admin/config` | Deep-merge config updates and persist to YAML |
| POST | `/admin/config/validate` | Validate a config dict without saving |

#### Queue (Admin)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/queue` | List tasks with pagination; filter by `status` |
| POST | `/admin/queue/{task_id}/cancel` | Cancel a pending or running task |
| POST | `/admin/queue/{task_id}/retry` | Retry a failed or cancelled task |

#### Logs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/logs/file-ops` | File operation logs; filter by `document_id`, `status` |
| GET | `/admin/logs/system` | System event logs; filter by `level`, `component` |

#### Stats (Extended)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/stats` | Extended stats: docs, users, watch folders, tokens, backups |

---

## MCP Server

The MCP (Model Context Protocol) server enables AI agents to interact with the document library programmatically. Intended for Claude Desktop and other MCP-compatible clients.

### Server Name

`mymemex`

### Transports

| Mode | Description | Config |
|------|-------------|--------|
| `stdio` | Default; for Claude Desktop (`claude_desktop_config.json`) | `mcp.transport = "stdio"` |
| `http` | Standalone HTTP server | `mcp.transport = "http"` |

### Tools

| Tool | Required Parameters | Optional Parameters | Description |
|------|---------------------|---------------------|-------------|
| `search_documents` | `query: str` | `mode: str = "hybrid"`, `limit: int = 10` | Search library (keyword/semantic/hybrid) |
| `get_document` | `document_id: int` | — | Full metadata and content chunks |
| `get_document_text` | `document_id: int` | `page_start: int = 1`, `page_end: int = null` | Extracted text for a page range |
| `list_documents` | — | `limit=50`, `offset=0`, `status`, `category`, `tag`, `sort="created_desc"` | Browse documents with filters |
| `add_tag` | `document_id: int`, `tag: str` | — | Add a tag to a document |
| `remove_tag` | `document_id: int`, `tag: str` | — | Remove a tag from a document |
| `upload_document` | `filename: str` | `file_path: str`, `content: str` | Upload via local path or base64 content |
| `get_library_stats` | — | — | Overall library statistics |
| `reclassify_documents` | — | `document_ids: list[int]`, `all_documents: bool = false` | Re-run AI classification |
| `aggregate_amounts` | — | `category`, `field_name`, `date_from`, `date_to`, `currency`, `min_confidence=0.5` | Sum monetary fields across documents |
| `get_extracted_fields` | `document_id: int` | — | View all extracted structured fields |
| `list_document_types` | — | — | All auto-classified categories with counts |
| `reextract_documents` | — | `document_ids: list[int]`, `all_documents: bool = false` | Re-run LLM structured extraction |

**`list_documents` sort values:** `created_desc`, `created_asc`, `title`

**`upload_document` notes:**
- Use `file_path` for a local filesystem path (validated against `mcp.security.allowed_parent_paths` if set)
- Use `content` for base64-encoded file content (limited by `mcp.security.max_upload_size_mb`, default 5 MB)

### Resources

| URI | Name | Content |
|-----|------|---------|
| `library://tags` | All Tags | JSON array of all tags with document counts |
| `library://stats` | Library Statistics | JSON object with overall library stats |

### Prompts

| Prompt | Parameters | Description |
|--------|------------|-------------|
| `search_and_summarize` | `query: str` | Instructs LLM to search the library and summarize findings |
| `compare_documents` | `document_ids: str` | Comma-separated IDs; instructs LLM to compare those documents |

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "mymemex": {
      "command": "mymemex",
      "args": ["mcp", "serve"],
      "env": {
        "MYMEMEX_CONFIG": "/path/to/mymemex.yaml"
      }
    }
  }
}
```

---

## CLI Commands

Main command: `mymemex`

### Top-Level Commands

| Command | Options | Description |
|---------|---------|-------------|
| `mymemex version` | — | Show version information |
| `mymemex config` | `--show/-s`, `--path/-p PATH` | Show current configuration |
| `mymemex init [PATH]` | PATH defaults to `./data` | Initialize data directory and `config.yaml` |
| `mymemex serve` | `--config/-c PATH`, `--host HOST`, `--port PORT` | Start API + web UI server (uvicorn) |

### Backup Sub-Commands

| Command | Options | Description |
|---------|---------|-------------|
| `mymemex backup create` | `--destination/-d PATH` (default `./backups`), `--config/-c PATH`, `--name/-n NAME` | Create tar.gz backup |
| `mymemex backup restore BACKUP_PATH` | `--config/-c PATH`, `--yes/-y` (skip confirmation) | Restore from .tar.gz backup |
| `mymemex backup list` | `--destination/-d PATH` (default `./backups`) | List available .tar.gz backups |

### Users Sub-Commands (M12)

| Command | Options | Description |
|---------|---------|-------------|
| `mymemex users create NAME` | `--admin`, `--default`, `--password PASSWORD` | Create a user |
| `mymemex users list` | — | List all users with roles and password status |

### MCP Sub-Commands

| Command | Options | Description |
|---------|---------|-------------|
| `mymemex mcp serve` | `--config/-c PATH` | Start MCP server via stdio (for Claude Desktop) |

---

## Web UI

The web interface is server-rendered HTML using Jinja2 templates, Alpine.js for interactivity, and Tailwind CSS for styling. All data fetching from page JS uses `fetch()` against the REST API.

### Main Pages

| URL | Description |
|-----|-------------|
| `/` | Document list / dashboard. First-run detection: calls `/api/v1/admin/setup/status` and redirects to `/ui/admin/setup` if `needs_setup` is true and `setup_skipped` is not set in localStorage |
| `/document/{id}` | Document detail: metadata, extracted fields, tags, text chunks |
| `/search` | Search interface: keyword / semantic / hybrid mode selector, results list |
| `/tags` | Tag browser: all tags with counts, click to filter documents |
| `/upload` | File upload interface (drag-and-drop) |

### Admin Pages

All admin pages are under `/ui/admin/`. The navigation bar has an **Admin** dropdown that links to all sections.

| URL | Page | Description |
|-----|------|-------------|
| `/ui/admin/setup` | Setup Wizard | First-run wizard: create initial user profile (name + aliases). Skip button sets `localStorage.setup_skipped = 1` |
| `/ui/admin/settings` | Settings | Tabbed config editor (Server, LLM, OCR, AI, Backup, MCP tabs). Shows restart-required warning for structural changes |
| `/ui/admin/watch-folders` | Watch Folders | CRUD table of watched directories + add/edit modal with path, patterns, file policy, active toggle |
| `/ui/admin/mcp` | MCP Tokens | Token list with prefix display + generate-token modal. Full token displayed once on creation |
| `/ui/admin/backup` | Backup | Config form (cron schedule, retention, destination) + backup history table + "Backup Now" button |
| `/ui/admin/users` | Users | CRUD table of user profiles + add/edit modal with name and aliases list |
| `/ui/admin/queue` | Task Queue | Live task list with WebSocket updates, status filter, cancel/retry actions |
| `/ui/admin/logs` | Logs | Dual-tab view: File Operations log and System Log, each with level/component filters |

---

## Processing Pipeline

### Ingestion Flow

```
File detected by watcher (or uploaded via API/MCP)
  └─ Quick hash check → duplicate? → record new path, skip
  └─ Full content hash check → duplicate? → record new path, skip
  └─ Create document record (status: pending)
  └─ Enqueue INGEST task (priority 5)
      └─ Extract PDF metadata (title, author, page count, created date)
      └─ Extract text page-by-page (PyMuPDF native)
          └─ Pages with < 50 chars: mark needs_ocr
      └─ Chunk native text (1,500 chars max, 200-char overlap)
      └─ Store chunks (FTS5 indexed)
      └─ [If OCR enabled] Tesseract OCR on pages needing it
          └─ Chunk and store OCR text
      └─ Update document status: processed
      └─ Apply file policy (if watch directory has one)
      └─ [If classification enabled] Enqueue CLASSIFY task (priority 3)
      └─ [If extraction enabled + LLM configured] Enqueue EXTRACT_METADATA task (priority 2)

CLASSIFY task:
  └─ Build user context (from Users table)
  └─ Send first 3,000 chars to LLM
  └─ Parse: document_type, tags with confidence, summary
  └─ Filter tags by confidence_threshold, cap at max_tags
  └─ Auto-apply user: tags for known users/aliases found in text
  └─ Update document: category, summary, tags

EXTRACT_METADATA task:
  └─ Send document content to LLM
  └─ Parse: title, document_date, category, monetary amounts, entities
  └─ Store to document_fields table
  └─ Update document.title, document.document_date if extracted
```

### File Policy Execution

Applied immediately after a document reaches `processed` status. The policy comes from the `watch_directories` record for the directory where the file was found.

| Policy | Action |
|--------|--------|
| `keep_original` | No-op |
| `delete_original` | `os.unlink(source)` |
| `move_to_archive` | `shutil.move(source, archive_path/rendered_name)` |
| `copy_organized` | `shutil.copy2(source, archive_path/rendered_name)` |
| `rename_template` | `os.rename(source, source_dir/rendered_name)` |

Conflict resolution: appends `-{hash[:8]}` suffix if destination exists. All operations logged to `file_operation_logs`. File operations update `document.current_path` and `document.file_policy_applied`.

### Chunker

`chunk_text(text, max_chars=1500, overlap_chars=200)`:
1. Split on double newlines (paragraphs)
2. If paragraph > max_chars: split on single newlines
3. If line > max_chars: split on sentence boundaries (`. `, `? `, `! `)
4. If sentence > max_chars: hard split

### Deduplication

Two-stage:
1. **Quick hash:** xxhash of first 64 KB — fast pre-check
2. **Content hash:** SHA-256 of full file — definitive check

Duplicate files are not re-indexed; their new path is recorded in `file_paths`.

### Task Worker

Background workers poll the `tasks` table. Task routing:

| TaskType | Handler |
|----------|---------|
| `ingest` | `run_ingest_pipeline()` |
| `classify` | `ClassificationService.classify_document()` |
| `extract_metadata` | `ExtractionService.extract_document()` |

Failed tasks retry up to `max_attempts` (default 3) with exponential backoff: 1m → 5m → 15m. Stale tasks (stuck in `running` > 30 minutes) are reset to `pending` by `recover_stale()`.

---

## LLM Integration

### Requirements

- LLM provider set to `ollama`, `openai`, or `anthropic` in config
- For semantic search/embeddings: Ollama running locally with `nomic-embed-text` (or configured model)
- For classification and extraction: any configured LLM provider with a chat model

### Classification

`DocumentClassifier.classify(content, user_context="")`:

- Input: first 3,000 characters of document text
- Returns: `document_type`, `type_confidence`, `tags[]` (name + confidence), `summary`

**Document types recognized:**
`invoice`, `tax_return`, `receipt`, `contract`, `medical_record`, `insurance_policy`, `bank_statement`, `utility_bill`, `other`

Tags are filtered to those meeting `classification.confidence_threshold` (default 0.7), capped at `classification.max_tags` (default 5).

### User Context Injection

If users exist in the database, `UserContextBuilder.build_prompt_context()` prepends a system prompt section to the classification call:

```
Known people in this collection:
- Alice Smith (also known as: alice, alice.smith)
- Bob Johnson (also known as: bob)
```

After classification, `get_person_tags(llm_response_text, users)` scans the LLM output for user names/aliases and adds `user:{name}` tags automatically.

### Structured Extraction

`ExtractionService.extract_document(document_id)`:

Extracts and stores to `document_fields`:
- **Monetary amounts** — stored as `currency` field type with `value_number` and `currency` (ISO 4217)
- **Entities** — stored as `string` field type (vendors, parties, etc.)
- **Dates** — stored as `date` field type in ISO format
- **Title** — updates `document.title` if not already set

### Aggregation

`ExtractionService.aggregate_amounts(...)` — sums currency fields across documents. Supports filtering by category, field_name, date range, and currency. Returns total sum + yearly breakdown.

### Embeddings

`Embedder` calls Ollama's `/api/embeddings` endpoint (model: `nomic-embed-text` by default). Embedding dimension: 768. Embeddings are stored in ChromaDB and linked via `chunk.vector_id`.

---

## Search

### Keyword Search (FTS5)

Uses SQLite's built-in FTS5 (Full-Text Search version 5) virtual table over chunk text. Supports standard FTS5 query syntax including phrase queries, prefix matching, and column filters.

- Results include: document title, filename, page number, chunk snippet, BM25 rank score
- Paginated: `page` + `per_page` parameters

### Semantic Search (Vector)

Requires: `ai.semantic_search_enabled = true`, Ollama running, `chromadb` installed.

Flow:
1. Embed the query using the configured embedding model
2. Search ChromaDB for nearest neighbor chunks (cosine distance)
3. Enrich results with document metadata and tags

Returns: document title, chunk text, vector distance (lower = more similar).

### Hybrid Search (RRF)

Combines keyword and semantic results using **Reciprocal Rank Fusion**:

```
score = keyword_weight / (k + rank_k) + semantic_weight / (k + rank_s)
```

where `k = 60` and `keyword_weight` defaults to 0.3 (semantic_weight = 0.7).

Gracefully degrades to keyword-only if semantic search is unavailable.

---

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get install -y libmagic1 poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu

# Non-root user (UID 1000)
RUN useradd -m -u 1000 mymemex

# Install (includes dev + OCR extras)
RUN pip install -e ".[dev,ocr]"

EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/health
CMD ["mymemex", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

Data directory: `/var/lib/mymemex`

### Minimal Setup (bare metal)

```bash
pip install mymemex[ocr,ai,mcp]
mymemex init ./data
mymemex serve --config ./data/mymemex.yaml
```

### Backup & Restore

**Format:** `.tar.gz` archive containing:
- `mymemex.db` — SQLite database (via online backup API, safe while running)
- `chroma/` — ChromaDB vector store directory
- `config.yaml` — Current configuration
- `metadata.json` — Version, timestamp, document count, checksums

**Create:**
```bash
mymemex backup create --destination ./backups --name my-backup
```

**List:**
```bash
mymemex backup list --destination ./backups
```

**Restore** (requires server to be stopped):
```bash
mymemex backup restore ./backups/my-backup.tar.gz --yes
```

**Schedule:** Set `backup.enabled = true` and `backup.schedule` (cron syntax, requires `croniter` package) for automated backups. Validated using `croniter.is_valid()`.

**Retention:** Backups older than `retention_days` can be pruned automatically.

---

## Extensibility

### Adding a New MCP Tool

1. Open `src/mymemex/mcp/tools.py`
2. Add a new function decorated with `@mcp.tool()`
3. Use `async with get_session() as session:` for DB access
4. Access config via `lctx.config` from `mcp_lifespan_context`
5. The tool is automatically registered with the MCP server

### Adding a New REST API Endpoint

1. Identify the relevant router module in `src/mymemex/api/`
2. Add a new `@router.get/post/patch/delete(...)` function
3. For admin endpoints: add to `src/mymemex/api/admin/` and register in `__init__.py`
4. Use `async with get_session() as session:` for DB access

### Adding a New Service

Follow the existing pattern:
```python
class MyService:
    def __init__(self, session: AsyncSession, config: AppConfig | None = None):
        self.session = session
        self.config = config
        self.repo = MyRepository(session)

    async def do_thing(self) -> dict:
        ...
```

Services receive an `AsyncSession` and optional config. They call repository methods for DB operations and never interact with the database directly.

### Adding a New Repository

Follow the pattern in `src/mymemex/storage/repositories.py`:
```python
class MyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: int) -> MyModel | None:
        result = await self.session.execute(select(MyModel).where(MyModel.id == id))
        return result.scalar_one_or_none()
```

---

## Testing

### Test Categories

| Category | Description | Files |
|----------|-------------|-------|
| Unit | Pure logic, no I/O | `test_chunker.py`, `test_hasher.py`, `test_config.py` |
| Service | Async DB with in-memory SQLite | `test_database.py`, `test_extraction.py`, `test_classification.py`, `test_embedder.py` |
| API | FastAPI test client | `test_api.py`, `test_web.py`, `test_mcp.py` |
| Integration | Requires live Ollama instance | `test_ollama_integration.py`, `test_semantic_search_e2e.py`, `test_ocr_integration.py` |

Integration tests are marked with `@pytest.mark.integration` and skipped unless `OLLAMA_API_BASE` is set in the environment.

### Running Tests

```bash
# All non-integration tests
python3 -m pytest tests/

# With coverage
python3 -m pytest tests/ --cov=src/mymemex --cov-report=html

# Integration tests (requires Ollama)
OLLAMA_API_BASE=http://localhost:11434 python3 -m pytest tests/ -m integration

# Single test file
python3 -m pytest tests/test_api.py -v
```

### Test Configuration

Tests use an in-memory SQLite database and a `tmp_path`-based config fixture defined in `tests/conftest.py`. The fixture creates a full `AppConfig` with sensible defaults for testing without requiring any installed services.

---

## Dependencies

### Required (always installed)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥ 0.115 | REST API framework |
| `uvicorn[standard]` | ≥ 0.34 | ASGI server |
| `pydantic` | ≥ 2.10 | Data validation |
| `pydantic-settings` | ≥ 2.6 | Config from env vars |
| `typer` | ≥ 0.15 | CLI framework |
| `rich` | ≥ 13.9 | CLI output formatting |
| `structlog` | ≥ 25.1 | Structured logging |
| `sqlalchemy` | ≥ 2.0 | ORM (async) |
| `alembic` | ≥ 1.14 | DB migrations |
| `aiosqlite` | ≥ 0.20 | Async SQLite driver |
| `watchdog` | ≥ 6.0 | Filesystem events |
| `python-magic` | ≥ 0.4.27 | MIME type detection |
| `xxhash` | ≥ 3.5 | Fast file hashing |
| `pymupdf` | ≥ 1.25 | PDF text extraction |
| `pillow` | ≥ 11.0 | Image processing |
| `ftfy` | ≥ 6.3 | Text encoding fixes |
| `httpx` | ≥ 0.28 | HTTP client (LLM calls) |
| `pyyaml` | ≥ 6.0 | YAML config parsing |
| `python-multipart` | ≥ 0.0.18 | File upload support |
| `jinja2` | ≥ 3.1 | Web UI templates |
| `croniter` | ≥ 1.3 | Backup schedule validation |

### Optional Extras

| Extra | Package | Purpose |
|-------|---------|---------|
| `[ocr]` | `pytesseract ≥ 0.3` | OCR via Tesseract |
| `[ai]` | `chromadb ≥ 0.6` | Vector store for semantic search |
| `[mcp]` | `mcp ≥ 1.26` | MCP server protocol |
| `[dev]` | pytest, ruff, mypy, etc. | Development tools |

System requirements for Docker/OCR: `libmagic1`, `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-eng`
