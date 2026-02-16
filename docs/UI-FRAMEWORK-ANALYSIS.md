# UI Framework Analysis for Librarian

**Date:** 2026-02-15
**Status:** Research Phase

---

## Requirements for Librarian UI

1. **Document browser** — List, filter, search documents
2. **Semantic search interface** — Natural language queries with results
3. **Processing status dashboard** — Real-time ingestion progress
4. **Configuration management** — Settings, watch folders, privacy modes
5. **Document detail view** — View extracted text, metadata, tags
6. **Admin panel** — System health, storage stats, model management
7. **Responsive** — Works on desktop and potentially mobile

---

## Framework Comparison

### 1. Reflex (Recommended for MVP)

**What it is:** Full-stack Python framework — write frontend and backend in Python only. React under the hood.

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Learning curve** | ⭐⭐⭐⭐⭐ | Pure Python, no JS/React knowledge needed |
| **Development speed** | ⭐⭐⭐⭐⭐ | Fast iteration, hot reload |
| **UI components** | ⭐⭐⭐⭐ | 60+ built-in, Tailwind support |
| **Scalability** | ⭐⭐⭐ | Newer framework, some breaking changes |
| **Production readiness** | ⭐⭐⭐ | Growing ecosystem (20k+ GitHub stars) |

**Pros:**
- Single language (Python) for full stack
- Built-in database integration (SQLAlchemy)
- Authentication built-in
- Single-command deploy
- Real-time state management

**Cons:**
- Smaller ecosystem than Django/React
- APIs may change between versions
- Less community support than mature frameworks

**Best for:** Rapid development, Python-first teams, MVP

---

### 2. FastAPI + React (Recommended for Production)

**What it is:** FastAPI backend + React frontend. Industry-standard separation.

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Learning curve** | ⭐⭐⭐ | Requires Python + JS/React knowledge |
| **Development speed** | ⭐⭐⭐ | More setup, but faster long-term |
| **UI components** | ⭐⭐⭐⭐⭐ | Entire React ecosystem available |
| **Scalability** | ⭐⭐⭐⭐⭐ | Proven at scale |
| **Production readiness** | ⭐⭐⭐⭐⭐ | Battle-tested |

**Pros:**
- Maximum flexibility and control
- Huge ecosystem (MUI, Ant Design, shadcn/ui)
- Can hire React developers easily
- Best performance and scalability
- Clear separation of concerns

**Cons:**
- Two codebases to maintain
- Requires frontend expertise
- More complex deployment
- Slower initial development

**Best for:** Production apps, teams with frontend expertise, long-term projects

---

### 3. Streamlit (NOT Recommended)

**What it is:** Quick data app framework. Great for demos, not production.

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Learning curve** | ⭐⭐⭐⭐⭐ | Easiest to learn |
| **Development speed** | ⭐⭐⭐⭐⭐ | Fastest for simple apps |
| **UI components** | ⭐⭐ | Limited, not customizable |
| **Scalability** | ⭐ | Re-runs entire app on every interaction |
| **Production readiness** | ⭐⭐ | Not designed for complex apps |

**Why NOT for Librarian:**
- Re-executes entire script on every user interaction (inefficient)
- Limited UI components
- State management becomes nightmare as app grows
- Not suitable for document browsing/search workflows
- Can't handle complex multi-step interactions well

---

### 4. Gradio (NOT Recommended)

**What it is:** ML demo interfaces. Perfect for single-model demos, not full applications.

**Why NOT for Librarian:**
- Designed for ML model demos, not full applications
- Very limited customization
- Not scalable for production

---

### 5. Django + HTMX (Alternative)

**What it is:** Django backend with HTMX for interactivity. Server-rendered with dynamic updates.

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Learning curve** | ⭐⭐⭐⭐ | Python + HTML, minimal JS |
| **Development speed** | ⭐⭐⭐⭐ | Fast with built-in admin |
| **UI components** | ⭐⭐⭐ | HTMX + templates |
| **Scalability** | ⭐⭐⭐⭐ | Proven framework |
| **Production readiness** | ⭐⭐⭐⭐⭐ | Battle-tested |

**Pros:**
- Built-in admin panel (huge time saver!)
- Mature ecosystem
- Good for content-heavy apps
- Minimal JavaScript needed

**Cons:**
- Less dynamic than React/Reflex
- HTMX learning curve for complex interactions
- Not ideal for real-time updates

---

## Recommendation

### Phase 1 (MVP): **Reflex**
- Fastest path to working application
- Single language for team
- Good enough for early adopters
- Can iterate quickly

### Phase 2 (Production): **FastAPI + React**
- When ready for production scale
- When UX polish matters
- When hiring becomes relevant
- When performance is critical

### Alternative: **Django + HTMX**
- If team prefers server-rendered approach
- If admin panel is priority
- If minimal JS is desired

---

## UI Screens Required

### Core Screens

1. **Dashboard**
   - System status (documents indexed, storage used, queue depth)
   - Recent activity feed
   - Quick search bar

2. **Document Browser**
   - List/grid view toggle
   - Filters (type, date, tags, status)
   - Sort options
   - Bulk actions (re-index, delete, tag)

3. **Document Detail**
   - File preview
   - Extracted text with highlighting
   - Metadata panel
   - Tags/categories
   - Related documents

4. **Search Interface**
   - Natural language query input
   - Results with snippets and sources
   - Filters and refinements
   - Query history

5. **Ingestion Queue**
   - Pending documents
   - Processing status (real-time)
   - Error logs
   - Retry controls

6. **Settings**
   - Watch folders configuration
   - Privacy mode toggles
   - OCR engine selection
   - Model configuration
   - Cloud API credentials (optional)

7. **Tags & Categories**
   - Tag management
   - Auto-tagging rules
   - Category hierarchy

---

## Next Steps

1. ✅ Framework analysis complete
2. 🔲 Create wireframes for each screen
3. 🔲 Define component library (if React) or Reflex components
4. 🔲 Design API contracts between UI and backend
5. 🔲 Create UI specification document
