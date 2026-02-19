"""OCR router for scanned documents."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from ..config import OCRConfig

log = structlog.get_logger()

TESSERACT_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image

    # Check that the tesseract binary is actually reachable
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except ImportError:
    pass
except Exception:
    # pytesseract imported but binary not found (TesseractNotFoundError)
    pass


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

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_number]

        # Render page to image at configured DPI
        mat = fitz.Matrix(config.dpi / 72.0, config.dpi / 72.0)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Run Tesseract OCR
        text = pytesseract.image_to_string(
            img,
            lang=config.language,
            config="--psm 6",  # Assume single uniform block of text
        )

        return text.strip()
    finally:
        doc.close()
