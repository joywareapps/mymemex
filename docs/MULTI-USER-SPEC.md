# Librarian Multi-User Specification

**Version:** 1.1
**Last Updated:** 2026-02-17
**Milestone:** M10

---

## Overview

Librarian M10 adds multi-user support, enabling a shared library where family members or small teams can:
- Share a single Librarian instance
- Track document ownership (who uploaded what)
- Query "my documents" vs "all documents"

**Key Design Principle:** Single library, multiple users, simple ownership tracking. Not separate libraries per user.

**Scope:** This spec defines the **MVP** — named profiles with upload tracking. Advanced features (roles, NER detection, visibility levels) are in the Future Enhancements section.

---

## User Model

### Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_default BOOLEAN DEFAULT FALSE
);
```

**Notes:**
- `name` is the display name used in queries (e.g., "Goran", "Ana")
- `is_default` marks the default user for single-user deployments
- No password/auth — named profiles only (auth deferred to future milestone)

### Document Ownership

Ownership is tracked via a simple `uploaded_by` column on the documents table:

```sql
ALTER TABLE documents ADD COLUMN uploaded_by_user_id INTEGER REFERENCES users(id);
```

**Notes:**
- One owner per document (the uploader)
- `NULL` means unassigned (legacy documents before multi-user was enabled)
- No roles, no co-ownership, no confidence scores in MVP

---

## API Changes

### New Endpoints

```
GET  /api/v1/users                  # List all users
POST /api/v1/users                  # Create user profile
GET  /api/v1/users/{id}             # Get user details
DELETE /api/v1/users/{id}           # Delete user profile
```

### Modified Endpoints

```
# Search with user filter
GET /api/v1/search?q=...&user={id|me|all}

# List with user filter
GET /api/v1/documents?user={id|me|all}
```

**User Filter Values:**
- `me` — Current user's documents only (based on session/MCP context)
- `all` — All documents (default)
- `{id}` — Specific user's documents

---

## MCP Changes

### Tool Parameters

All MCP tools accept optional `user` context:

```json
{
  "query": "insurance",
  "user": "me"  // optional: me, all, or user id
}
```

### MCP Context

MCP clients can pass user identity:

```json
{
  "user_id": 1,
  "user_name": "Goran"
}
```

**Implementation:**
- Claude Desktop: Configured per-user in MCP settings
- OpenClaw: Passed from session context
- If no user context provided, uses the default user (if set) or returns all documents

---

## Ownership Tracking

### Upload Tracking (MVP)

When a document is uploaded/added:
1. Capture the user context from upload source (MCP user context, API session, or CLI flag)
2. Set `uploaded_by_user_id` on the document record
3. If no user context is available, leave as `NULL` (unassigned)

### Manual Assignment

Users can reassign ownership:
- Via API: `PUT /api/v1/documents/{id}` with `uploaded_by_user_id`
- Via MCP: include user context in upload tool calls

---

## Configuration

```yaml
# config.yaml
multi_user:
  enabled: true
  default_user: Goran  # For single-user migration
```

---

## Migration Path

### From Single-User to Multi-User

1. Run migration: `alembic upgrade +1` (creates users table, adds `uploaded_by_user_id` column)
2. Create default user: `librarian users create --default "Goran"`
3. Assign existing docs: `librarian users assign-all --user 1`
4. Enable in config: `multi_user.enabled: true`

### Backward Compatibility

- Single-user deployments continue working unchanged
- If `multi_user.enabled: false`, all queries skip user filtering
- `is_default` user is used for uploads when no user context is provided

---

## Success Criteria

1. Multiple named profiles can coexist
2. Documents can be filtered by owner ("my documents")
3. Single-user deployments are unaffected
4. Ownership is tracked on upload
5. No authentication required (named profiles only)

---

## Future Enhancements

The following features are **not in MVP scope** but may be added in later milestones:

### Roles and Permissions
- Owner/viewer/editor roles per document
- Role-based access control
- **Why deferred:** Family use case doesn't need role enforcement. All users are trusted.

### NER-Based Ownership Detection
- Use Named Entity Recognition to detect names in documents
- Auto-assign ownership based on addressee fields, signatures, etc.
- Confidence scoring (0.0-1.0) for detected ownership
- **Why deferred:** Requires NLP pipeline, adds complexity. Upload tracking covers 90% of cases.

### Document Visibility Levels
- `shared` (default), `private`, `hidden` visibility per document
- Privacy controls for sensitive documents
- **Why deferred:** Family use case assumes shared library. Privacy can be added when real demand appears.

### Co-Ownership
- Multiple owners per document (joint accounts, shared bills)
- Separate `document_ownership` junction table with confidence scores
- **Why deferred:** Simple `uploaded_by` covers the primary use case.

### User Authentication
- Password-based or SSO authentication
- Session management
- API key per user (for M10 multi-key auth in MCP)
- **Why deferred:** Named profiles are sufficient for trusted family/small-team environments.

### Web UI User Switching
- User picker dropdown in Web UI header
- "My Documents" / "All Documents" toggle
- Per-user settings and preferences
- **Why deferred:** This integrates as part of M8 (Web UI) or a post-M8 enhancement. The data model and MCP integration in M10 work independently.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-17 | Initial specification |
| 1.1 | 2026-02-17 | Simplify to MVP scope: named profiles + `uploaded_by` column. Remove roles, NER detection, confidence scores, visibility levels, co-ownership from MVP. Move to Future Enhancements. Update effort estimate. Fix M10 dependency (no longer requires M8). |
