# M8: Web UI — Document Browser Interface

**Goal:** Build a browser-based interface for searching, browsing, and managing documents in Librarian.

**Prerequisites:**
- ✅ M1-M6 complete
- ✅ M6.5 Service Layer complete
- ✅ M7 MCP Server optional (not required for basic UI)

---

## Overview

A lightweight web UI served by FastAPI that provides:
- Document browsing with filtering and sorting
- Search interface (keyword + semantic with highlighting)
- Document viewer (text view with page navigation)
- Tag management
- File upload
- Settings panel

**Design principle:** Boring tech, minimal dependencies. HTMX + Alpine.js or vanilla JS. No heavy framework.

**Target users:**
- Librarian users who want visual document management
- Users who prefer browser over CLI or MCP clients

---

## Architecture

```
Browser (HTMX + Alpine.js)
    │
    ▼
FastAPI (existing server)
    │
    ▼
Service Layer (M6.5)
    │
    ▼
Repositories → SQLite + ChromaDB
```

**Key decisions:**
- UI served by existing FastAPI server (no separate frontend server)
- HTMX for dynamic updates (no SPA framework)
- Alpine.js for client-side interactivity
- Tailwind CSS via CDN for styling
- PDF.js for document preview (optional, phase 2)

---

## Features (Priority Order)

### Phase 1: Core Browsing & Search (Week 1-2)

| Feature | Description | Effort |
|---------|-------------|--------|
| Document list | Paginated table with columns: title, date, status, tags | Medium |
| Filtering | Filter by status, tag, date range | Medium |
| Sorting | Sort by date, title, status | Low |
| Search bar | Keyword search with real-time results | Medium |
| Search modes | Toggle: keyword / semantic / hybrid | Low |
| Result highlighting | Show matching text snippets in results | Medium |
| Document detail view | Full metadata + extracted text | Medium |
| Page navigation | Jump to specific page in document | Low |

### Phase 2: Tag Management & Upload (Week 2-3)

| Feature | Description | Effort |
|---------|-------------|--------|
| Tag display | Show tags on document cards | Low |
| Add tag | Modal or inline form to add tags | Low |
| Remove tag | Click to remove with confirmation | Low |
| Tag browser | Browse all tags with document counts | Low |
| Bulk tag | Select multiple docs → apply tag | Medium |
| Upload interface | Drag & drop file upload area | Medium |
| Upload progress | Show upload + processing status | Medium |
| Upload queue | List pending/processing uploads | Low |

### Phase 3: Settings & Polish (Week 3-4)

| Feature | Description | Effort |
|---------|-------------|--------|
| Settings panel | Configure watch directories | Low |
| System status | Show queue length, storage usage | Low |
| Responsive design | Tablet-friendly layout | Medium |
| Dark mode | Optional dark theme | Low |
| Keyboard shortcuts | Power user navigation | Low |
| PDF preview | Embedded PDF viewer (PDF.js) | Medium |

---

## Implementation Steps

### Step 1: Project Structure

Create the web UI package:

```
src/librarian/
└── web/
    ├── __init__.py
    ├── router.py           # FastAPI router for /ui routes
    ├── templates/
    │   ├── base.html       # Base template with layout
    │   ├── index.html      # Dashboard / document list
    │   ├── search.html     # Search results page
    │   ├── document.html   # Document detail view
    │   ├── tags.html       # Tag browser
    │   ├── upload.html     # Upload interface
    │   └── settings.html   # Settings panel
    └── static/
        ├── css/
        │   └── style.css   # Custom styles (Tailwind via CDN)
        └── js/
            ├── app.js      # Main JS (Alpine.js components)
            └── htmx.min.js # HTMX library
```

### Step 2: Add Web Dependencies

Update `pyproject.toml`:

```toml
[project.optional-dependencies]
web = [
    "jinja2>=3.1",
]
```

### Step 3: Create Base Template

