"""Two-phase file hashing for fast deduplication."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import xxhash


@dataclass
class FileHash:
    """File hash result."""

    content_hash: str  # SHA-256 (canonical)
    quick_hash: str  # xxhash of first 4KB + size
    file_size: int


def quick_fingerprint(path: Path) -> str:
    """
    Fast pre-filter: file size + xxhash of first 4KB.
    ~2 seconds for 50K files on SSD.
    """
    stat = path.stat()
    with open(path, "rb") as f:
        head = f.read(4096)
    return f"{stat.st_size}:{xxhash.xxh64(head).hexdigest()}"


def canonical_hash(path: Path, buf_size: int = 1 << 20) -> str:
    """
    Full SHA-256 hash.
    Only computed for files that pass quick_fingerprint as new.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(buf_size):
            h.update(chunk)
    return h.hexdigest()


def hash_file(path: Path) -> FileHash:
    """Hash a file with two-phase approach."""
    file_size = path.stat().st_size
    quick = quick_fingerprint(path)
    content = canonical_hash(path)
    return FileHash(
        content_hash=content,
        quick_hash=quick,
        file_size=file_size,
    )
