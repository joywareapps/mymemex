# Packaging Librarian as a macOS Apple Silicon App

Analysis of obstacles, licensing, and architecture for distributing Librarian as a native macOS `.app` with local inference on Apple Silicon.

---

## 1. Licensing Blockers

There are **two red flags** in our current dependencies:

| Package | License | Problem |
|---|---|---|
| **PyMuPDF** | AGPL-3.0 | Must open-source entire app, or buy commercial license from Artifex (~$1.5K-$50K) |
| **Poppler** (native dep of `pdf2image`) | GPL-2.0 | Must open-source entire app if bundled. No commercial license available |

Everything else (FastAPI, SQLAlchemy, Pillow, Tesseract, ChromaDB, SQLite, httpx, etc.) is MIT/BSD/Apache-2.0/Public Domain — fine for commercial distribution.

**Fix:** Replace both with **`pypdfium2`** (Apache-2.0, wraps Google's PDFium). It handles both PDF text extraction and PDF-to-image rendering, eliminating both problems in one swap. Alternatively, on macOS specifically, Apple's native PDFKit/Quartz APIs are available at no cost.

### Full Dependency License Audit

#### GREEN — No issues for commercial distribution

| Package | License |
|---|---|
| fastapi | MIT |
| uvicorn | BSD |
| pydantic, pydantic-settings | MIT |
| typer | MIT |
| rich | MIT |
| structlog | MIT OR Apache-2.0 |
| sqlalchemy | MIT |
| alembic | MIT |
| aiosqlite | MIT |
| watchdog | Apache-2.0 |
| python-magic | MIT |
| xxhash | BSD-2-Clause |
| pillow | HPND (permissive) |
| ftfy | Apache-2.0 |
| langdetect | Apache-2.0 |
| httpx | BSD |
| pyyaml | MIT |
| python-multipart | Apache-2.0 |
| jinja2 | BSD |
| pytesseract | Apache-2.0 |
| chromadb | Apache-2.0 |
| mcp (Anthropic) | MIT |
| libmagic (native) | BSD |
| Tesseract OCR (native) | Apache-2.0 |
| SQLite (native) | Public Domain |

#### YELLOW — Review carefully

| Package | License | Note |
|---|---|---|
| chromadb | Apache-2.0 core | Audit transitive deps for surprises |

#### RED — Incompatible with closed-source distribution

| Package | License | Note |
|---|---|---|
| pymupdf | AGPL-3.0 | Must buy commercial license or replace |
| poppler-utils | GPL-2.0 | Must replace; no commercial license available |
| pdf2image | MIT | Useless without GPL Poppler |

### Recommended Replacements

| Problem Package | Replacement | License | Notes |
|---|---|---|---|
| **pymupdf** | `pypdfium2` | Apache-2.0 | Wraps Google's PDFium. Covers text extraction and rendering |
| **pymupdf** | `pdfplumber` + `pdfminer.six` | MIT | Good for text extraction, not rendering |
| **pdf2image** + poppler | `pypdfium2` | Apache-2.0 | Renders PDF pages to images directly |
| **pdf2image** + poppler | macOS PDFKit/Quartz | Apple SDK | macOS only; requires native code bridge |

The single cleanest fix is to replace both `pymupdf` and `pdf2image`+`poppler` with **`pypdfium2`**, which handles both PDF text extraction and PDF-to-image rendering — eliminating both GPL and AGPL problems in one move.

---

## 2. Packaging Python as a .app

| Approach | Pros | Cons |
|---|---|---|
| **py2app** | Mature, macOS-native | Python-only, large bundles (~200MB+) |
| **PyInstaller** | Cross-platform, well-tested | Large bundles, startup time |
| **Nuitka** | Compiles to C, smaller/faster | Complex build, long compile times |
| **Tauri + Python backend** | Native macOS chrome, tiny frontend | Two runtimes (Rust+Python), more complex |
| **Swift/SwiftUI shell + bundled Python** | Most "native" feel, App Store possible | Significant frontend rewrite |

The pragmatic path: **Tauri or Swift shell** wrapping the existing FastAPI backend (bundled via PyInstaller/py2app), with the web UI served locally. The user opens the app, it starts uvicorn on localhost, and the native window loads `http://localhost:8000/ui/`.

---

## 3. Local Inference on Apple Silicon

Apple Silicon has excellent ML capabilities via the Neural Engine and Metal GPU.

| Runtime | Apple Silicon Support | License | Notes |
|---|---|---|---|
| **MLX** (Apple) | Native, best performance | MIT | Apple's own framework. Supports GGUF, safetensors |
| **llama.cpp** (via `llama-cpp-python`) | Native Metal acceleration | MIT | Mature, wide model support |
| **Ollama** | Bundles llama.cpp + Metal | MIT | Easiest UX but separate process |
| **Core ML** | Native Neural Engine | Apple SDK | Requires model conversion, limited model support |

For a self-contained app, **MLX** or **llama.cpp** are the best choices — they compile natively for Apple Silicon, use Metal for GPU acceleration, and are MIT licensed. They would replace the `httpx`-based `OllamaClient` with direct in-process inference.

---

## 4. Model Distribution

### Can users choose models from HuggingFace?

Yes. The app ships with **no models**. On first launch, a setup wizard lets the user pick:

- An **embedding model** (small, ~50-100MB)
- A **classification/extraction LLM** (3B-7B, ~2-4GB quantized)

Models download from HuggingFace into `~/Library/Application Support/Librarian/models/` using the `huggingface_hub` Python library (Apache-2.0).

### Model Format

- **GGUF format** (llama.cpp/MLX): Thousands of quantized models on HuggingFace. Download on-demand.
- **Embedding models**: `nomic-embed-text`, `all-MiniLM-L6-v2`, `bge-small-en` — all available as GGUF or safetensors, with permissive licenses (Apache-2.0/MIT).

### Suitable LLMs with Permissive Licenses

| Model | License | Size (Q4) | Notes |
|---|---|---|---|
| Llama 3.2 3B | Meta Community License | ~2GB | Free for <700M monthly users |
| Mistral 7B | Apache-2.0 | ~4GB | Fully permissive |
| Phi-3 Mini | MIT | ~2GB | Fully permissive |
| Qwen2.5 3B/7B | Apache-2.0 | ~2-4GB | Fully permissive |

---

## 5. Obstacles Summary

| Obstacle | Severity | Solution |
|---|---|---|
| PyMuPDF AGPL license | **High** | Replace with `pypdfium2` (Apache-2.0) |
| Poppler GPL license | **High** | Replace `pdf2image` with `pypdfium2` or macOS PDFKit |
| App bundle size | Medium | ~300-500MB (Python + deps + Tesseract). Models downloaded separately |
| Python packaging complexity | Medium | py2app/PyInstaller work but need careful testing |
| Code signing + notarization | Medium | Required for macOS distribution. Apple Developer account ($99/yr) |
| Model download UX | Low | First-run wizard with HuggingFace Hub library |
| Tesseract binary bundling | Low | Apache-2.0, include pre-built arm64 binary |
| ChromaDB embedded | Low | Already runs in-process, no server needed |

---

## 6. Target Architecture

### App Bundle

```
Librarian.app/
  Contents/
    MacOS/
      librarian          # PyInstaller/py2app bundle
    Resources/
      tesseract          # Pre-built arm64 binary
      tessdata/          # Language models (eng, deu)
    Frameworks/
      libmagic.dylib     # BSD licensed
      libpdfium.dylib    # Apache-2.0 (replaces PyMuPDF + poppler)
```

### User Data

```
~/Library/Application Support/Librarian/
  librarian.db           # SQLite database
  chromadb/              # Vector store
  models/                # Downloaded from HuggingFace
    nomic-embed-text.gguf
    llama-3.2-3b-Q4_K_M.gguf
```

---

## 7. User Experience

### First Launch

1. User drags `Librarian.app` to `/Applications`, double-clicks
2. **Setup wizard** (3 screens):
   - "Choose your documents folder" — native macOS folder picker, defaults to `~/Documents`
   - "Choose AI model" — list of recommended models with size/speed tradeoffs, "Download" button. Option to skip (AI features disabled, search still works)
   - "Ready!" — shows menu bar icon, opens web UI
3. Model downloads in background with progress in menu bar

### Daily Use

- **Menu bar icon** (always running, like Dropbox/1Password) — shows document count, processing status
- Clicking menu bar icon opens `http://localhost:8000/ui/` in default browser
- Drop PDFs onto the Dock icon or menu bar icon to ingest
- **macOS notifications** when documents finish processing ("Invoice from Finanzamt classified and indexed")
- Documents folder is watched automatically — drop a PDF there, it appears in Librarian

### What It Is NOT

It's not a fully native AppKit/SwiftUI app — the UI is still the web UI in a browser. The native shell handles lifecycle, menu bar, notifications, and drag-and-drop. This is the same model as Ollama, Docker Desktop, and many Electron apps.

---

## 8. macOS-Specific Features

### Must-Have (users expect these)

| Feature | Effort | Notes |
|---|---|---|
| Menu bar icon | 2-3 days | Background process indicator, quick access, status |
| macOS notifications | 1-2 days | Document processing events via `NSUserNotification` |
| Dock icon drag-and-drop | 1-2 days | Drop PDFs onto Dock icon to ingest |
| `~/Library/Application Support/` paths | 1 day | Correct macOS data location |
| Code signing + notarization | 2-3 days | Required — Gatekeeper blocks unsigned apps |
| Dark mode follows system | 0 days | Already implemented in web UI |
| Cmd keyboard shortcuts | 0 days | Browser handles this automatically |

### Nice-to-Have (differentiators)

| Feature | Effort | Notes |
|---|---|---|
| Global hotkey (`Cmd+Shift+L`) | 1 day | Open Librarian search from anywhere |
| Spotlight integration | ~1 week | Register as Spotlight importer, document content appears in system search |
| Quick Look plugin | 2-3 days | Press Space on a PDF in Finder to preview Librarian metadata |
| Share Extension | 2-3 days | "Send to Librarian" in the macOS share sheet |
| Auto-start on login | 0.5 days | LaunchAgent plist |
| File provider extension | ~2 weeks | Librarian documents as a virtual folder in Finder |

### Skip (not worth the effort)

| Feature | Why Skip |
|---|---|
| Full native SwiftUI UI rewrite | Massive effort, web UI works fine |
| App Store distribution | Sandbox restrictions are painful for file watchers and local servers |
| Universal binary (Intel+ARM) | Intel Macs are dying, target ARM only |
| Touch Bar support | Dead technology |

---

## 9. Effort Estimate

### Phase 1: License-Clean Foundation (1-2 weeks)

| Task | Effort | Notes |
|---|---|---|
| Replace PyMuPDF with pypdfium2 | 3-4 days | Rewrite `extractor.py`, update chunker, run all PDF tests |
| Replace pdf2image+Poppler with pypdfium2 | 1-2 days | OCR image rendering path |
| Update tests, verify full suite | 1 day | |

This is required regardless and benefits all platforms.

### Phase 2: Local Inference (1-2 weeks)

| Task | Effort | Notes |
|---|---|---|
| Add `LlamaCppClient` to `llm_client.py` | 2-3 days | `llama-cpp-python` with Metal, implements same `LLMClient` ABC |
| Add local embedding via llama.cpp or sentence-transformers | 2-3 days | Replace Ollama embedding calls |
| Model manager (download from HuggingFace, list/delete) | 2-3 days | `huggingface_hub` library |
| First-run model selection UI | 1-2 days | New page in web UI |

### Phase 3: macOS App Shell (2-3 weeks)

| Task | Effort | Notes |
|---|---|---|
| PyInstaller/py2app bundle | 3-4 days | Hidden files, native libs, signing — always harder than expected |
| Menu bar agent | 2-3 days | Status icon, dropdown menu, "Open UI" / "Quit" |
| Dock icon + drag-and-drop | 1-2 days | Accept PDF drops on Dock icon |
| macOS notifications | 1-2 days | Document processing events |
| macOS paths | 1 day | Platform-conditional config defaults |
| Auto-start on login | 0.5 days | LaunchAgent |
| Code signing + notarization | 2-3 days | Apple Developer account, `codesign`, `notarytool`, CI |
| DMG installer | 1 day | `create-dmg` or similar |
| Auto-update mechanism | 2-3 days | Sparkle framework or custom |

### Phase 4: Polish (1 week)

| Task | Effort | Notes |
|---|---|---|
| App icon (1024x1024 .icns) | 1 day | Design or commission |
| First-run experience testing | 2 days | Fresh Mac, edge cases, permissions dialogs |
| Crash reporting / error handling | 1 day | Port conflicts, missing permissions |
| "About" window, version display | 0.5 days | |

### Total

| Phase | Duration |
|---|---|
| Phase 1: License cleanup | 1-2 weeks |
| Phase 2: Local inference | 1-2 weeks |
| Phase 3: macOS shell | 2-3 weeks |
| Phase 4: Polish | 1 week |
| **Total** | **5-8 weeks** |

---

## 10. Required Code Changes

Before packaging as a commercial macOS app:

1. **Replace PyMuPDF with pypdfium2** — affects `processing/extractor.py`
2. **Replace pdf2image + Poppler with pypdfium2** — affects OCR image rendering
3. **Add local inference backend** — new `MLXClient` or `LlamaCppClient` in `intelligence/llm_client.py`
4. **Add model manager** — download/select models from HuggingFace
5. **Add macOS app shell** — Tauri or Swift wrapper around the existing web UI
6. **macOS-specific paths** — use `~/Library/Application Support/Librarian/` instead of `~/.local/share/librarian/`