**File:** `src/librarian/web/templates/base.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Librarian{% endblock %}</title>

    <!-- Tailwind CSS via CDN -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- HTMX -->
    <script src="{{ url_for('static', path='js/htmx.min.js') }}"></script>

    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

    {% block head %}{% endblock %}
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Navigation -->
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex">
                    <a href="/ui/" class="flex items-center">
                        <span class="text-xl font-bold text-gray-900">📚 Librarian</span>
                    </a>
                    <div class="hidden sm:ml-6 sm:flex sm:space-x-8">
                        <a href="/ui/" class="nav-link {% if request.url.path == '/ui/' %}active{% endif %}">Documents</a>
                        <a href="/ui/tags" class="nav-link {% if '/tags' in request.url.path %}active{% endif %}">Tags</a>
                        <a href="/ui/upload" class="nav-link {% if '/upload' in request.url.path %}active{% endif %}">Upload</a>
                        <a href="/ui/settings" class="nav-link {% if '/settings' in request.url.path %}active{% endif %}">Settings</a>
                    </div>
                </div>

                <!-- Search Bar -->
                <div class="flex items-center">
                    <form action="/ui/search" method="get" class="flex">
                        <input type="text"
                               name="q"
                               placeholder="Search documents..."
                               class="w-64 px-4 py-2 border border-gray-300 rounded-l-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                               value="{{ query|default('') }}">
                        <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700">
                            Search
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {% block content %}{% endblock %}
    </main>

    <!-- Toast Notifications -->
    <div id="toast-container" class="fixed bottom-4 right-4 space-y-2"></div>

    <style>
        .nav-link {
            @apply inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900;
        }
        .nav-link.active {
            @apply text-blue-600 border-b-2 border-blue-600;
        }
    </style>

    {% block scripts %}{% endblock %}
</body>
</html>
```

### Step 4: Create Document List (Dashboard)

**File:** `src/librarian/web/templates/index.html`

```html
{% extends "base.html" %}

{% block title %}Documents - Librarian{% endblock %}

{% block content %}
<div class="px-4 sm:px-0">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-2xl font-bold text-gray-900">Documents</h1>
        <a href="/ui/upload" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            + Upload
        </a>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-lg shadow p-4 mb-6" x-data="{ showFilters: false }">
        <div class="flex items-center justify-between">
            <div class="flex space-x-4">
                <!-- Status Filter -->
                <select name="status" class="px-3 py-2 border border-gray-300 rounded-md" hx-get="/ui/documents" hx-trigger="change" hx-target="#document-list">
                    <option value="">All Status</option>
                    <option value="processed" {% if status == 'processed' %}selected{% endif %}>Processed</option>
                    <option value="pending" {% if status == 'pending' %}selected{% endif %}>Pending</option>
                    <option value="error" {% if status == 'error' %}selected{% endif %}>Error</option>
                </select>

                <!-- Tag Filter -->
                <select name="tag" class="px-3 py-2 border border-gray-300 rounded-md" hx-get="/ui/documents" hx-trigger="change" hx-target="#document-list">
                    <option value="">All Tags</option>
                    {% for tag in tags %}
                    <option value="{{ tag.name }}" {% if tag_filter == tag.name %}selected{% endif %}>{{ tag.name }} ({{ tag.count }})</option>
                    {% endfor %}
                </select>
            </div>

            <!-- Sort -->
            <select name="sort" class="px-3 py-2 border border-gray-300 rounded-md">
                <option value="created_desc">Newest First</option>
                <option value="created_asc">Oldest First</option>
                <option value="title">Title A-Z</option>
            </select>
        </div>
    </div>

    <!-- Document List -->
    <div id="document-list" class="bg-white rounded-lg shadow overflow-hidden">
        {% if documents %}
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tags</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pages</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for doc in documents %}
                <tr class="hover:bg-gray-50 cursor-pointer" onclick="window.location='/ui/document/{{ doc.id }}'">
                    <td class="px-6 py-4">
                        <div class="text-sm font-medium text-gray-900">{{ doc.title or doc.filename }}</div>
                        <div class="text-sm text-gray-500">{{ doc.filename }}</div>
                    </td>
                    <td class="px-6 py-4">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full
                            {% if doc.status == 'processed' %}bg-green-100 text-green-800
                            {% elif doc.status == 'pending' %}bg-yellow-100 text-yellow-800
                            {% elif doc.status == 'processing' %}bg-blue-100 text-blue-800
                            {% else %}bg-red-100 text-red-800{% endif %}">
                            {{ doc.status }}
                        </span>
                    </td>
                    <td class="px-6 py-4">
                        <div class="flex flex-wrap gap-1">
                            {% for tag in doc.tags %}
                            <span class="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800">{{ tag.name }}</span>
                            {% endfor %}
                        </div>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500">
                        {{ doc.created_at.strftime('%Y-%m-%d') }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500">
                        {{ doc.page_count or '-' }}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <!-- Pagination -->
        {% if total_pages > 1 %}
        <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
            <div class="flex-1 flex justify-between sm:hidden">
                <a href="?page={{ page - 1 }}" class="{% if page == 1 %}opacity-50 cursor-not-allowed{% endif %}">Previous</a>
                <a href="?page={{ page + 1 }}" class="{% if page == total_pages %}opacity-50 cursor-not-allowed{% endif %}">Next</a>
            </div>
            <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                    <p class="text-sm text-gray-700">
                        Showing <span class="font-medium">{{ (page - 1) * limit + 1 }}</span>
                        to <span class="font-medium">{{ [page * limit, total] | min }}</span>
                        of <span class="font-medium">{{ total }}</span> results
                    </p>
                </div>
                <div>
                    <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                        {% for p in range(1, total_pages + 1) %}
                        <a href="?page={{ p }}"
                           class="{% if p == page %}bg-blue-50 border-blue-500 text-blue-600{% else %}bg-white text-gray-500{% endif %}
                                  relative inline-flex items-center px-4 py-2 border text-sm font-medium">
                            {{ p }}
                        </a>
                        {% endfor %}
                    </nav>
                </div>
            </div>
        </div>
        {% endif %}

        {% else %}
        <div class="text-center py-12">
            <p class="text-gray-500">No documents found.</p>
            <a href="/ui/upload" class="mt-4 inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Upload your first document
            </a>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

### Step 5: Create Document Detail View

**File:** `src/librarian/web/templates/document.html`

```html
{% extends "base.html" %}

