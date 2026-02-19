# M11: Admin Panel, File Management & User Context

**Status:** Draft
**Last Updated:** 2026-02-19
**Dependencies:** M7 (MCP Server), M8 (Web UI), M10 (Deployment)
**Estimated Effort:** 2-3 weeks

---

## Overview

M11 delivers a web-based administration interface for configuration, backup, file management policies, MCP access control, and user profiles for LLM classification context.

---

## Table of Contents

1. [Admin Panel](#1-admin-panel)
2. [Watch Folder Management](#2-watch-folder-management)
3. [MCP Configuration](#3-mcp-configuration)
4. [Backup Management](#4-backup-management)
5. [Post-Ingestion File Policies](#5-post-ingestion-file-policies)
6. [User Profiles for LLM Context](#6-user-profiles-for-llm-context)
7. [Storage & System Stats](#7-storage--system-stats)
8. [Task Queue Management](#8-task-queue-management)
9. [Activity & System Logs](#9-activity--system-logs)
10. [Database Schema Changes](#10-database-schema-changes)
11. [Configuration Changes](#11-configuration-changes)
12. [API Endpoints](#12-api-endpoints)
13. [Implementation Order](#13-implementation-order)

---

## 1. Admin Panel

### 1.1 Settings Editor

Web UI for editing `config.yaml` without manual file editing.

Watch folders and users are managed through their own dedicated admin pages and stored
in the database — they do not appear in the Settings editor.

**Features:**
- Form-based config editing
- Validation before saving
- Backup of previous config on save
- Restart required warning where applicable (see table below)

**Config sections exposed:**

| Section | Editable Fields |
|---------|-----------------|
| `server` | Host, port |
| `watch` | Global file patterns, ignore patterns, debounce, max file size |
| `llm` | Provider, model, API base, API key (masked) |
| `ocr` | Enabled, language, confidence threshold |
| `ai` | Embedding model, embedding dimension, batch size |
| `classification` | Enabled, confidence threshold, max tags |
| `backup` | Enabled, schedule, retention, destination, include options |
| `mcp` | Enabled, transport, HTTP host/port, auth mode, IP whitelist |

**Restart requirements:**

| Setting changed | Restart required? | Reason |
|-----------------|:-----------------:|--------|
| `server.host`, `server.port` | Yes | uvicorn binds at startup |
| `database.path` | Yes | connection pool created at startup |
| `mcp.transport`, `mcp.http.host/port` | Yes | server setup differs per transport |
| `ai.embedding_model`, `ai.embedding_dimension` | Yes | ChromaDB collection is tied to model + dimension; existing embeddings become invalid |
| `llm.*` | No | client instantiated per request |
| `ocr.*` | No | applied per document |
| `classification.*`, `extraction.*` | No | applied per task |
| `ingestion.max_concurrent` | No | semaphore recreated on next task |
| `backup.*` | No | scheduler updated in place |
| `watch.file_patterns`, `watch.ignore_patterns`, `watch.debounce_seconds`, `watch.max_file_size_mb` | No | applied to next file event |
| `mcp.security.*`, `mcp.auth.*` | No | checked per request |

**UI Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│  Settings                                                   │
├─────────────────────────────────────────────────────────────┤
│  [Server] [LLM] [OCR] [AI] [Backup] [MCP]                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LLM Configuration                                          │
│  ─────────────────                                          │
│                                                             │
│  Provider:    [ollama ▼]                                    │
│  Model:       [llama3.2          ]                          │
│  API Base:    [http://localhost:11434]                      │
│  API Key:     [•••••••••••••] (for OpenAI/Anthropic)       │
│                                                             │
│  [Save Changes]                    [Reset to Defaults]      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Navigation

Add Admin section to Web UI navigation:

```
[Documents] [Search] [Tags] [Upload] | [Admin]
                                         │
                                         ├─ Settings
                                         ├─ Watch Folders
                                         ├─ Backup
                                         ├─ MCP Access
                                         ├─ File Policies
                                         ├─ Users
                                         ├─ Queue
                                         └─ Logs
```

---

## 2. Watch Folder Management

### 2.1 Folder List UI

```
┌─────────────────────────────────────────────────────────────┐
│  Watch Folders                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Path                          Status    Files    Actions   │
│  ─────────────────────────────────────────────────────────  │
│  /home/goran/Documents         Active    234      [Edit]    │
│  /home/goran/Downloads         Active    12       [Edit]    │
│  /home/goran/Scans             Paused    0        [Edit]    │
│                                                             │
│  [+ Add Folder]                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Add/Edit Folder Modal

```
┌─────────────────────────────────────────────────────────────┐
│  Edit Watch Folder                                    [X]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Path:           [/home/goran/Documents        ] [Browse]  │
│                                                             │
│  File Patterns:                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ *.pdf                                               │   │
│  │ *.docx                                              │   │
│  │ [+ Add Pattern]                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  File Policy:    [Keep Original ▼]                         │
│                                                             │
│  Active:         [x] Enabled                               │
│                                                             │
│               [Cancel]              [Save]                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Folder Operations

| Action | Description |
|--------|-------------|
| Add | Register new watch directory |
| Edit | Modify patterns, policy, active status |
| Pause/Resume | Temporarily stop watching |
| Remove | Stop watching (files remain in library) |
| Rescan | Trigger immediate scan for new files |

> **Implementation note — Pause/Resume:** `watchdog` has no per-directory pause API; it
> observes all scheduled directories simultaneously. Pause is implemented by setting
> `watch_directories.is_active = false` in the DB and filtering events in the watcher's
> event handler: when a file event arrives, the handler checks the DB record for that
> path's directory and skips processing if `is_active` is false. No watcher restart is
> needed. Rescan likewise reads only active directories from the DB.

---

## 3. MCP Configuration

### 3.1 MCP Settings Panel

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Configuration                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Enable MCP:     [x] Enabled                               │
│                                                             │
│  Transport:      [HTTP ▼]                                  │
│                   ○ stdio (local Claude Desktop only)      │
│                   ● HTTP (network access)                  │
│                                                             │
│  HTTP Settings:                                             │
│  Host:           [0.0.0.0] (bind to all interfaces)        │
│  Port:           [8001]                                    │
│                                                             │
│  Authentication: [Token ▼]                                 │
│                   ○ None (not recommended)                 │
│                   ● Token (recommended)                    │
│                   ○ IP Whitelist                           │
│                   ○ Both                                    │
│                                                             │
│  IP Whitelist (optional):                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 192.168.178.0/24                         [Remove]   │   │
│  │ [+ Add IP/Range]                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Save Changes]                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 MCP Access Tokens

Token management is only relevant when `mcp.transport = http`. When transport is `stdio`,
this section is hidden in the UI and the API returns a 409 with a clear message
(`"Token auth is only applicable to HTTP transport"`).

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Access Tokens                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [+ Generate New Token]                                     │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ OpenClaw on clawtop                                    │ │
│  │ Token: mymemex_a1b2c3d4e5f6...     [Copy] [Revoke]   │ │
│  │ Created: 2026-02-18  Last used: 2026-02-19 09:45     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ Claude Desktop on laptop                               │ │
│  │ Token: mymemex_x9y8z7w6...         [Copy] [Revoke]   │ │
│  │ Created: 2026-02-17  Last used: Never                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Token Generation

When clicking "Generate New Token":

```
┌─────────────────────────────────────────────────────────────┐
│  Generate MCP Token                                   [X]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Name:           [OpenClaw on clawtop        ]              │
│                  (for your reference)                       │
│                                                             │
│  [Cancel]                          [Generate]               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

After generation, show token once with copy button:

```
┌─────────────────────────────────────────────────────────────┐
│  Token Generated                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ⚠️ Copy this token now. It won't be shown again.          │
│                                                             │
│  mymemex_a1b2c3d4e5f6g7h8i9j0                              │
│                                                             │
│  [Copy to Clipboard]                                        │
│                                                             │
│  [Done]                                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.4 Token Format

```
mymemex_<32-char-random-string>
```

Generated using `secrets.token_urlsafe(24)` (produces ~32 chars).

---

## 4. Backup Management

### 4.1 Backup Configuration

```
┌─────────────────────────────────────────────────────────────┐
│  Backup Configuration                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Enable Backup:     [x] Enabled                            │
│                                                             │
│  Schedule:          [0 3 * * *    ] (cron: 3 AM daily)     │
│                     Examples: "0 3 * * *" (daily 3AM)      │
│                              "0 3 * * 0" (weekly Sunday)   │
│                                                             │
│  Retention:         [30] days                              │
│                                                             │
│  Destination:       [/mnt/backup/mymemex] [Browse]         │
│                                                             │
│  Include:                                                   │
│  [x] Database (SQLite)                                     │
│  [x] Vector Index (ChromaDB)                               │
│  [x] Configuration                                         │
│  [ ] Original Files (not recommended - large)              │
│                                                             │
│  [Save Configuration]                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Backup History

```
┌─────────────────────────────────────────────────────────────┐
│  Backup History                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Backup Now]                                               │
│                                                             │
│  Timestamp            Size       Status    Actions         │
│  ─────────────────────────────────────────────────────────  │
│  2026-02-19 03:00     45 MB      Success   [Download]      │
│  2026-02-18 03:00     44 MB      Success   [Download]      │
│  2026-02-17 03:00     43 MB      Success   [Download]      │
│  2026-02-16 03:00     42 MB      Failed    [View Error]    │
│                                                             │
│  Showing last 30 days. [Load More]                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Backup File Format

Replaces the earlier directory-based format from `cli/backup.py` (`mymemex_backup_YYYYMMDD_HHMMSS/`
with `manifest.json`). The CLI backup command must be updated to produce this format.

**Filename:** `mymemex-backup-YYYY-MM-DD-HHmmss.tar.gz`

**Archive layout:**
```
mymemex-backup-2026-02-19-030000.tar.gz
├── database/
│   └── mymemex.db          # SQLite online backup (consistent snapshot)
├── vectors/
│   └── chromadb/           # path from config, not hardcoded
├── config/
│   └── config.yaml
└── metadata.json
```

**metadata.json** (replaces the earlier `manifest.json`):
```json
{
  "version": "1.0.0",
  "created": "2026-02-19T03:00:00Z",
  "mymemex_version": "0.5.0",
  "document_count": 1234,
  "source_db_path": "/home/goran/myproject/data/mymemex.db",
  "source_vector_path": "/home/goran/myproject/data/chromadb",
  "checksum": "sha256:abc123..."
}
```

`source_db_path` and `source_vector_path` record where the data came from at backup time.
On restore, the destination is always the *current* config's paths — these fields are
informational only (shown in the restore UI, logged if paths differ).

The `checksum` covers the uncompressed archive content (computed before compression).
The ChromaDB path is read from config at backup time, not hardcoded.

### 4.4 Restore Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Restore Backup                                       [X]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ⚠️ This will replace your current database and vectors.   │
│     A backup of current state will be created first.        │
│                                                             │
│  Upload backup file:  [Choose file]  (.tar.gz)              │
│                                                             │
│  Backup Info:                                               │
│  Created: 2026-02-15 03:00                                  │
│  Documents: 1,234                                           │
│  Version: 0.5.0                                             │
│  Source DB:  /home/goran/myproject/data/mymemex.db          │
│  Source vectors: /home/goran/myproject/data/chromadb        │
│                                                             │
│  [Cancel]                          [Restore]                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Restore sequence (server-side):**

1. Validate the uploaded archive (checksum + metadata.json present)
2. Extract to a temp directory
3. Create a safety backup of the current state (non-scheduled, stored alongside scheduled backups)
4. Stop accepting new requests (return 503 for incoming traffic)
5. Close all DB connections and the ChromaDB client
6. Replace DB and vector store files with the extracted copies
7. Initiate graceful shutdown — the process manager (systemd, Docker restart policy) brings the server back up with the restored data

If any step from 4 onwards fails, the safety backup is restored before shutdown.
A warning is logged if `source_db_path` or `source_vector_path` differ from the current config paths.

---

## 5. Post-Ingestion File Policies

### 5.1 Policy Types

| Policy | Description | Use Case |
|--------|-------------|----------|
| `keep_original` | Leave file in place | Default, safe |
| `rename_template` | Rename in place using template | Organize without moving |
| `move_to_archive` | Move to archive directory | Keep inbox clean |
| `copy_organized` | Copy organized version to output | Keep original, create organized copy |
| `delete_original` | Delete after successful ingest | Dangerous, for import-only folders |

### 5.2 Template Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `{date}` | 2026-02-19 | Document date (extracted or file mtime) |
| `{year}` | 2026 | Year component |
| `{month}` | 02 | Month component (zero-padded) |
| `{day}` | 19 | Day component (zero-padded) |
| `{category}` | invoice | Auto-classified category |
| `{title}` | Invoice-ABC123 | Extracted title (sanitized) |
| `{original_name}` | scan001 | Original filename without extension |
| `{ext}` | pdf | Original extension |
| `{hash}` | a1b2c3d4 | First 8 chars of content hash |

### 5.3 Template Examples

```
{date}_{category}_{title}.{ext}
→ 2026-02-19_invoice_ACME-Corp.pdf

{year}/{month}/{category}/{original_name}.{ext}
→ 2026/02/invoice/scan001.pdf

{category}/{date}_{hash}.{ext}
→ invoice/2026-02-19_a1b2c3d4.pdf
```

### 5.4 File Policy Configuration

Per-watch-folder setting:

```
┌─────────────────────────────────────────────────────────────┐
│  File Policy                                         [X]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Watch Folder: /home/goran/Downloads                        │
│                                                             │
│  After Ingestion:                                           │
│  ● Keep original (no changes)                              │
│  ○ Rename in place                                         │
│  ○ Move to archive                                         │
│  ○ Copy organized version                                  │
│  ○ Delete original ⚠️                                      │
│                                                             │
│  Archive/Organized Path:                                    │
│  [/home/goran/Documents/Organized        ] [Browse]        │
│                                                             │
│  Rename Template:                                           │
│  [{date}_{category}_{title}.{ext}        ]                 │
│                                                             │
│  [Cancel]                          [Save]                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.5 Safety Guarantees

1. **Atomic operations** — Rename/move are atomic; no partial states
2. **Failure handling** — If ingestion fails, file is never moved/deleted
3. **Conflict resolution** — If target exists, append `-{hash}` suffix
4. **Audit log** — All file operations logged with timestamp and result
5. **Path tracking** — After a successful move/rename, `Document.current_path` is updated immediately so the system always knows where the file is. If the update fails (e.g. DB write error), the file operation is rolled back.

---

## 6. User Profiles for LLM Context

### 6.1 Overview

User profiles provide names and aliases so the LLM can identify people when classifying
documents and apply `person:{name}` tags automatically.

Authentication (username/password, sessions, login UI) is out of scope for M11 and will
be addressed in a dedicated auth milestone. User profiles contain no credentials.

### 6.2 User List UI

```
┌─────────────────────────────────────────────────────────────┐
│  Users                                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [+ Add User]                                               │
│                                                             │
│  Name        Aliases              Actions                   │
│  ────────────────────────────────────────────────────────  │
│  Goran       Goran O, Potato      [Edit] [Delete]          │
│  Zeljana     Zelj, Zeljana O      [Edit] [Delete]          │
│  Maja        —                     [Edit] [Delete]          │
│                                                             │
│  💡 User names help the AI classify documents. Add family  │
│     members so documents can be auto-tagged by person.      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Add/Edit User Modal

```
┌─────────────────────────────────────────────────────────────┐
│  Edit User                                           [X]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Name:           [Zeljana               ]                   │
│                   (shown in UI, passed to LLM)              │
│                                                             │
│  Aliases:                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Zelj                                                │   │
│  │ Zeljana O                                           │   │
│  │ [+ Add Alias]                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  (name variants the AI should recognise)                   │
│                                                             │
│               [Cancel]              [Save]                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 LLM Context Integration

When the LLM performs classification/extraction, it receives user context:

**System Prompt Addition:**
```
You are classifying documents for a household with the following members:

- Goran (aliases: Goran O, Potato, PotatoWarriah)
- Zeljana (aliases: Zelj, Zeljana O)
- Maja (no aliases)

When a document mentions or relates to any of these people, tag it with 
the appropriate person tag (e.g., "person:goran", "person:zeljana").

Consider:
- Names mentioned in the document text
- Recipients or senders of correspondence
- People referenced in forms or applications
- Context clues (e.g., "my wife" → Zeljana if Goran is the primary user)
```

### 6.5 Auto-Tagging Behavior

| Document Content | Matched User | Auto-Tag Applied |
|------------------|--------------|------------------|
| "Invoice for Goran O" | Goran (alias) | `person:goran` |
| "Dear Zeljana," | Zeljana | `person:zeljana` |
| "Maja's school report" | Maja | `person:maja` |
| "PotatoWarriah subscription" | Goran (alias) | `person:goran` |

### 6.6 User Data Storage

Users are stored in the `users` database table (see Section 8.1). There is no
`users:` section in `config.yaml`. The admin UI is the only way to manage users.

### 6.7 First-Run Wizard

On first open, if the `users` table is empty, the UI shows a welcome screen instead
of the normal document list:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Welcome to MyMemex                                         │
│                                                             │
│  Let's set up your library. First, tell us your name so    │
│  the AI can recognise documents that belong to you.         │
│                                                             │
│  Your name:      [                    ]                     │
│                   e.g. Goran                               │
│                                                             │
│  Aliases (optional):                                        │
│  [                    ]  [+ Add]                           │
│   Name variants the AI should also recognise               │
│                                                             │
│  [Skip for now]              [Get Started →]               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- **Get Started** — creates the user record and redirects to the document list
- **Skip for now** — proceeds with no users; person tagging is disabled until a user is added via Admin → Users. The wizard does not appear again after being skipped (a `setup_skipped` flag in local storage).
- Additional household members can be added later via Admin → Users.

### 6.8 Future: Authentication

When a login system is added (post-M11), the `users` table will gain `username` and
`password_hash` columns and `passlib[bcrypt]` will be added as a dependency. The DB
table is already the storage layer, so no migration of user data is needed.

---

## 7. Storage & System Stats

> **Implementation note:** Build on the existing `StatsService`
> (`src/mymemex/services/stats.py`) which already provides document counts, chunk count,
> queue stats, and SQLite size. The admin stats endpoints extend it with storage breakdown
> and activity history rather than duplicating the logic.

### 7.1 Stats Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  System Overview                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Library                                                    │
│  ───────────────────────────────────────────────────────   │
│  Documents:        1,234                                   │
│  Total Size:       2.4 GB                                  │
│  Tags:             45                                      │
│  Pending:          3 documents                             │
│                                                             │
│  Storage                                                    │
│  ───────────────────────────────────────────────────────   │
│  Database:         156 MB                                  │
│  Vector Index:     234 MB                                  │
│  Watch Folders:    12 GB (files)                           │
│                                                             │
│  Documents by Category                                     │
│  ───────────────────────────────────────────────────────   │
│  Invoice:          234 ████████████░░░░ 35%               │
│  Receipt:          189 █████████░░░░░░░ 28%               │
│  Contract:         87 █████░░░░░░░░░░░░ 13%               │
│  Tax Document:     65 ████░░░░░░░░░░░░░ 10%               │
│  Other:            176 █████████░░░░░░░ 14%               │
│                                                             │
│  Recent Activity                                            │
│  ───────────────────────────────────────────────────────   │
│  Last 24h:         12 documents ingested                   │
│  Last 7 days:      47 documents ingested                   │
│  Last backup:      2026-02-19 03:00 (Success)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Task Queue Management

### 8.1 Queue Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  Task Queue                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Running: 1   Pending: 3   Failed: 2   [Retry All Failed]  │
│                                                             │
│  Type        Document               Status    Tries  Action │
│  ─────────────────────────────────────────────────────────  │
│  classify    Invoice-March.pdf      Running   1/3    —      │
│  embed       Contract-Q1.pdf        Pending   0/3    [✕]    │
│  embed       Receipt-042.pdf        Pending   0/3    [✕]    │
│  ingest      Report-2026.pdf        Pending   0/3    [✕]    │
│  classify    Unknown-doc.pdf        Failed    3/3    [↺]    │
│  extract     Scan-001.pdf           Failed    3/3    [↺]    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Updates in real-time via the existing WebSocket (`/ws`).

### 8.2 Actions

| Action | Applies to | Description |
|--------|-----------|-------------|
| Cancel (✕) | `pending` tasks | Marks task `cancelled`; document status reset to `processed` if it has chunks, else `failed` |
| Retry (↺) | `failed` tasks | Resets `attempt_count` to 0, sets status back to `pending` |
| Retry All Failed | All `failed` | Bulk retry |

Running tasks cannot be cancelled (they are in-flight; the worker will complete or fail them naturally).

---

## 9. Activity & System Logs

### 9.1 Logs Page

Two tabs on a shared page — both are read-only audit views.

```
┌─────────────────────────────────────────────────────────────┐
│  Logs            [File Operations]  [System]                │
├─────────────────────────────────────────────────────────────┤
│  Level: [All ▼]   Component: [All ▼]        [Clear Filters] │
│                                                             │
│  Time              Level    Component  Message              │
│  ─────────────────────────────────────────────────────────  │
│  2026-02-19 09:45  INFO     watcher    File detected:       │
│                                        Invoice-March.pdf    │
│  2026-02-19 09:44  ERROR    classify   LLM timeout doc #42  │
│  2026-02-19 09:40  INFO     backup     Scheduled backup OK  │
│  2026-02-19 03:00  INFO     backup     Backup: 45 MB        │
│                                                             │
│  [Load More]                                                │
└─────────────────────────────────────────────────────────────┘
```

**File Operations tab** — sourced from `file_operations_log` (document-centric; shows
rename/move/copy/delete events with source and destination paths).

**System tab** — sourced from `system_log` (component-centric; covers startup, config
reload, backup events, LLM/OCR errors, watcher events, and any unhandled exceptions).
They are different enough in structure to warrant separate views but share the same page.

### 9.2 System Log

```sql
CREATE TABLE system_log (
    id INTEGER PRIMARY KEY,
    level TEXT NOT NULL,      -- info, warning, error
    component TEXT NOT NULL,  -- watcher, ingest, classify, extract, embed, backup, mcp, api
    message TEXT NOT NULL,
    details TEXT,             -- optional JSON for structured context (e.g. document_id, path)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Retention:** a background job trims `system_log` to the most recent 10,000 rows after
each insert batch. `file_operations_log` is not trimmed (it is an audit trail).

**What gets logged to `system_log`:**

| Event | Level | Component |
|-------|-------|-----------|
| Server startup / shutdown | info | api |
| Config saved | info | api |
| Watch folder added / removed | info | watcher |
| File detected / skipped / duplicate | info | watcher |
| Backup started / completed / failed | info / error | backup |
| LLM call failed or timed out | error | classify / extract |
| OCR failed for a page | warning | ingest |
| Embedding batch failed | error | embed |
| Unhandled exception in task worker | error | ingest |

---

## 10. Database Schema Changes

No existing installations — all changes go directly into ORM models and are created via
`Base.metadata.create_all()` on first run. No Alembic migrations are required at this stage.

### 10.0 Alembic Migrations

**Current approach:** No migrations during M11 development. All new tables and columns are created via `Base.metadata.create_all()` on startup. This allows rapid iteration with fresh database resets.

**TODO (before production release):** Add Alembic migrations for:
- M11 tables: `users`, `watch_directories`, `mcp_tokens`, `backups`, `file_operations_log`, `system_log`
- M11 columns: `documents.current_path`, `documents.file_policy_applied`
- Future user management tables (auth, sessions, etc.)

Migrations should be added alongside or after the user management/auth milestone, once the schema is stable for production users.

---

### 10.1 New Tables

**users**

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**watch_directories** — persistent watch folder registry (sole source of truth; not in config)

```sql
CREATE TABLE watch_directories (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    patterns TEXT NOT NULL DEFAULT '[]',  -- JSON array; empty = use global watch.file_patterns
    is_active BOOLEAN DEFAULT TRUE,
    file_policy TEXT NOT NULL DEFAULT 'keep_original',
    archive_path TEXT,
    rename_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**mcp_tokens**

```sql
CREATE TABLE mcp_tokens (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,  -- SHA-256 of full token
    token_prefix TEXT NOT NULL,        -- "mymemex_" + first 8 chars of random part, for display
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

**backups**

```sql
CREATE TABLE backups (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,  -- pending, success, failed
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

**file_operations_log**

```sql
CREATE TABLE file_operations_log (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    operation TEXT NOT NULL,  -- rename, move, copy, delete
    source_path TEXT NOT NULL,
    destination_path TEXT,
    status TEXT NOT NULL,  -- success, failed, skipped
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**system_log** — see Section 9.2 for full definition (also a new table, listed there for proximity to the log spec).

### 10.2 Modified Tables

**documents** — add two new nullable columns to the ORM model (`original_path` already exists and is immutable)

| Column | Type | Description |
|--------|------|-------------|
| `current_path` | `TEXT NULL` | Current file location after a policy move/rename. `NULL` means the file is still at `original_path`. Updated in-place whenever the file is moved or renamed. |
| `file_policy_applied` | `TEXT NULL` | Which policy was executed (e.g. `move_to_archive`). Set once, not updated again. |

**Path tracking semantics:**

- `original_path` — set at ingestion, **never modified**. Always points to where the file entered the system.
- `current_path` — updated each time the file is physically moved or renamed by a policy. `NULL` = no policy moved it.
- `FilePath` table remains **deduplication-only** (same content found at multiple filesystem locations simultaneously) and is not used to track policy-driven moves.
- The effective current location is: `COALESCE(current_path, original_path)`.

---

## 11. Configuration Changes

### 11.1 Config Changes

Watch folders and users are removed from `config.yaml` entirely — both are now managed
exclusively through the admin UI and stored in the database. `watch.directories` is
dropped from `WatchConfig`; the global watch settings (`file_patterns`, `ignore_patterns`,
`debounce_seconds`, `max_file_size_mb`) remain in config as they apply to all folders.

New `mcp` and `backup` top-level sections:

```yaml
# config.yaml additions / changes

watch:
  # directories removed — managed via Admin → Watch Folders (stored in DB)
  file_patterns: ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif", "*.bmp", "*.webp"]
  ignore_patterns: ["*/.*", "*/.Trash-*", "*/@eaDir/*", "*/#recycle/*"]
  debounce_seconds: 2.0
  max_file_size_mb: 100  # default 100, configurable up to 500

mcp:
  enabled: true
  transport: http  # stdio | http
  security:
    allowed_parent_paths: []  # existing setting — keep
    max_upload_size_mb: 5     # existing setting — keep
  http:
    host: "0.0.0.0"
    port: 8001
  auth:
    mode: token  # none | token | ip_whitelist | both
    ip_whitelist:
      - "192.168.178.0/24"

backup:
  enabled: true
  schedule: "0 3 * * *"  # cron expression
  retention_days: 30
  destination: "/var/lib/mymemex/backups"
  include:
    database: true
    vectors: true
    config: true
    original_files: false
```

### 11.2 Config Validation

New and updated Pydantic models:

```python
# FilePolicy used by the WatchDirectory ORM model (not config)
class FilePolicy(str, Enum):
    KEEP_ORIGINAL = "keep_original"
    RENAME_TEMPLATE = "rename_template"
    MOVE_TO_ARCHIVE = "move_to_archive"
    COPY_ORGANIZED = "copy_organized"
    DELETE_ORIGINAL = "delete_original"

class WatchConfig(BaseModel):
    # directories removed — managed via DB
    file_patterns: list[str] = Field(default=[...])  # global fallback patterns (unchanged)
    ignore_patterns: list[str] = Field(default=[...])  # unchanged
    debounce_seconds: float = 2.0
    max_file_size_mb: int = Field(default=100, ge=1, le=500)  # hard cap 500 MB

class MCPAuthMode(str, Enum):
    NONE = "none"
    TOKEN = "token"
    IP_WHITELIST = "ip_whitelist"
    BOTH = "both"

class MCPHTTPConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8001

class MCPAuthConfig(BaseModel):
    mode: MCPAuthMode = MCPAuthMode.NONE
    ip_whitelist: list[str] = Field(default_factory=list)

class MCPConfig(BaseModel):
    enabled: bool = True
    transport: Literal["stdio", "http"] = "stdio"
    security: MCPSecurityConfig = Field(default_factory=MCPSecurityConfig)  # existing — keep
    http: MCPHTTPConfig = Field(default_factory=MCPHTTPConfig)
    auth: MCPAuthConfig = Field(default_factory=MCPAuthConfig)

class BackupIncludeConfig(BaseModel):
    database: bool = True
    vectors: bool = True
    config: bool = True
    original_files: bool = False

class BackupConfig(BaseModel):
    enabled: bool = False
    schedule: str = "0 3 * * *"
    retention_days: int = Field(default=30, ge=1, le=365)
    destination: str = ""
    include: BackupIncludeConfig = Field(default_factory=BackupIncludeConfig)

    @field_validator("schedule")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        try:
            from croniter import croniter
            if not croniter.is_valid(v):
                raise ValueError(f"Invalid cron expression: {v!r}")
        except ImportError:
            pass  # croniter optional at config-load time; validated at backup scheduling
        return v
```

> **Implementation note:** Add `croniter` to `pyproject.toml` dependencies.
> Validation runs on both config load and `PATCH /api/v1/admin/config`.

Add `backup: BackupConfig` to `AppConfig`. Users are ORM models, not config.

---

## 12. API Endpoints

### 12.0 CORS Policy for Admin Endpoints

All `/api/v1/admin/*` endpoints enforce same-origin access. Requests carrying an `Origin`
header that does not match the server's own host are rejected with `403 Forbidden`.

```python
# Middleware pseudocode
if request.url.path.startswith("/api/v1/admin/"):
    origin = request.headers.get("origin")
    if origin and not is_same_origin(origin, request.base_url):
        return Response(status_code=403, content="Admin endpoints are same-origin only")
```

Non-admin endpoints retain the existing `allow_origins=["*"]` CORS behaviour.

### 12.1 Admin Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/config` | Get full config (secrets masked) |
| PATCH | `/api/v1/admin/config` | Update config sections |
| POST | `/api/v1/admin/config/validate` | Validate config without saving |

### 12.2 Watch Folders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/watch-folders` | List watch folders |
| POST | `/api/v1/admin/watch-folders` | Add watch folder |
| PATCH | `/api/v1/admin/watch-folders/{id}` | Update watch folder |
| DELETE | `/api/v1/admin/watch-folders/{id}` | Remove watch folder |
| POST | `/api/v1/admin/watch-folders/{id}/rescan` | Trigger rescan |

### 12.3 MCP Tokens

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/mcp/tokens` | List tokens (masked) |
| POST | `/api/v1/admin/mcp/tokens` | Generate new token |
| DELETE | `/api/v1/admin/mcp/tokens/{id}` | Revoke token |

### 12.4 Backup

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/backup/config` | Get backup config |
| PATCH | `/api/v1/admin/backup/config` | Update backup config |
| POST | `/api/v1/admin/backup/run` | Trigger manual backup |
| GET | `/api/v1/admin/backup/history` | List backup history |
| GET | `/api/v1/admin/backup/{id}/download` | Download backup file (streamed; max 2 GB) |
| POST | `/api/v1/admin/backup/restore` | Restore from backup file |

### 12.5 Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/users` | List users |
| POST | `/api/v1/admin/users` | Add user |
| PATCH | `/api/v1/admin/users/{id}` | Update user |
| DELETE | `/api/v1/admin/users/{id}` | Remove user |

### 12.6 Stats

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/stats` | Get system overview |
| GET | `/api/v1/admin/stats/storage` | Detailed storage stats |
| GET | `/api/v1/admin/stats/activity` | Ingestion activity |

### 12.7 Setup

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/setup/status` | `{"needs_setup": bool}` — true when users table is empty |

### 12.8 Task Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/queue` | List tasks (filterable by `status`, `task_type`) |
| POST | `/api/v1/admin/queue/tasks/{id}/cancel` | Cancel a pending task |
| POST | `/api/v1/admin/queue/tasks/{id}/retry` | Retry a failed task |
| POST | `/api/v1/admin/queue/retry-all` | Retry all failed tasks |

### 12.9 Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/logs/file-operations` | List file operation log entries |
| GET | `/api/v1/admin/logs/system` | List system log entries (filterable by `level`, `component`) |

---

## 13. Implementation Order

### Phase 1: Foundation (Week 1)

1. **ORM model updates** (no Alembic migrations — fresh installs only)
   - Add `WatchDirectory`, `MCPToken`, `Backup`, `FileOperationLog` models
   - Add `current_path` and `file_policy_applied` columns to `Document`
   - All created via `Base.metadata.create_all()` on startup

2. **Config schema updates**
   - Drop `WatchConfig.directories` (DB-managed)
   - Add `BackupConfig`, extend `MCPConfig` with `transport`, `http`, `auth`
   - No `users` in config — DB only

3. **Users API + Storage**
   - `User` ORM model CRUD via `/api/v1/admin/users`
   - LLM context builder (formats users for classification prompts)
   - First-run wizard endpoint: `GET /api/v1/admin/setup/status` → `{needs_setup: bool}`

### Phase 2: MCP & Backup (Week 2)

4. **MCP token management**
   - Token generation (secrets.token_urlsafe)
   - Token storage (hashed)
   - Token validation middleware

5. **Backup infrastructure**
   - BackupService with create/list/restore
   - Cron scheduling integration
   - Backup file format implementation

6. **Admin API endpoints**
   - All `/api/v1/admin/*` routes including queue, logs, setup
   - Same-origin middleware for admin paths
   - Request validation and error handling

### Phase 3: Web UI (Week 2-3)

7. **Admin panel navigation + first-run wizard**
   - Admin section added to nav
   - Settings editor forms with restart-required warnings
   - First-run wizard (shown when `needs_setup: true`)
   - Watch folder management

8. **MCP configuration UI**
   - MCP settings panel
   - Token management (shown only when transport = HTTP)

9. **Backup UI**
   - Backup configuration form (cron expression validated on blur)
   - History viewer
   - Restore flow

10. **User management UI**
    - User list
    - Add/edit user modal with alias management

11. **Queue management UI**
    - Real-time task list via WebSocket
    - Cancel / retry / retry-all actions

12. **Logs UI**
    - Shared Logs page with File Operations and System tabs
    - Level and component filters

### Phase 4: Integration (Week 3)

13. **File policy execution**
    - Integration with ingestion pipeline
    - Atomic file operations
    - Audit logging

14. **LLM context integration**
    - User context in classification prompts
    - Auto-tagging with person tags
    - Fallback when no users configured

15. **Testing & Documentation**
    - Unit tests for new services
    - Integration tests for admin flows
    - Update user documentation

---

## Success Criteria

- [ ] All config editable through UI (no manual YAML required)
- [ ] MCP tokens can be generated and revoked
- [ ] Backups run on schedule and can be restored
- [ ] File policies execute safely (atomic operations, no data loss)
- [ ] User profiles improve classification accuracy
- [ ] Documents auto-tagged with `person:{name}` when appropriate
- [ ] Audit log shows all file operations
- [ ] First-run wizard shown when no users exist in DB
- [ ] System functions correctly with no users (person tagging simply disabled)

---

## Future Enhancements (Post-M11)

- **M12:** Document ownership, private documents, folder-user association
- **M13:** Chat interface with user-aware RAG
- **User authentication** — username/password login, sessions, `passlib[bcrypt]` (users already in DB — no data migration needed)
- **Two-factor authentication**
- **User-specific document preferences**
- **Export user data (GDPR compliance)**
- **Activity logs per user**
