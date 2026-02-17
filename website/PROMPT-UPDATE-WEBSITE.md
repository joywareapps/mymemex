# Update Librarian Website - M1-M6 Complete + MCP-First Architecture

Update the Librarian website (librarian.joywareapps.com) to reflect the current project status: **M1-M6 COMPLETE** with **MCP-first conversational interface** coming in M7.

## Current Website State

The website currently shows:
- Status: "M1-M4 Complete - Keyword search is working!"
- Tests: 43/43
- Roadmap: M5-M7 as "AI Enhancement Phase" (future)

## What Actually Exists Now (Feb 2026)

### Completed (M1-M6)
| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 | ✅ Complete | Project skeleton, config, CLI |
| M2 | ✅ Complete | File watching, dedup (xxhash + SHA-256) |
| M3 | ✅ Complete | Text extraction (PyMuPDF), chunking |
| M4 | ✅ Complete | REST API, FTS5 keyword search |
| M5 | ✅ Complete | OCR integration (Tesseract) |
| M6 | ✅ Complete | Semantic search (Ollama + ChromaDB) |

### Stats (Current)
- **Tests:** 83 (68 passing + 15 skip when Ollama/Tesseract unavailable)
- **Code:** ~35 Python modules
- **Features working:**
  - File watching with deduplication
  - PDF text extraction + OCR fallback
  - Keyword search (FTS5)
  - Semantic search (embeddings + vector similarity)
  - Hybrid search (Reciprocal Rank Fusion)
  - REST API on port 8000

### New Roadmap (M6.5-M13)
| Milestone | Effort | Description |
|-----------|--------|-------------|
| **M6.5** | 2-3 days | Service Layer Extraction (prerequisite for M7) |
| **M7** | 1.5-2 weeks | **MCP Server** — Claude Desktop, OpenClaw integration |
| M8 | 3-4 weeks | Web UI (browser-based browsing/searching) |
| M9 | 1 week | Auto-Tagging (LLM classification) |
| M10 | 2-3 weeks | Multi-User Support (family/team sharing) |
| M11 | 3-4 days | Cloud OCR Fallback |
| M12 | 1-2 weeks | Chat Interface (optional, MCP covers most use cases) |
| M13 | 1 week | Deployment & Distribution |

**Total:** 10-14 weeks for M6.5-M13

### Key Architecture Decision: MCP-First

Instead of building a custom chat UI, Librarian will expose its capabilities via **Model Context Protocol (MCP)**:
- Works with Claude Desktop, OpenClaw, any MCP client
- 8 tools: `search_documents`, `get_document`, `get_document_text`, `list_documents`, `add_tag`, `remove_tag`, `upload_document`, `get_library_stats`
- Two transports: stdio (Claude Desktop) + HTTP/SSE (OpenClaw)
- Security: path boundaries, localhost default, rate limiting

This means users can **talk to their documents** through their existing AI assistants — no custom chat UI needed for MVP.

---

## Required Updates

### 1. Update `src/pages/index.astro`

**Hero section:**
- Change badge from "Coming Soon" to "M1-M6 Complete"
- Update status indicator from gray/yellow to emerald/green
- Consider: "Semantic Search Working" or "Alpha Ready"

**Stats section (add after hero):**
```html
<div class="grid md:grid-cols-4 gap-4">
  <div class="bg-slate-900/50 rounded-lg p-4 text-center">
    <div class="text-3xl font-bold text-emerald-400">83</div>
    <div class="text-sm text-slate-400">Tests</div>
  </div>
  <div class="bg-slate-900/50 rounded-lg p-4 text-center">
    <div class="text-3xl font-bold text-cyan-400">6</div>
    <div class="text-sm text-slate-400">Milestones Complete</div>
  </div>
  <div class="bg-slate-900/50 rounded-lg p-4 text-center">
    <div class="text-3xl font-bold text-blue-400">3</div>
    <div class="text-sm text-slate-400">Search Modes</div>
  </div>
  <div class="bg-slate-900/50 rounded-lg p-4 text-center">
    <div class="text-3xl font-bold text-violet-400">M7</div>
    <div class="text-sm text-slate-400">MCP Server Next</div>
  </div>
</div>
```

