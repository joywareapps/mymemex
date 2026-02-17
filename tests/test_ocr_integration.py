"""Integration tests for OCR with real scanned PDFs.

These tests use actual scanned documents to validate OCR functionality.
Requires Tesseract to be installed.

Run with:
    pytest tests/test_ocr_integration.py -v -s

For audit logging (saves to tests/fixtures/ocr-audit.log):
    pytest tests/test_ocr_integration.py -v -s --audit

Prerequisites:
    # Install Tesseract
    sudo apt-get install tesseract-ocr  # Debian/Ubuntu
    brew install tesseract              # macOS

    # Install language packs (if needed)
    sudo apt-get install tesseract-ocr-deu  # German
    sudo apt-get install tesseract-ocr-srp  # Serbian
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from datetime import datetime

import pytest

from librarian.config import OCRConfig
from librarian.processing.ocr import ocr_page, TESSERACT_AVAILABLE
from librarian.processing.extractor import extract_text_from_pdf


# Audit logging setup
AUDIT_LOG = Path(__file__).parent / "fixtures" / "ocr-audit.log"


def setup_audit_logging():
    """Set up file logging for OCR audit trail."""
    AUDIT_LOG.parent.mkdir(exist_ok=True)
    
    handler = logging.FileHandler(AUDIT_LOG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    
    logger = logging.getLogger("ocr_audit")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    return logger


def get_audit_logger():
    """Get or create the audit logger."""
    logger = logging.getLogger("ocr_audit")
    if not logger.handlers:
        return setup_audit_logging()
    return logger


# Skip all tests in this module if Tesseract not installed
pytestmark = pytest.mark.skipif(
    not TESSERACT_AVAILABLE,
    reason="Tesseract not installed. Run: sudo apt-get install tesseract-ocr",
)


# =============================================================================
# REAL SCANNED PDF TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_scanned_pdf_needs_ocr(real_scanned_pdf):
    """Verify the real scanned PDF has no native text."""
    pages = list(extract_text_from_pdf(real_scanned_pdf))

    assert len(pages) > 0, "PDF should have at least one page"

    # At least one page should need OCR (little to no native text)
    needs_ocr_pages = [p for p in pages if p.method == "needs_ocr" or len(p.text.strip()) < 50]

    assert len(needs_ocr_pages) > 0, (
        f"Expected scanned PDF to have pages needing OCR. "
        f"Got methods: {[p.method for p in pages]}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_scanned_pdf_ocr_extraction(real_scanned_pdf):
    """Extract text from real scanned PDF using OCR."""
    config = OCRConfig(enabled=True, language="eng", dpi=300)
    audit = get_audit_logger()

    # Get number of pages
    import fitz
    doc = fitz.open(str(real_scanned_pdf))
    num_pages = len(doc)
    doc.close()

    print(f"\nOCR test: {real_scanned_pdf.name} ({num_pages} pages)")

    # OCR first page
    text = await ocr_page(real_scanned_pdf, 0, config)

    print(f"Extracted text ({len(text)} chars):")
    print("-" * 40)
    print(text[:500] if len(text) > 500 else text)
    print("-" * 40)

    # Audit log
    audit.info(
        "OCR extraction completed",
        extra={
            "pdf_name": real_scanned_pdf.name,
            "pages": num_pages,
            "chars_extracted": len(text),
            "config_dpi": config.dpi,
            "config_lang": config.language,
        }
    )
    audit.info(f"Extracted text preview:\n{text[:500]}")

    assert len(text) > 50, (
        f"Expected at least 50 chars of OCR text, got {len(text)}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_scanned_pdf_multipage(real_scanned_pdf):
    """OCR multiple pages from a real scanned PDF."""
    config = OCRConfig(enabled=True, language="eng", dpi=300)

    import fitz
    doc = fitz.open(str(real_scanned_pdf))
    num_pages = len(doc)
    doc.close()

    # OCR first 3 pages (or all if fewer)
    pages_to_ocr = min(3, num_pages)
    extracted_texts = []

    for page_num in range(pages_to_ocr):
        text = await ocr_page(real_scanned_pdf, page_num, config)
        extracted_texts.append(text)
        print(f"\nPage {page_num + 1}: {len(text)} chars")

    # At least one page should have meaningful content
    total_chars = sum(len(t) for t in extracted_texts)
    assert total_chars > 100, (
        f"Expected at least 100 total chars across {pages_to_ocr} pages, got {total_chars}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ocr_language_detection(real_scanned_pdf):
    """Test OCR with different language settings."""
    config_eng = OCRConfig(enabled=True, language="eng", dpi=300)

    text_eng = await ocr_page(real_scanned_pdf, 0, config_eng)

    # English should work
    assert len(text_eng) > 50, "English OCR should extract text"

    # Note: You can add language-specific tests if the document is in a specific language
    # For German: config_deu = OCRConfig(enabled=True, language="deu", dpi=300)
    # For Serbian: config_srp = OCRConfig(enabled=True, language="srp", dpi=300)


# =============================================================================
# OCR QUALITY TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_ocr_dpi_quality(real_scanned_pdf):
    """Compare OCR quality at different DPI settings."""
    results = {}

    for dpi in [150, 300, 400]:
        config = OCRConfig(enabled=True, language="eng", dpi=dpi)
        text = await ocr_page(real_scanned_pdf, 0, config)
        results[dpi] = len(text)
        print(f"DPI {dpi}: {len(text)} chars")

    # Higher DPI should generally produce more/better text
    # (though not always linearly)
    assert results[300] > 0, "300 DPI should produce some text"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ocr_word_boundaries(real_scanned_pdf):
    """OCR should produce text with proper word boundaries."""
    config = OCRConfig(enabled=True, language="eng", dpi=300)

    text = await ocr_page(real_scanned_pdf, 0, config)

    # Check that we have words, not just one long string
    words = text.split()
    assert len(words) > 10, f"Expected at least 10 words, got {len(words)}"

    # Average word length should be reasonable (2-15 chars)
    avg_word_len = sum(len(w) for w in words) / len(words)
    assert 2 < avg_word_len < 15, (
        f"Average word length {avg_word_len:.1f} seems off"
    )


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.integration
async def test_ocr_latency(real_scanned_pdf):
    """Measure OCR processing time."""
    import time
    audit = get_audit_logger()

    config = OCRConfig(enabled=True, language="eng", dpi=300)

    start = time.time()
    text = await ocr_page(real_scanned_pdf, 0, config)
    elapsed = time.time() - start

    print(f"\nOCR latency (1 page): {elapsed*1000:.0f}ms")

    # Audit log
    audit.info(
        "OCR latency measured",
        extra={
            "pdf_name": real_scanned_pdf.name,
            "latency_ms": round(elapsed * 1000),
            "chars_extracted": len(text),
        }
    )

    # OCR is slow but should complete within 30 seconds per page
    assert elapsed < 30, f"OCR took {elapsed}s — expected < 30s"
    assert len(text) > 0
