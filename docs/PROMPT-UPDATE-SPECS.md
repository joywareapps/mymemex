# Prompt: Update Librarian Specs Based on Claude Review

## Your Task

Update all Librarian specification documents to address the critical issues and improvements identified in the architecture review. The review found several major problems that must be fixed before implementation can begin.

## Context

We just completed a comprehensive review of the MCP-first architecture plan. Claude identified **4 critical issues** and **6 improvements** that need to be incorporated into the specs before we start implementation.

## Critical Issues to Fix

### 1. Service Layer Gap
**Problem:** Specs reference a "service layer" that doesn't exist in the codebase. Business logic is scattered across API handlers, pipelines, and repositories.

**Required Changes:**
- Add a new milestone **M6.5: Service Layer Extraction** (2-3 days) that must happen BEFORE M7
- Update M7 to reference the existing service layer
- Update ARCHITECTURE.md to document the service layer architecture
- Add ADR-008 for service layer design

### 2. Upload via Base64 Problematic
**Problem:** Base64 encoding inflates file size by 33%, hitting MCP message limits for large PDFs.

**Required Changes:**
- Update MCP-SPEC.md `upload_document` tool:
  - Make `file_path` the PRIMARY method for stdio transport
  - Add `max_base64_size` parameter (default: 5MB)
  - Add error case for files exceeding limit
  - Document that HTTP transport should use two-step flow (upload endpoint → reference)
- Add `max_upload_size_mb` to config schema

### 3. `watch_directory` Security Risk
**Problem:** Tool allows adding arbitrary directories, could expose sensitive system files.

**Required Changes:**
- Update MCP-SPEC.md `watch_directory` tool:
  - Add `allowed_parent_paths` array in config
  - Tool must reject paths outside allowed boundaries
  - Add security warnings in documentation
  - Consider making this admin-only (not exposed via MCP by default)
- Add security section to MCP-SPEC.md

### 4. HTTP/SSE Authentication Weak
**Problem:** Single static API key, no rate limiting, no TLS consideration.

**Required Changes:**
- Update MCP-SPEC.md authentication section:
  - Default to `localhost` binding only
  - Add `rate_limit_requests_per_minute` config
  - Add `require_tls_for_network` flag with warnings
  - Document that network exposure requires reverse proxy with TLS
  - Defer multi-key auth to M10 (multi-user milestone)

## Improvements to Implement

### 1. Add `get_document_text` Tool
**Reason:** LLMs have context limits, need page-specific access.

**Changes:**
- Add to MCP-SPEC.md:
```json
{
  "name": "get_document_text",
  "parameters": {
    "document_id": "integer — required",
    "page_start": "integer — optional, 1-indexed",
    "page_end": "integer — optional, inclusive"
  },
  "returns": {
    "text": "Concatenated text for page range",
    "pages": [{"number": 1, "text": "..."}],
    "total_pages": 5
  }
}
```

### 2. Simplify MCP Resources
**Reason:** Resources should be lean, contextual data only.

**Changes:**
- Keep: `library://stats`, `library://tags`
- Remove: `library://documents` (too large), `library://document/{id}` (use tool instead)
- Update MCP-SPEC.md resources section with rationale

### 3. Fix Error Handling
**Reason:** Must follow MCP protocol, not HTTP-style errors.

**Changes:**
- Update MCP-SPEC.md error handling section:
  - Use MCP SDK's `isError: true` on tool results
  - Remove HTTP status codes (400, 503)
  - Keep custom error codes in message text for debugging
  - Show example of proper MCP error format

### 4. Update Effort Estimates
**Reason:** Estimates were optimistic, didn't account for service layer extraction.

**Changes:**
- Update MILESTONES.md:
  - M6.5 (NEW): 2-3 days
  - M7: 1 week → 1.5-2 weeks
  - M8: 2-3 weeks → 3-4 weeks
  - M10: 1-2 weeks → 2-3 weeks
  - Total: 8-11 weeks → 10-14 weeks

### 5. Simplify Multi-User MVP
**Reason:** Current spec over-engineered for family use case.

**Changes:**
- Update MULTI-USER-SPEC.md:
  - **MVP scope:** Named profiles + `uploaded_by` column + "my docs" filter
  - **Remove from MVP:** Roles (owner/viewer/editor), NER detection, confidence scores, visibility levels, co-ownership
  - Move removed features to "Future Enhancements" section
  - Simplify `document_ownership` table to just `uploaded_by_user_id`
  - Update effort estimate to 1 week (MVP only)

### 6. Fix M10 Dependency
**Reason:** Multi-user data model shouldn't depend on Web UI.

**Changes:**
- Update MILESTONES.md dependency graph:
  - M10 can start after M7 (MCP provides user context)
  - M10 Web UI integration is part of M8 or post-M8
  - Update notes to clarify split

## Files to Update

1. **docs/MILESTONES.md**
   - Add M6.5 milestone
   - Update effort estimates
   - Fix dependency graph
   - Add service layer extraction to M7 prerequisites

2. **docs/MCP-SPEC.md**
   - Fix `upload_document` (file_path primary, size limits)
   - Add `get_document_text` tool
   - Simplify resources section
   - Fix error handling (MCP protocol)
   - Add security section
   - Update authentication (localhost default, rate limiting)

3. **docs/MULTI-USER-SPEC.md**
   - Strip to MVP scope
   - Move advanced features to "Future"
   - Simplify data model
   - Update effort estimate

4. **docs/ARCHITECTURE.md**
   - Add ADR-008: Service Layer Design
   - Update ADR-007 with service layer reference
   - Add security considerations

## Expected Output

For each file:
1. Show the specific changes you're making
2. Highlight critical sections that changed
3. Ensure consistency across all documents
4. Add any missing cross-references

## Constraints

- Maintain document structure and formatting style
- Keep backward compatibility notes where relevant
- Preserve existing completed milestone content
- Don't remove content, move to "Future" sections instead

## Success Criteria

After your updates:
- All 4 critical issues are addressed
- All 6 improvements are implemented
- Effort estimates are realistic
- Service layer extraction is clearly positioned as prerequisite
- Security is properly addressed
- MVP scope is achievable for family use case