**Solution section:** Already good, but could add "MCP Integration" as a feature highlight.

**How It Works section:** Update step 3 from "Ask Anything" to mention MCP:
- "Ask Anything (via Claude, OpenClaw, or any MCP client)"

### 2. Update `src/pages/roadmap.astro`

**Current Status box:**
- Phase: "M1-M6 Complete - Semantic Search Working! 🎉"
- Next Milestone: "M6.5: Service Layer Extraction"
- Target: "MCP Server (M7) in 2-3 weeks"

**Stats row:**
- Tests: 83 (68 pass + 15 skip)
- Code: ~35 modules
- Deployment: Docker ready
- GitHub: joywareapps/librarian

**Add M5 and M6 as completed milestones:**

```html
<!-- M5: OCR Integration -->
<div class="border border-emerald-500/30 rounded-xl p-6 bg-gradient-to-r from-emerald-500/5 to-transparent">
  <div class="flex items-center gap-4 mb-4">
    <div class="w-10 h-10 bg-emerald-500/30 rounded-lg flex items-center justify-center">
      <span class="text-emerald-400 font-bold">M5</span>
    </div>
    <div>
      <h3 class="text-xl font-semibold">OCR Integration <span class="ml-2 px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs font-semibold">✅ COMPLETE</span></h3>
      <p class="text-slate-400">Tesseract OCR for scanned PDFs with confidence scoring</p>
    </div>
  </div>
  <div class="ml-14">
    <ul class="space-y-2 text-slate-400">
      <li class="flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">...</svg>
        Automatic OCR fallback for image-based PDFs
      </li>
      <li class="flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">...</svg>
        Confidence scoring and audit logging
      </li>
      <li class="flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">...</svg>
        Tested with real scanned documents (German certificates)
      </li>
    </ul>
  </div>
</div>

<!-- M6: Semantic Search -->
<div class="border border-emerald-500/30 rounded-xl p-6 bg-gradient-to-r from-emerald-500/5 to-transparent">
  <div class="flex items-center gap-4 mb-4">
    <div class="w-10 h-10 bg-emerald-500/30 rounded-lg flex items-center justify-center">
      <span class="text-emerald-400 font-bold">M6</span>
    </div>
    <div>
      <h3 class="text-xl font-semibold">Semantic Search <span class="ml-2 px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs font-semibold">✅ COMPLETE</span></h3>
      <p class="text-slate-400">Vector embeddings + similarity search + hybrid RRF merge</p>
    </div>
  </div>
  <div class="ml-14">
    <ul class="space-y-2 text-slate-400">
      <li class="flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">...</svg>
        Ollama embeddings (nomic-embed-text, 768D vectors)
      </li>
      <li class="flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">...</svg>
        ChromaDB vector store with cosine similarity
      </li>
      <li class="flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">...</svg>
        Hybrid search: keyword + semantic with RRF merge
      </li>
    </ul>
    <div class="mt-4">
      <span class="px-3 py-1 bg-cyan-500/20 text-cyan-400 rounded-full text-sm font-medium">🧠 AI-Powered</span>
    </div>
  </div>
</div>
```

**Restructure upcoming milestones section:**

Replace the old M5-M7 block with:

