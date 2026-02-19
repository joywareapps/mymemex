"""Text extraction from PDFs using PyMuPDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import structlog

log = structlog.get_logger()


@dataclass
class ExtractedPage:
    """Text extracted from a single page."""

    page_number: int  # 0-based
    text: str
    char_count: int
    method: str  # pymupdf_native, needs_ocr


def extract_text_from_pdf(
    path: Path,
    min_chars_for_native: int = 50,
) -> Iterator[ExtractedPage]:
    """
    Extract text from PDF using PyMuPDF native extraction.

    For ~60% of PDFs (born-digital), this gives instant text.
    For scanned PDFs, returns empty text (to be filled by OCR in M5).

    Yields:
        ExtractedPage for each page
    """
    import fitz  # pymupdf

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        log.error("Failed to open PDF", path=str(path), error=str(e))
        raise

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Try native text extraction
            text = page.get_text("text")

            if len(text.strip()) >= min_chars_for_native:
                text = _clean_text(text)
                yield ExtractedPage(
                    page_number=page_num,
                    text=text,
                    char_count=len(text),
                    method="pymupdf_native",
                )
            else:
                # Needs OCR (will be handled in M5)
                yield ExtractedPage(
                    page_number=page_num,
                    text="",
                    char_count=0,
                    method="needs_ocr",
                )
    finally:
        doc.close()


def extract_pdf_metadata(path: Path) -> dict:
    """Extract PDF metadata (title, author, page count)."""
    import fitz

    try:
        doc = fitz.open(str(path))
        metadata = doc.metadata or {}
        page_count = len(doc)
        doc.close()

        return {
            "title": metadata.get("title") or None,
            "author": metadata.get("author") or None,
            "page_count": page_count,
            "created_date": metadata.get("creationDate") or None,
        }
    except Exception:
        return {"title": None, "author": None, "page_count": 0, "created_date": None}


def _clean_text(text: str) -> str:
    """Clean extracted text."""
    import ftfy

    # Fix encoding issues
    text = ftfy.fix_text(text)

    # Normalize whitespace (preserve paragraph breaks)
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]

    # Remove excessive blank lines (keep max 2)
    result = []
    blank_count = 0
    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                result.append("")
        else:
            blank_count = 0
            result.append(line)

    return "\n".join(result).strip()
