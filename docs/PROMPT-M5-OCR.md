# M5 Implementation: OCR Integration for Scanned Documents

**Project:** Librarian - Sovereign Document Intelligence Platform
**Milestone:** M5 - OCR support for scanned PDFs
**Effort:** High (expect 30-45 min)
**Location:** `~/code/librarian`

---

## Overview

Implement OCR (Optical Character Recognition) for scanned PDF documents that don't have embedded text. This enables full-text search for scanned documents.

**Current Status:**
- M1-M4 complete: File watching, text extraction (PyMuPDF), chunking, FTS5 search
- PyMuPDF already detects pages that need OCR (returns empty text)
- Tesseract already installed in Docker image
- OCR config already exists in `config.py` (`ocr.enabled`, `ocr.language`, `ocr.dpi`)

**Goal:**
Enable OCR for pages where PyMuPDF returns <50 chars (configurable threshold).

---

## What to Implement

### 1. OCR Router (`src/librarian/processing/ocr.py`)

Create a new file that handles OCR processing:

```python
"""OCR router for scanned documents."""
import asyncio
from pathlib import Path
from typing import Optional
import structlog

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from ..config import OCRConfig

log = structlog.get_logger()


async def ocr_page(
    pdf_path: Path,
    page_number: int,
    config: OCRConfig,
) -> str:
    """
    Perform OCR on a single PDF page.

    Args:
        pdf_path: Path to PDF file
        page_number: Page number (0-indexed)
        config: OCR configuration

    Returns:
        Extracted text (empty string if OCR unavailable or failed)
    """
    if not config.enabled:
        log.debug("OCR disabled, skipping", page=page_number)
        return ""

    if not TESSERACT_AVAILABLE:
        log.warning("Tesseract not available, cannot OCR", page=page_number)
        return ""

    try:
        # Run OCR in thread pool (CPU-bound operation)
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            _ocr_page_sync,
            pdf_path,
            page_number,
            config,
        )
        return text
    except Exception as e:
        log.error("OCR failed", page=page_number, error=str(e))
        return ""


def _ocr_page_sync(pdf_path: Path, page_number: int, config: OCRConfig) -> str:
    """Synchronous OCR processing (runs in thread pool)."""
    import fitz  # PyMuPDF

    # Render page to image
    doc = fitz.open(str(pdf_path))
    page = doc[page_number]

    # Set DPI for rendering
    mat = fitz.Matrix(config.dpi / 72.0, config.dpi / 72.0)
    pix = page.get_pixmap(matrix=mat)

    # Convert to PIL Image
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # Run Tesseract OCR
    text = pytesseract.image_to_string(
        img,
        lang=config.language,
        config=f"--psm 6",  # Assume single uniform block of text
    )

    doc.close()
    return text.strip()
```

### 2. Update Pipeline (`src/librarian/processing/pipeline.py`)

Modify the `run_ingest_pipeline()` function to use OCR when PyMuPDF returns insufficient text:

```python
# In run_ingest_pipeline(), replace the extraction loop:

from .ocr import ocr_page

async def run_ingest_pipeline(document_id: int, config: AppConfig) -> None:
    # ... existing setup code ...

    # Extract text
    all_chunks = []
    pages_needing_ocr = []

    for page in extract_text_from_pdf(path):
        if page.method == "needs_ocr":
            pages_needing_ocr.append(page.page_number)
            continue

        # Chunk the page text
        page_chunks = chunk_text(page.text, page_number=page.page_number)
        all_chunks.extend(page_chunks)

    # Process OCR pages
    if config.ocr.enabled and pages_needing_ocr:
        log.info("Processing OCR pages", doc_id=doc.id, count=len(pages_needing_ocr))

        for page_num in pages_needing_ocr:
            text = await ocr_page(path, page_num, config.ocr)

            if text:
                # Chunk OCR text
                page_chunks = chunk_text(text, page_number=page_num)
                all_chunks.extend(page_chunks)

                # Store chunks with OCR extraction method
                for chunk in page_chunks:
                    await chunk_repo.create(
                        document_id=doc.id,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        text=chunk.text,
                        char_count=chunk.char_count,
                        extraction_method="tesseract_ocr",
                    )

    # ... rest of existing code ...
```

### 3. Add OCR Tests (`tests/test_ocr.py`)

Create basic tests:

```python
"""Tests for OCR functionality."""

import pytest
from pathlib import Path
from librarian.processing.ocr import ocr_page
from librarian.config import OCRConfig


@pytest.mark.asyncio
async def test_ocr_disabled():
    """OCR should return empty string when disabled."""
    config = OCRConfig(enabled=False)
    # Would need a real PDF to test, but we can check the logic
    text = await ocr_page(Path("/dummy.pdf"), 0, config)
    assert text == ""


@pytest.mark.asyncio
async def test_ocr_page(sample_pdf_scanned, test_config):
    """Test OCR on a scanned PDF page."""
    if not test_config.ocr.enabled:
        pytest.skip("OCR not enabled in test config")

    text = await ocr_page(sample_pdf_scanned, 0, test_config.ocr)
    # Should extract some text from the scanned page
    assert len(text) > 0
```

### 4. Update Dependencies (`pyproject.toml`)

The `ocr` optional dependencies already exist, but verify:

```toml
[project.optional-dependencies]
ocr = [
    "pytesseract>=0.3",
]
```

### 5. Create Test Fixture (`tests/conftest.py`)

Add a fixture for a scanned PDF (image-based, no embedded text):

```python
@pytest.fixture
def sample_pdf_scanned(tmp_dir):
    """Create a scanned PDF (image-only, no embedded text)."""
    import fitz

    pdf_path = tmp_dir / "scanned.pdf"
    doc = fitz.open()

    # Create a page with an image containing text
    page = doc.new_page()

    # For testing, we'll create a simple page
    # In reality, this would be a scanned image
    # For now, just create a blank page
    page.insert_text((72, 72), "Scanned Document Text")

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path
```

---

## Implementation Steps

1. **Create `src/librarian/processing/ocr.py`**
   - Implement OCR router with async support
   - Add Tesseract integration
   - Handle errors gracefully

2. **Update `src/librarian/processing/pipeline.py`**
   - Import `ocr_page`
   - Process pages needing OCR after PyMuPDF extraction
   - Store chunks with `extraction_method="tesseract_ocr"`

3. **Create `tests/test_ocr.py`**
   - Basic OCR tests
   - Mock tests for when Tesseract unavailable

4. **Test the implementation:**
   ```bash
   # Install OCR dependencies
   pip install -e ".[ocr]"

   # Run tests
   pytest tests/test_ocr.py -v
   ```

5. **Validate with real scanned PDF:**
   ```python
   # Test with a real scanned document
   from pathlib import Path
   from librarian.processing.ocr import ocr_page
   from librarian.config import OCRConfig

   config = OCRConfig(enabled=True, language="eng", dpi=300)
   text = await ocr_page(Path("/path/to/scanned.pdf"), 0, config)
   print(text[:200])
   ```

---

## Important Notes

1. **Performance:** OCR is slow (1-3 seconds per page). Run in thread pool.
2. **Accuracy:** Tesseract is good but not perfect. Works best with:
   - High DPI (300+)
   - Clean, straight text
   - English language
3. **Fallback Chain:** PyMuPDF native → Tesseract OCR → (future) cloud OCR
4. **Docker:** Tesseract already installed in Dockerfile (tesseract-ocr, tesseract-ocr-eng)
5. **Config:** Users must enable OCR in `config.yaml`:
   ```yaml
   ocr:
     enabled: true
     language: eng  # or eng+deu for multilingual
     dpi: 300
   ```

---

## Expected Outcome

After M5:
- Scanned PDFs can be processed
- OCR text is extracted and chunked
- OCR text is searchable via FTS5
- Document status shows "ready" even for scanned docs
- Extraction method tracked as "tesseract_ocr"

---

## Files to Create/Modify

**Create:**
- `src/librarian/processing/ocr.py` (new file, ~80 LOC)
- `tests/test_ocr.py` (new file, ~40 LOC)

**Modify:**
- `src/librarian/processing/pipeline.py` (add OCR processing, ~20 LOC changes)
- `tests/conftest.py` (add scanned PDF fixture, ~15 LOC)

**Total:** ~155 lines of new/modified code

---

## Validation Criteria

✅ OCR module created and imports successfully
✅ Tests pass (pytest tests/test_ocr.py)
✅ Scanned PDF processes without errors
✅ OCR text appears in search results
✅ Performance acceptable (<5 sec per page)

---

Start with creating `ocr.py` and getting basic tests working. Then integrate into the pipeline.

Good luck! 🚀