```html
<!-- M6.5: Service Layer -->
<div class="border border-cyan-500/30 rounded-xl p-6">
  <div class="flex items-center gap-4 mb-4">
    <div class="w-10 h-10 bg-cyan-500/20 rounded-lg flex items-center justify-center">
      <span class="text-cyan-400 font-bold">M6.5</span>
    </div>
    <div>
      <h3 class="text-xl font-semibold">Service Layer Extraction <span class="ml-2 px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs font-semibold">NEXT UP</span></h3>
      <p class="text-slate-400">Extract business logic for MCP + REST API sharing</p>
    </div>
  </div>
  <div class="ml-14 text-slate-400">
    <p>Prerequisite for M7. Creates clean service layer that both MCP tools and REST endpoints call into.</p>
    <p class="mt-2 text-sm"><span class="text-cyan-400">Effort:</span> 2-3 days</p>
  </div>
</div>

<!-- M7: MCP Server (HIGHLIGHT THIS) -->
<div class="border border-violet-500/30 rounded-xl p-6 bg-gradient-to-r from-violet-500/5 to-transparent">
  <div class="flex items-center gap-4 mb-4">
    <div class="w-10 h-10 bg-violet-500/30 rounded-lg flex items-center justify-center">
      <span class="text-violet-400 font-bold">M7</span>
    </div>
    <div>
      <h3 class="text-xl font-semibold">MCP Server <span class="ml-2 px-2 py-1 bg-violet-500/20 text-violet-400 rounded text-xs font-semibold">🎯 PRIORITY</span></h3>
      <p class="text-slate-400">Conversational access via Claude Desktop, OpenClaw, any MCP client</p>
    </div>
  </div>
  <div class="ml-14">
    <ul class="space-y-2 text-slate-400">
      <li>8 tools: search, get_document, upload, tag management, stats</li>
      <li>Two transports: stdio (Claude Desktop) + HTTP/SSE (OpenClaw)</li>
      <li>Security: path boundaries, localhost default, rate limiting</li>
      <li>No custom chat UI needed — use your existing AI assistants!</li>
    </ul>
    <div class="mt-4">
      <span class="px-3 py-1 bg-violet-500/20 text-violet-400 rounded-full text-sm font-medium">🗣️ Talk to Your Documents</span>
      <span class="px-3 py-1 bg-slate-800 rounded-full text-sm text-slate-300 ml-2">1.5-2 weeks</span>
    </div>
  </div>
</div>

<!-- M8-M13: Future Enhancements -->
<div class="border border-slate-800 rounded-xl p-6">
  <div class="flex items-center gap-4 mb-4">
    <div class="w-10 h-10 bg-slate-700 rounded-lg flex items-center justify-center">
      <span class="text-slate-400 font-bold">M8+</span>
    </div>
    <div>
      <h3 class="text-xl font-semibold">Future Enhancements</h3>
      <p class="text-slate-400">Web UI, auto-tagging, multi-user, cloud OCR, chat, deployment</p>
    </div>
  </div>
  <div class="ml-14">
    <div class="grid md:grid-cols-3 gap-3 text-sm">
      <div class="bg-slate-900/50 rounded p-3">
        <span class="text-slate-300">M8:</span> Web UI (3-4 weeks)
      </div>
      <div class="bg-slate-900/50 rounded p-3">
        <span class="text-slate-300">M9:</span> Auto-Tagging (1 week)
      </div>
      <div class="bg-slate-900/50 rounded p-3">
        <span class="text-slate-300">M10:</span> Multi-User (2-3 weeks)
      </div>
      <div class="bg-slate-900/50 rounded p-3">
        <span class="text-slate-300">M11:</span> Cloud OCR (3-4 days)
      </div>
      <div class="bg-slate-900/50 rounded p-3">
        <span class="text-slate-300">M12:</span> Chat UI (1-2 weeks)
      </div>
      <div class="bg-slate-900/50 rounded p-3">
        <span class="text-slate-300">M13:</span> Deployment (1 week)
      </div>
    </div>
    <p class="mt-4 text-slate-500 text-sm">Total: 10-14 weeks for M6.5-M13</p>
  </div>
</div>
```

### 3. Update `src/pages/features.astro`

Add a new "Conversational Access" feature section highlighting MCP:

```html
<div class="bg-gradient-to-br from-violet-500/10 to-transparent border border-violet-500/20 rounded-xl p-6 text-center">
  <div class="w-16 h-16 bg-violet-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
    <svg class="w-8 h-8 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>
    </svg>
  </div>
  <h3 class="text-lg font-semibold mb-2">Conversational Access (M7)</h3>
  <p class="text-slate-400 text-sm">Talk to your documents via Claude Desktop, OpenClaw, or any MCP client. No custom chat UI needed.</p>
  <div class="mt-3">
    <span class="px-2 py-1 bg-violet-500/20 text-violet-400 rounded text-xs">Coming in M7</span>
  </div>
</div>
```