{% block title %}{{ document.title or document.filename }} - Librarian{% endblock %}

{% block content %}
<div class="px-4 sm:px-0">
    <!-- Breadcrumb -->
    <nav class="mb-4">
        <a href="/ui/" class="text-blue-600 hover:text-blue-800">Documents</a>
        <span class="mx-2 text-gray-400">/</span>
        <span class="text-gray-600">{{ document.title or document.filename }}</span>
    </nav>

    <!-- Document Header -->
    <div class="bg-white rounded-lg shadow p-6 mb-6">
        <div class="flex justify-between items-start">
            <div>
                <h1 class="text-2xl font-bold text-gray-900">{{ document.title or document.filename }}</h1>
                <p class="text-gray-500 mt-1">{{ document.filename }}</p>
            </div>
            <div class="flex space-x-2">
                <button class="px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50">
                    Download
                </button>
                <button class="px-3 py-2 text-red-600 border border-red-300 rounded-md hover:bg-red-50">
                    Delete
                </button>
            </div>
        </div>

        <!-- Metadata Grid -->
        <div class="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
                <dt class="text-sm font-medium text-gray-500">Status</dt>
                <dd class="mt-1">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full
                        {% if document.status == 'processed' %}bg-green-100 text-green-800
                        {% elif document.status == 'pending' %}bg-yellow-100 text-yellow-800
                        {% else %}bg-red-100 text-red-800{% endif %}">
                        {{ document.status }}
                    </span>
                </dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-gray-500">Pages</dt>
                <dd class="mt-1 text-sm text-gray-900">{{ document.page_count or '-' }}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-gray-500">Added</dt>
                <dd class="mt-1 text-sm text-gray-900">{{ document.created_at.strftime('%Y-%m-%d %H:%M') }}</dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-gray-500">Size</dt>
                <dd class="mt-1 text-sm text-gray-900">{{ document.file_size_mb }} MB</dd>
            </div>
        </div>

        <!-- Tags -->
        <div class="mt-6" x-data="{ adding: false }">
            <dt class="text-sm font-medium text-gray-500 mb-2">Tags</dt>
            <dd class="flex flex-wrap gap-2">
                {% for tag in document.tags %}
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800">
                    {{ tag.name }}
                    <button class="ml-2 text-blue-600 hover:text-blue-800"
                            hx-delete="/api/v1/documents/{{ document.id }}/tags/{{ tag.name }}"
                            hx-target="closest span"
                            hx-swap="outerHTML">
                        &times;
                    </button>
                </span>
                {% endfor %}

                <!-- Add Tag Button -->
                <button @click="adding = true" x-show="!adding"
                        class="px-3 py-1 rounded-full text-sm border-2 border-dashed border-gray-300 text-gray-500 hover:border-gray-400">
                    + Add tag
                </button>

                <!-- Add Tag Form -->
                <form x-show="adding" x-cloak
                      @submit.prevent="adding = false"
                      hx-post="/api/v1/documents/{{ document.id }}/tags"
                      hx-target="previousElementSibling"
                      class="inline-flex items-center">
                    <input type="text" name="tag" placeholder="Tag name"
                           class="px-3 py-1 rounded-full text-sm border border-gray-300 focus:ring-2 focus:ring-blue-500">
                    <button type="submit" class="ml-2 px-3 py-1 bg-blue-600 text-white rounded-full text-sm">Add</button>
                </form>
            </dd>
        </div>
    </div>

    <!-- Document Content -->
    <div class="bg-white rounded-lg shadow">
        <div class="border-b border-gray-200 px-6 py-4">
            <h2 class="text-lg font-medium text-gray-900">Content</h2>
        </div>

        <!-- Page Navigation -->
        <div class="border-b border-gray-200 px-6 py-3 bg-gray-50 flex items-center justify-between" x-data="{ page: {{ current_page or 1 }} }">
            <div class="flex items-center space-x-2">
                <button @click="page = Math.max(1, page - 1)"
                        :disabled="page === 1"
                        class="px-3 py-1 border border-gray-300 rounded disabled:opacity-50">
                    ← Previous
                </button>
                <span class="text-sm text-gray-600">
                    Page <input type="number" x-model="page" min="1" max="{{ document.page_count }}"
                                class="w-12 text-center border border-gray-300 rounded px-1 py-0.5">
                    of {{ document.page_count }}
                </span>
                <button @click="page = Math.min({{ document.page_count }}, page + 1)"
                        :disabled="page === {{ document.page_count }}"
                        class="px-3 py-1 border border-gray-300 rounded disabled:opacity-50">
                    Next →
                </button>
            </div>
            <div class="text-sm text-gray-500">
                {{ chunks|length }} chunks on this page
            </div>
        </div>

        <!-- Content Text -->
        <div class="p-6 prose max-w-none">
            {% for chunk in chunks %}
            <div class="mb-4 p-4 bg-gray-50 rounded" id="chunk-{{ chunk.id }}">
                <div class="text-xs text-gray-400 mb-2">Chunk {{ loop.index }}</div>
                <div class="text-gray-700 whitespace-pre-wrap">{{ chunk.text }}</div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
