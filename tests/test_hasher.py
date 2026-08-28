"""Unit tests for the SHA-256 file hashing functions."""

from pathlib import Path

import hashlib

import pytest

from smart_file_sync.hasher import sha256_file


def _write_bytes(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _expected_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_sha256_of_simple_file(tmp_path: Path) -> None:
    data = b"hello world"
    path = _write_bytes(tmp_path / "file.txt", data)
    assert sha256_file(path) == _expected_hash(data)


def test_sha256_of_empty_file(tmp_path: Path) -> None:
    path = _write_bytes(tmp_path / "empty.txt", b"")
    assert sha256_file(path) == hashlib.sha256(b"").hexdigest()


def test_sha256_of_large_file(tmp_path: Path) -> None:
    data = b"x" * (512 * 1024)  # 512 KiB
    path = _write_bytes(tmp_path / "large.bin", data)
    assert sha256_file(path) == _expected_hash(data)


def test_sha256_uses_read_chunks() -> None:
    """Verify the hasher reads binary data (not text) and handles binary content."""
    data = bytes(range(256))
    path = Path("hasher_chunk_test.bin")
    try:
        path.write_bytes(data)
        digest = sha256_file(path)
        assert digest == hashlib.sha256(data).hexdigest()
    finally:
        path.unlink()


def test_sha256_deterministic(tmp_path: Path) -> None:
    data = b"deterministic content"
    path = _write_bytes(tmp_path / "a.txt", data)
    assert sha256_file(path) == sha256_file(path)


def test_sha256_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.bin"
    with pytest.raises(FileNotFoundError):
        sha256_file(missing)