### 4. Add MCP Architecture to `src/pages/architecture.astro`

Add a section explaining the MCP-first approach:

```html
<section class="py-16 border-t border-slate-800">
  <div class="max-w-6xl mx-auto px-6">
    <h2 class="text-3xl font-bold mb-8">MCP-First Conversational Interface</h2>

    <div class="bg-slate-900/50 border border-slate-800 rounded-xl p-8 mb-8">
      <p class="text-lg text-slate-300 mb-6">
        Instead of building a custom chat UI, Librarian exposes its capabilities via the
        <strong class="text-violet-400">Model Context Protocol (MCP)</strong>. This means you can
        talk to your documents through your existing AI assistants.
      </p>

      <div class="grid md:grid-cols-2 gap-6">
        <div>
          <h3 class="text-xl font-semibold mb-4 text-violet-400">Supported Clients</h3>
          <ul class="space-y-2 text-slate-400">
            <li class="flex items-center gap-2">
              <span class="w-2 h-2 bg-violet-400 rounded-full"></span>
              Claude Desktop (stdio transport)
            </li>
            <li class="flex items-center gap-2">
              <span class="w-2 h-2 bg-violet-400 rounded-full"></span>
              OpenClaw (HTTP/SSE transport)
            </li>
            <li class="flex items-center gap-2">
              <span class="w-2 h-2 bg-violet-400 rounded-full"></span>
              Any MCP-compatible client
            </li>
          </ul>
        </div>
        <div>
          <h3 class="text-xl font-semibold mb-4 text-violet-400">Available Tools</h3>
          <ul class="space-y-2 text-slate-400 text-sm">
            <li><code class="text-cyan-400">search_documents</code> — Keyword/semantic/hybrid</li>
            <li><code class="text-cyan-400">get_document</code> — Full document + chunks</li>
            <li><code class="text-cyan-400">get_document_text</code> — Page-range access</li>
            <li><code class="text-cyan-400">list_documents</code> — Paginated listing</li>
            <li><code class="text-cyan-400">add_tag / remove_tag</code> — Tag management</li>
            <li><code class="text-cyan-400">upload_document</code> — Add new files</li>
            <li><code class="text-cyan-400">get_library_stats</code> — Library overview</li>
          </ul>
        </div>
      </div>
    </div>

    <div class="bg-slate-900/50 border border-emerald-500/20 rounded-xl p-6">
      <h3 class="text-lg font-semibold mb-3 text-emerald-400">Why MCP-First?</h3>
      <ul class="space-y-2 text-slate-400">
        <li>✅ Works with your existing AI assistants (no new app to learn)</li>
        <li>✅ Faster development (no custom chat UI needed for MVP)</li>
        <li>✅ Flexible integration (any MCP client can connect)</li>
        <li>✅ Future-proof (custom chat UI can be added later in M12)</li>
      </ul>
    </div>
  </div>
</section>
```

---

## Design Notes

- Keep the existing dark theme with emerald/cyan/violet accents
- Use emerald for completed items, cyan for in-progress, violet for MCP features
- Add subtle gradients and glow effects for emphasis
- Maintain responsive design (mobile-first)
- Keep the existing typography and spacing patterns

---

## Output Expected

1. Updated `src/pages/index.astro` with M1-M6 complete status and new stats
2. Updated `src/pages/roadmap.astro` with M5, M6 complete and new M6.5-M13 roadmap
3. Updated `src/pages/features.astro` with MCP feature highlight
4. Updated `src/pages/architecture.astro` with MCP-first section
5. All pages should build without errors: `npm run build`

After updates, the site should clearly communicate:
- **6 milestones complete** (not just 4)
- **Semantic search is working** (not just keyword)
- **MCP server is next** (conversational access via Claude/OpenClaw)
- **10-14 weeks** to full feature set (M13)