```

### Step 6: Create Search Results Page

**File:** `src/librarian/web/templates/search.html`

```html
{% extends "base.html" %}

{% block title %}Search: {{ query }} - Librarian{% endblock %}

{% block content %}
<div class="px-4 sm:px-0">
    <!-- Search Header -->
    <div class="bg-white rounded-lg shadow p-6 mb-6">
        <form action="/ui/search" method="get" class="flex space-x-4">
            <input type="text" name="q" value="{{ query }}"
                   placeholder="Search documents..."
                   class="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500">
            <select name="mode" class="px-3 py-2 border border-gray-300 rounded-md">
                <option value="hybrid" {% if mode == 'hybrid' %}selected{% endif %}>Hybrid</option>
                <option value="keyword" {% if mode == 'keyword' %}selected{% endif %}>Keyword</option>
                <option value="semantic" {% if mode == 'semantic' %}selected{% endif %}>Semantic</option>
            </select>
            <button type="submit" class="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                Search
            </button>
        </form>

        {% if query %}
        <p class="mt-4 text-sm text-gray-600">
            Found <strong>{{ total }}</strong> results for "<em>{{ query }}</em>" using {{ mode }} search
        </p>
        {% endif %}
    </div>

    <!-- Results -->
    {% if results %}
    <div class="space-y-4">
        {% for result in results %}
        <div class="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow cursor-pointer"
             onclick="window.location='/ui/document/{{ result.document_id }}'">
            <div class="flex justify-between items-start mb-2">
                <h3 class="text-lg font-medium text-gray-900">{{ result.title or result.filename }}</h3>
                <span class="text-sm text-gray-500">Score: {{ "%.2f"|format(result.score) }}</span>
            </div>

            <!-- Matched Text -->
            <div class="text-gray-600 text-sm mb-4">
                {{ result.highlighted_text|safe if result.highlighted_text else result.text[:300] + '...' }}
            </div>

            <!-- Metadata -->
            <div class="flex items-center space-x-4 text-xs text-gray-500">
                <span>{{ result.filename }}</span>
                <span>•</span>
                <span>Page {{ result.page_number or '?' }}</span>
                {% if result.tags %}
                <span>•</span>
                <div class="flex space-x-1">
                    {% for tag in result.tags %}
                    <span class="px-2 py-0.5 bg-blue-100 text-blue-800 rounded">{{ tag }}</span>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>

    <!-- Pagination -->
    {% if total_pages > 1 %}
    <div class="mt-6 flex justify-center">
        <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
            {% for p in range(1, total_pages + 1) %}
            <a href="?q={{ query }}&mode={{ mode }}&page={{ p }}"
               class="{% if p == page %}bg-blue-50 border-blue-500 text-blue-600{% else %}bg-white text-gray-500{% endif %}
                      relative inline-flex items-center px-4 py-2 border text-sm font-medium">
                {{ p }}
            </a>
            {% endfor %}
        </nav>
    </div>
    {% endif %}

    {% elif query %}
    <div class="text-center py-12 bg-white rounded-lg shadow">
        <p class="text-gray-500">No results found for "{{ query }}"</p>
        <p class="text-sm text-gray-400 mt-2">Try different keywords or switch search mode</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

