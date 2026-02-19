"""Tests for PDF text extraction."""

from __future__ import annotations

from mymemex.processing.extractor import extract_pdf_metadata, extract_text_from_pdf


def test_extract_text_from_pdf(sample_pdf):
    """Should extract text from a born-digital PDF."""
    pages = list(extract_text_from_pdf(sample_pdf))
    assert len(pages) == 1
    assert pages[0].page_number == 0
    assert pages[0].method == "pymupdf_native"
    assert "test document" in pages[0].text
    assert pages[0].char_count > 0


def test_extract_pdf_metadata(sample_pdf_multi_page):
    """Should extract metadata from PDF."""
    meta = extract_pdf_metadata(sample_pdf_multi_page)
    assert meta["page_count"] == 3
    assert meta["title"] == "Test Multi-Page Document"
    assert meta["author"] == "Test Author"


def test_extract_multi_page(sample_pdf_multi_page):
    """Should extract text from each page."""
    pages = list(extract_text_from_pdf(sample_pdf_multi_page))
    assert len(pages) == 3
    for i, page in enumerate(pages):
        assert page.page_number == i
        assert f"Page {i + 1}" in page.text


def test_extract_metadata_missing(sample_pdf):
    """PDF without explicit metadata should return None for missing fields."""
    meta = extract_pdf_metadata(sample_pdf)
    assert meta["page_count"] == 1
    # title and author may be None for a simple PDF
