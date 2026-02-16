"""Tests for text chunking."""

from __future__ import annotations

from librarian.processing.chunker import TextChunk, chunk_pages, chunk_text


def test_chunk_short_text():
    """Short text should produce single chunk."""
    chunks = chunk_text("Hello, world!")
    assert len(chunks) == 1
    assert chunks[0].text == "Hello, world!"
    assert chunks[0].chunk_index == 0
    assert chunks[0].char_count == 13


def test_chunk_empty_text():
    """Empty text should produce no chunks."""
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_long_text():
    """Long text should be split into multiple chunks."""
    # Create text longer than max_chars
    paragraphs = [f"Paragraph {i}. " + "x" * 200 for i in range(20)]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.char_count <= 600  # Allow some flexibility


def test_chunk_preserves_page_number():
    """Chunk should preserve page number."""
    chunks = chunk_text("Test text", page_number=5)
    assert chunks[0].page_number == 5


def test_chunk_pages_global_index():
    """chunk_pages should assign global indices across pages."""
    pages = [
        (0, "Page one text content " * 200),
        (1, "Page two text content " * 200),
    ]

    chunks = chunk_pages(pages, max_chars=500)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))  # 0, 1, 2, ...


def test_chunk_pages_empty():
    """Empty pages list should produce no chunks."""
    assert chunk_pages([]) == []


def test_chunk_pages_preserves_page_numbers():
    """Chunks should retain their source page number."""
    pages = [
        (0, "First page content."),
        (2, "Third page content."),
    ]
    chunks = chunk_pages(pages)
    assert chunks[0].page_number == 0
    assert chunks[1].page_number == 2