### Step 7: Create Upload Interface

**File:** `src/librarian/web/templates/upload.html`

```html
{% extends "base.html" %}

{% block title %}Upload - Librarian{% endblock %}

{% block content %}
<div class="px-4 sm:px-0">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Upload Documents</h1>

    <!-- Drop Zone -->
    <div class="bg-white rounded-lg shadow p-8 mb-6"
         x-data="{ dragging: false, files: [] }"
         @dragover.prevent="dragging = true"
         @dragleave.prevent="dragging = false"
         @drop.prevent="dragging = false; files = [...$event.dataTransfer.files]; $refs.fileInput.files = $event.dataTransfer.files">

        <div class="border-2 border-dashed rounded-lg p-12 text-center"
             :class="dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'">

            <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>

            <p class="mt-4 text-lg text-gray-600">
                Drag and drop files here, or
                <label class="text-blue-600 hover:text-blue-800 cursor-pointer">
                    browse
                    <input type="file" x-ref="fileInput" multiple accept=".pdf" class="hidden"
                           @change="files = [...$event.target.files]">
                </label>
            </p>

            <p class="mt-2 text-sm text-gray-500">PDF files only, max 50MB each</p>
        </div>

        <!-- Selected Files -->
        <div x-show="files.length > 0" class="mt-6">
            <h3 class="text-sm font-medium text-gray-700 mb-2">Selected Files</h3>
            <ul class="space-y-2">
                <template x-for="file in files" :key="file.name">
                    <li class="flex items-center justify-between bg-gray-50 rounded px-4 py-2">
                        <span class="text-sm text-gray-700" x-text="file.name"></span>
                        <span class="text-xs text-gray-500" x-text="(file.size / 1024 / 1024).toFixed(2) + ' MB'"></span>
                    </li>
                </template>
            </ul>

            <button class="mt-4 w-full px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
                    @click="uploadFiles()">
                Upload <span x-text="files.length"></span> file(s)
            </button>
        </div>
    </div>

    <!-- Upload Queue -->
    <div class="bg-white rounded-lg shadow">
        <div class="border-b border-gray-200 px-6 py-4">
            <h2 class="text-lg font-medium text-gray-900">Upload Queue</h2>
        </div>

        <div class="divide-y divide-gray-200">
            <div class="px-6 py-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center">
                        <div class="text-sm font-medium text-gray-900">No recent uploads</div>
                    </div>
                </div>
                <p class="text-sm text-gray-500 mt-1">Upload files to see them here</p>
            </div>
        </div>
    </div>
</div>

{% block scripts %}
<script>
function uploadFiles() {
    // HTMX or fetch upload implementation
}
</script>
{% endblock %}
{% endblock %}
```

### Step 8: Create FastAPI Router

**File:** `src/librarian/web/router.py`

