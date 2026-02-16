"""Tests for two-phase file hashing."""

from __future__ import annotations

from pathlib import Path

from librarian.processing.hasher import FileHash, canonical_hash, hash_file, quick_fingerprint


def test_quick_fingerprint(tmp_path):
    """Quick fingerprint should include size and xxhash."""
    f = tmp_path / "test.txt"
    f.write_text("hello world")

    fp = quick_fingerprint(f)
    assert ":" in fp
    size_part, hash_part = fp.split(":", 1)
    assert int(size_part) == f.stat().st_size
    assert len(hash_part) == 16  # xxhash64 hex


def test_quick_fingerprint_different_content(tmp_path):
    """Different files should produce different fingerprints."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("file one")
    f2.write_text("file two")

    assert quick_fingerprint(f1) != quick_fingerprint(f2)


def test_quick_fingerprint_same_content(tmp_path):
    """Same content files should produce same fingerprint."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("identical")
    f2.write_text("identical")

    assert quick_fingerprint(f1) == quick_fingerprint(f2)


def test_canonical_hash(tmp_path):
    """Canonical hash should be SHA-256."""
    f = tmp_path / "test.txt"
    f.write_text("hello")

    h = canonical_hash(f)
    assert len(h) == 64  # SHA-256 hex


def test_canonical_hash_deterministic(tmp_path):
    """Same content should produce same hash."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    content = "deterministic content"
    f1.write_text(content)
    f2.write_text(content)

    assert canonical_hash(f1) == canonical_hash(f2)


def test_hash_file(tmp_path):
    """hash_file should return FileHash with all fields."""
    f = tmp_path / "test.pdf"
    f.write_bytes(b"fake pdf content" * 100)

    result = hash_file(f)
    assert isinstance(result, FileHash)
    assert len(result.content_hash) == 64
    assert ":" in result.quick_hash
    assert result.file_size == f.stat().st_size
