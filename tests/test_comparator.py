"""Unit tests for the file comparison logic."""

from pathlib import Path

import pytest

from smart_file_sync.comparator import CompareResult, compare_files


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestIdenticalFiles:
    def test_identical_files(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "photo.jpg", "same content")
        dst = _write_text(tmp_path / "b" / "photo.jpg", "same content")
        assert compare_files(src, dst) == CompareResult.IDENTICAL

    def test_identical_empty_files(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "a" / "empty.bin", b"")
        dst = _write(tmp_path / "b" / "empty.bin", b"")
        assert compare_files(src, dst) == CompareResult.IDENTICAL

    def test_identical_binary_files(self, tmp_path: Path) -> None:
        data = bytes(range(256))
        src = _write(tmp_path / "a" / "data.bin", data)
        dst = _write(tmp_path / "b" / "data.bin", data)
        assert compare_files(src, dst) == CompareResult.IDENTICAL

    def test_identical_different_filenames(self, tmp_path: Path) -> None:
        """Filenames must not affect content equality."""
        data = bytes(range(128))
        src = _write(tmp_path / "a" / "whatever.jpg", data)
        dst = _write(tmp_path / "b" / "completely_different_name.png", data)
        assert compare_files(src, dst) == CompareResult.IDENTICAL


class TestDifferentFilesSameSize:
    def test_different_content_same_size(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "f.txt", "AAAA")
        dst = _write_text(tmp_path / "b" / "f.txt", "BBBB")
        assert compare_files(src, dst) == CompareResult.DIFFERENT

    def test_different_content_same_size_binary(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "a" / "f.bin", b"\x00" * 1024)
        dst = _write(tmp_path / "b" / "f.bin", b"\xff" * 1024)
        assert compare_files(src, dst) == CompareResult.DIFFERENT


class TestDifferentFilesDifferentSizes:
    def test_different_sizes(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "f.txt", "short")
        dst = _write_text(tmp_path / "b" / "f.txt", "a much longer destination file")
        assert compare_files(src, dst) == CompareResult.DIFFERENT

    def test_source_larger_than_destination(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "f.txt", "long source")
        dst = _write_text(tmp_path / "b" / "f.txt", "dst")
        assert compare_files(src, dst) == CompareResult.DIFFERENT

    def test_destination_larger_than_source(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "f.txt", "src")
        dst = _write_text(tmp_path / "b" / "f.txt", "a much longer destination")
        assert compare_files(src, dst) == CompareResult.DIFFERENT


class TestEmptyFiles:
    def test_empty_source_with_content_destination(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "a" / "f.txt", b"")
        dst = _write_text(tmp_path / "b" / "f.txt", "content")
        assert compare_files(src, dst) == CompareResult.DIFFERENT

    def test_content_source_with_empty_destination(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "f.txt", "content")
        dst = _write(tmp_path / "b" / "f.txt", b"")
        assert compare_files(src, dst) == CompareResult.DIFFERENT

    def test_both_empty_identical(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "a" / "f.txt", b"")
        dst = _write(tmp_path / "b" / "f.txt", b"")
        assert compare_files(src, dst) == CompareResult.IDENTICAL


class TestLargeFiles:
    def test_identical_large_files(self, tmp_path: Path) -> None:
        data = b"z" * (8 * 1024 * 1024)  # 8 MiB
        src = _write(tmp_path / "a" / "big.bin", data)
        dst = _write(tmp_path / "b" / "big.bin", data)
        assert compare_files(src, dst) == CompareResult.IDENTICAL

    def test_large_files_different_tail(self, tmp_path: Path) -> None:
        """Same size but differ only in the last byte."""
        size = 4 * 1024 * 1024
        data_a = bytearray(b"a" * size)
        data_b = bytearray(b"a" * size)
        data_b[-1] = ord("b")
        src = _write(tmp_path / "a" / "big.bin", bytes(data_a))
        dst = _write(tmp_path / "b" / "big.bin", bytes(data_b))
        assert compare_files(src, dst) == CompareResult.DIFFERENT


class TestMissingDestination:
    def test_destination_does_not_exist_returns_new(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "a" / "f.txt", "content")
        dst = tmp_path / "b" / "f.txt"
        assert compare_files(src, dst) == CompareResult.NEW
