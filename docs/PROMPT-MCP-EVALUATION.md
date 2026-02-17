# Prompt: Evaluate and Finalize Librarian MCP-First Architecture

## Context
I've already updated the Librarian project plan based on our previous discussion about MCP-first approach. Please evaluate the current state and make any necessary adjustments.

## Current State
1. **MILESTONES.md updated** - M7 (MCP Server) is now the next priority (Week 1)
2. **MCP-SPEC.md created** - Full specification of MCP tools including `upload_document`
3. **MULTI-USER-SPEC.md created** - Specification for shared library with ownership tracking
4. **ARCHITECTURE.md needs update** - Should add MCP architecture section

## Key Decisions to Validate

### 1. MCP-First Approach ✅
- **M7 (MCP Server)** is now the next milestone
- Provides conversational access via Claude Desktop/OpenClaw
- No built-in chat UI needed initially
- **Agreement:** This aligns with user's request

### 2. Chat Interface Deferred ✅  
- **M12 (Chat Interface)** is now milestone 12 (after Web UI)
- Optional feature for self-contained experience
- Uses separate Ollama model for chat (not embedding model)
- **Agreement:** This aligns with user's concern about needing "chatbot to call MCP"

### 3. Upload via MCP Included ✅
- `upload_document` tool in MCP-SPEC.md
- Places files in inbox folder for processing
- Simple implementation (base64 or file path)
- **Agreement:** This aligns with user's "nice to have" request

### 4. Multi-User Support Planned ✅
- **M10 (Multi-User)** specified in MULTI-USER-SPEC.md
- Shared library with ownership tagging
- NER-based detection (addressee fields) as stretch goal
- **Agreement:** This aligns with user's request for shared library with ownership

## Tasks for Claude

### 1. Evaluate Current Plan
- Does the MCP-first approach make sense given the constraints?
- Are the dependencies correct (M7 before M8, M10 after M7+M8)?
- Is the effort estimation realistic (1 week for M7)?

### 2. Update ARCHITECTURE.md
Add a new section "ADR-007: MCP-First Interface" covering:
- Why MCP over built-in chat
- Transport options (stdio vs HTTP/SSE)
- Integration with existing REST API
- User context passing for multi-user

### 3. Review MCP-SPEC.md
- Are all necessary tools defined?
- Is the `upload_document` tool correctly specified?
- Are error cases properly handled?

### 4. Review MULTI-USER-SPEC.md
- Does the ownership detection approach make sense?
- Is the migration path from single-user clear?
- Are privacy considerations adequate?

### 5. Finalize Roadmap
- Confirm milestone order: M7 → M8 → M9 → M10 → M11 → M12 → M13
- Add any missing dependencies
- Update effort estimates if needed

## Constraints to Respect
1. **Privacy first** - Local processing default, cloud opt-in only
2. **Simple deployment** - Should work on consumer hardware
3. **Backward compatibility** - Single-user deployments unaffected
4. **Incremental adoption** - Features can be added gradually

## Expected Output
1. Updated ARCHITECTURE.md with MCP architecture decision
2. Any refinements to MCP-SPEC.md or MULTI-USER-SPEC.md
3. Confirmation that the plan is ready for implementation

## Questions for Consideration
1. Should MCP be a separate service or integrated into the main process?
2. How should user context be passed from MCP clients?
3. What's the simplest path to get M7 working for initial testing?
4. Are there any critical dependencies we're missing?