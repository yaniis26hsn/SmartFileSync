"""Tests for path safety helpers (symlink handling and directory nesting)."""

import os

from pathlib import Path

import pytest

from smart_file_sync.pathutil import paths_are_nested, walk_files


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class TestWalkFiles:
    def test_walks_nested_files(self, tmp_path: Path) -> None:
        a = _write(tmp_path / "A" / "f.txt", b"1")
        b = _write(tmp_path / "A" / "sub" / "g.bin", b"2")
        c = _write(tmp_path / "A" / "sub" / "deep" / "h.txt", b"3")
        got = walk_files(tmp_path / "A")
        # Sorted by full path: A/f.txt, A/sub/deep/h.txt, A/sub/g.bin
        assert got == [a, c, b]

    def test_skips_directories(self, tmp_path: Path) -> None:
        a = _write(tmp_path / "A" / "f.txt", b"1")
        (tmp_path / "A" / "empty").mkdir()
        assert walk_files(tmp_path / "A") == [a]

    def test_unreadable_or_missing_root_returns_empty(self, tmp_path: Path) -> None:
        assert walk_files(tmp_path / "does_not_exist") == []

    def test_symlinked_file_is_skipped(self, tmp_path: Path) -> None:
        target = _write(tmp_path / "target.txt", b"content")
        link = tmp_path / "A" / "link.txt"
        try:
            link.symlink_to(target)
        except OSError as exc:
            pytest.skip(f"symlink not permitted: {exc}")

        real = _write(tmp_path / "A" / "real.txt", b"real")
        got = walk_files(tmp_path / "A")
        assert got == [real]
        assert link not in got

    def test_symlinked_directory_is_not_followed(self, tmp_path: Path) -> None:
        outside = _write(tmp_path / "outside_dir" / "secret.txt", b"s")
        link = tmp_path / "A" / "linkdir"
        try:
            link.symlink_to(tmp_path / "outside_dir", target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink not permitted: {exc}")

        _write(tmp_path / "A" / "own.txt", b"own")
        got = walk_files(tmp_path / "A")
        names = [p.name for p in got]
        assert "own.txt" in names
        assert "secret.txt" not in names


class TestPathsAreNested:
    def test_equal_paths_are_not_strictly_nested(self, tmp_path: Path) -> None:
        """Equality is reported separately (same-directory), not as nesting."""
        d = tmp_path / "A"
        d.mkdir()
        assert paths_are_nested(d, d) is False

    def test_destination_inside_source(self, tmp_path: Path) -> None:
        src = tmp_path / "A"
        dst = src / "backup"
        src.mkdir()
        assert paths_are_nested(src, dst) is True

    def test_source_inside_destination(self, tmp_path: Path) -> None:
        src = tmp_path / "outer" / "inner"
        dst = tmp_path / "outer"
        dst.mkdir()
        assert paths_are_nested(src, dst) is True

    def test_sibling_directories_not_nested(self, tmp_path: Path) -> None:
        a = tmp_path / "A"
        b = tmp_path / "B"
        a.mkdir()
        b.mkdir()
        assert paths_are_nested(a, b) is False

    def test_nested_using_dot_notation(self, tmp_path: Path) -> None:
        src = tmp_path / "A"
        src.mkdir()
        dst = tmp_path / ".\\A\\sub"
        assert paths_are_nested(src, dst) is True

    def test_deep_nested(self, tmp_path: Path) -> None:
        src = tmp_path / "A"
        src.mkdir()
        dst = src / "x" / "y" / "z"
        assert paths_are_nested(src, dst) is True