```python
"""Web UI routes for Librarian."""

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from librarian.services.document import DocumentService
from librarian.services.search import SearchService
from librarian.services.tag import TagService
from librarian.services.stats import StatsService

router = APIRouter(prefix="/ui", tags=["ui"])

# Jinja2 setup
env = Environment(loader=FileSystemLoader("src/librarian/web/templates"))


@router.get("/", response_class=HTMLResponse)
async def document_list(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    tag: str | None = None,
    sort: str = Query("created_desc"),
):
    """Document list / dashboard."""
    doc_service = DocumentService()
    tag_service = TagService()

    # Get documents
    offset = (page - 1) * limit
    documents, total = doc_service.list_documents(
        limit=limit,
        offset=offset,
        status=status,
        tag=tag,
        sort=sort,
    )

    # Get all tags for filter
    tags = tag_service.get_all_tags_with_counts()

    # Pagination
    total_pages = (total + limit - 1) // limit

    template = env.get_template("index.html")
    return template.render(
        request=request,
        documents=documents,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        status=status,
        tag_filter=tag,
        tags=tags,
        sort=sort,
    )


@router.get("/document/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: int, page: int = Query(1, ge=1)):
    """Document detail view with content."""
    doc_service = DocumentService()

    document = doc_service.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = doc_service.get_document_text(doc_id, page_start=page, page_end=page)

    template = env.get_template("document.html")
    return template.render(
        request=request,
        document=document,
        chunks=chunks,
        current_page=page,
    )


@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query(""),
    mode: str = Query("hybrid"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Search results page."""
    if not q:
        template = env.get_template("search.html")
        return template.render(request=request, query="", results=[], total=0, mode=mode, page=1, total_pages=0)

    search_service = SearchService()

    offset = (page - 1) * limit
    results, total = search_service.search(
        query=q,
        mode=mode,
        limit=limit,
        offset=offset,
    )

    total_pages = (total + limit - 1) // limit

    template = env.get_template("search.html")
    return template.render(
        request=request,
        query=q,
        mode=mode,
        results=results,
        total=total,
        page=page,
        total_pages=total_pages,
    )


@router.get("/tags", response_class=HTMLResponse)
async def tag_browser(request: Request):
    """Tag browser page."""
    tag_service = TagService()
    tags = tag_service.get_all_tags_with_counts()

    template = env.get_template("tags.html")
    return template.render(request=request, tags=tags)


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Upload interface."""
    template = env.get_template("upload.html")
    return template.render(request=request)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings panel."""
    stats_service = StatsService()
    stats = stats_service.get_library_stats()

    template = env.get_template("settings.html")
    return template.render(request=request, stats=stats)
```

### Step 9: Register Router in Main App

**File:** `src/librarian/__main__.py` (update)

```python
# Add web UI router
from librarian.web.router import router as web_router
app.include_router(web_router)

# Static files
from fastapi.staticfiles import StaticFiles
app.mount("/ui/static", StaticFiles(directory="src/librarian/web/static"), name="static")
```

### Step 10: Add CLI Command

```python
# Add to CLI
@cli.command()
def ui():
    """Start the web UI server."""
    import uvicorn
    uvicorn.run("librarian:app", host="0.0.0.0", port=8000, reload=True)
```

---

## Testing Strategy

### Unit Tests

1. **Router tests:**
   - Each route returns correct status code
   - Templates render without errors
   - Query parameters parsed correctly

2. **Integration tests:**
   - Full page load with sample data
   - Search returns expected results
   - Pagination works correctly

### Manual Testing Checklist

- [ ] Document list loads
- [ ] Filtering by status works
- [ ] Filtering by tag works
- [ ] Sorting works
- [ ] Pagination works
- [ ] Document detail view loads
- [ ] Page navigation in detail view
- [ ] Tag add/remove works
- [ ] Search returns results
- [ ] Search mode toggle works
- [ ] Upload drag & drop works
- [ ] Upload processes files
- [ ] Settings page loads

---

## Responsive Design

**Breakpoints:**
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

**Key adaptations:**
- Navigation collapses to hamburger on mobile
- Document list becomes cards on mobile
- Filters collapse to dropdown on mobile
- Search bar becomes full-width on mobile

---

## Performance Considerations

1. **Lazy load content:**
   - Document list pagination (50 per page)
   - Search results pagination (20 per page)
   - Document chunks load per page

2. **Caching:**
   - Tag list cached (5 minute TTL)
   - Static assets with cache headers

3. **Database optimization:**
   - Indexed queries for filtering/sorting
   - Count queries optimized

---

## Success Criteria

- [ ] Document list displays with pagination
- [ ] Search works for keyword, semantic, and hybrid modes
- [ ] Document detail view shows metadata and content
- [ ] Tag management works (add/remove)
- [ ] File upload works with drag & drop
- [ ] Settings page shows system status
- [ ] Responsive layout works on tablet
- [ ] All routes return HTML responses
- [ ] Existing tests still pass
- [ ] New tests cover UI routes

---

## Time Estimate

- **Phase 1 (Core Browsing & Search):** 5-8 days
- **Phase 2 (Tag Management & Upload):** 4-6 days
- **Phase 3 (Settings & Polish):** 3-5 days

**Total: 12-19 days (2.5-4 weeks)**

---

## References

- HTMX: https://htmx.org
- Alpine.js: https://alpinejs.dev
- Tailwind CSS: https://tailwindcss.com
- Jinja2: https://jinja.palletsprojects.com
- MILESTONES.md: M8 specification
- ARCHITECTURE.md: Service layer design
