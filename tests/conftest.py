"""Shared test fixtures."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from mymemex.config import AppConfig
from mymemex.storage.database import init_database, get_session, _engine, _session_factory


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temp directory for test data."""
    return tmp_path


@pytest.fixture
def test_config(tmp_dir):
    """Create a test configuration with temp paths."""
    return AppConfig(
        debug=True,
        log_level="DEBUG",
        watch={},
        database={"path": str(tmp_dir / "test.db")},
        server={"host": "127.0.0.1", "port": 0},
    )


@pytest_asyncio.fixture
async def db_session(test_config):
    """Initialize test database and provide a session."""
    import mymemex.storage.database as db_module

    await init_database(test_config.database.path)
    async with get_session() as session:
        yield session

    # Cleanup: dispose engine
    if db_module._engine:
        await db_module._engine.dispose()
        db_module._engine = None
        db_module._session_factory = None


@pytest.fixture
def sample_pdf(tmp_dir):
    """Create a minimal valid PDF for testing."""
    import fitz  # pymupdf

    pdf_path = tmp_dir / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This is a test document with some sample text.\n\n"
                     "It has multiple paragraphs to test text extraction and chunking.\n\n"
                     "The third paragraph contains keywords like insurance, policy, and coverage "
                     "to test full-text search capabilities.")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_pdf_multi_page(tmp_dir):
    """Create a multi-page PDF for testing."""
    import fitz

    pdf_path = tmp_dir / "multi_page.pdf"
    doc = fitz.open()

    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content.\n\n"
                         f"This is page {i + 1} of the test document.\n\n"
                         f"It contains unique text for page number {i + 1}.")

    doc.set_metadata({"title": "Test Multi-Page Document", "author": "Test Author"})
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_pdf_scanned(tmp_dir):
    """Create a scanned-style PDF (image-only page, no embedded text).

    We render text into a raster image, then insert that image into a PDF page.
    PyMuPDF native extraction returns <50 chars for this, triggering the OCR path.
    """
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    pdf_path = tmp_dir / "scanned.pdf"

    # Create a raster image with text
    img = Image.new("RGB", (612, 792), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((72, 72), "Scanned Document OCR Test\n\nThis text exists only as pixels.", fill="black", font=font)
    img_path = tmp_dir / "page.png"
    img.save(str(img_path))

    # Build a PDF with just the image (no selectable text)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(0, 0, 612, 792), filename=str(img_path))
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def real_scanned_pdf():
    """Real-world scanned PDF for integration testing.

    This is a document that requires OCR to extract text.
    Skip test if file doesn't exist (not in repo by default).
    """
    pdf_path = Path(__file__).parent / "fixtures" / "ocr-test-document.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Real scanned PDF not found: {pdf_path}")
    return pdf_path
