"""Text chunking for embedding and search."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    """A chunk of text."""

    text: str
    chunk_index: int
    page_number: int | None
    char_count: int


def chunk_text(
    text: str,
    page_number: int | None = None,
    max_chars: int = 1500,
    overlap_chars: int = 200,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks.

    Strategy:
    1. Split on double newlines (paragraphs)
    2. If still too big, split on single newlines
    3. If still too big, split on sentence boundaries
    4. Last resort: hard split
    """
    if not text.strip():
        return []

    if len(text) <= max_chars:
        return [
            TextChunk(
                text=text.strip(),
                chunk_index=0,
                page_number=page_number,
                char_count=len(text.strip()),
            )
        ]

    # Try paragraph split
    chunks = _split_on_separator(text, "\n\n", max_chars, overlap_chars)
    if chunks is None:
        # Try line split
        chunks = _split_on_separator(text, "\n", max_chars, overlap_chars)
    if chunks is None:
        # Try sentence split
        chunks = _split_on_separator(text, r"(?<=[.!?])\s+", max_chars, overlap_chars, regex=True)
    if chunks is None:
        # Hard split
        chunks = _hard_split(text, max_chars, overlap_chars)

    return [
        TextChunk(text=c, chunk_index=i, page_number=page_number, char_count=len(c))
        for i, c in enumerate(chunks)
    ]


def chunk_pages(
    pages: list[tuple[int, str]],
    max_chars: int = 1500,
    overlap_chars: int = 200,
) -> list[TextChunk]:
    """Chunk text from multiple pages, maintaining global chunk indices."""
    all_chunks: list[TextChunk] = []
    global_index = 0

    for page_number, text in pages:
        page_chunks = chunk_text(text, page_number=page_number, max_chars=max_chars, overlap_chars=overlap_chars)
        for chunk in page_chunks:
            chunk.chunk_index = global_index
            global_index += 1
            all_chunks.append(chunk)

    return all_chunks


def _split_on_separator(
    text: str,
    sep: str,
    max_chars: int,
    overlap_chars: int,
    regex: bool = False,
) -> list[str] | None:
    """Split text on separator, respecting max_chars. Returns None if can't split meaningfully."""
    if regex:
        parts = re.split(sep, text)
    else:
        parts = text.split(sep)

    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= 1:
        return None

    # Merge small parts together up to max_chars
    return _merge_chunks(parts, max_chars)


def _merge_chunks(chunks: list[str], max_chars: int) -> list[str]:
    """Merge small consecutive chunks up to max_chars."""
    result = []
    current = ""

    for chunk in chunks:
        if not current:
            current = chunk
        elif len(current) + len(chunk) + 2 <= max_chars:
            current += "\n\n" + chunk
        else:
            result.append(current)
            current = chunk

    if current:
        result.append(current)

    return result


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Hard split on max_chars boundary with overlap."""
    result = []
    start = 0

    while start < len(text):
        end = start + max_chars
        chunk = text[start:end].strip()
        if chunk:
            result.append(chunk)
        start = end - overlap_chars
        if start <= 0 and end >= len(text):
            break

    return result if result else [text.strip()]
