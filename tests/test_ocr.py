"""Tests for OCR functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from librarian.config import OCRConfig
from librarian.processing.ocr import ocr_page, TESSERACT_AVAILABLE


@pytest.mark.asyncio
async def test_ocr_disabled():
    """OCR should return empty string when disabled."""
    config = OCRConfig(enabled=False)
    text = await ocr_page(Path("/dummy.pdf"), 0, config)
    assert text == ""


@pytest.mark.asyncio
async def test_ocr_unavailable():
    """OCR should return empty string when tesseract is not installed."""
    config = OCRConfig(enabled=True)
    with patch("librarian.processing.ocr.TESSERACT_AVAILABLE", False):
        text = await ocr_page(Path("/dummy.pdf"), 0, config)
    assert text == ""


@pytest.mark.asyncio
async def test_ocr_bad_path():
    """OCR should return empty string for non-existent file."""
    config = OCRConfig(enabled=True)
    text = await ocr_page(Path("/nonexistent/fake.pdf"), 0, config)
    assert text == ""


@pytest.mark.asyncio
@pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")
async def test_ocr_page_extracts_text(sample_pdf_scanned):
    """OCR should extract text from a scanned PDF page."""
    config = OCRConfig(enabled=True, language="eng", dpi=300)
    text = await ocr_page(sample_pdf_scanned, 0, config)
    # Tesseract should find at least some of the rendered text
    assert len(text) > 0
    # Check for key words (case-insensitive, OCR can be imperfect)
    lower = text.lower()
    assert "scanned" in lower or "document" in lower or "ocr" in lower or "test" in lower


def test_scanned_pdf_has_no_native_text(sample_pdf_scanned):
    """Verify the scanned fixture produces a page that needs OCR."""
    from librarian.processing.extractor import extract_text_from_pdf

    pages = list(extract_text_from_pdf(sample_pdf_scanned))
    assert len(pages) == 1
    assert pages[0].method == "needs_ocr"
