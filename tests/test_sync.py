"""Unit tests for the core A -> B synchronization logic."""

from pathlib import Path

import pytest

from smart_file_sync.sync import SyncAction, sync


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestNewFiles:
    def test_copies_file_to_destination(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "document.pdf", "content")
        dest_dir = tmp_path / "B"
        actions = sync(tmp_path / "A", dest_dir)

        assert dest_dir.joinpath("document.pdf").read_text() == "content"
        assert src.exists()
        assert len(actions) == 1
        assert actions[0].relative_path == Path("document.pdf")
        assert "COPY" in actions[0].action
        assert not actions[0].is_delete

    def test_preserves_relative_directory_structure(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "sub" / "nested" / "file.txt", "deep")
        dest_dir = tmp_path / "B"
        sync(tmp_path / "A", dest_dir)

        assert dest_dir.joinpath("sub", "nested", "file.txt").read_text() == "deep"

    def test_dry_run_copies_nothing(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "doc.pdf", "content")
        dest_dir = tmp_path / "B"
        actions = sync(tmp_path / "A", dest_dir, dry_run=True)

        assert not dest_dir.exists()
        assert len(actions) == 1
        assert "COPY" in actions[0].action


class TestIdenticalFiles:
    def test_deletes_source_keeps_destination(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "photo.jpg", "same data")
        dst = _write_text(tmp_path / "B" / "photo.jpg", "same data")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert not src.exists()
        assert dst.read_text() == "same data"
        assert len(actions) == 1
        assert actions[0].is_delete is True
        assert "DELETE" in actions[0].action

    def test_identical_in_nested_directory(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "A" / "sub" / "img.png", b"\x01\x02\x03")
        dst = _write(tmp_path / "B" / "sub" / "img.png", b"\x01\x02\x03")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert not src.exists()
        assert dst.read_bytes() == b"\x01\x02\x03"
        assert actions[0].relative_path == Path("sub") / "img.png"
        assert actions[0].is_delete

    def test_dry_run_deletes_nothing(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same")
        _write_text(tmp_path / "B" / "f.txt", "same")
        actions = sync(tmp_path / "A", tmp_path / "B", dry_run=True)

        assert src.exists()
        assert len(actions) == 1
        assert actions[0].is_delete is True


class TestDifferentFiles:
    def test_different_sizes_keeps_both(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "video.mp4", "short")
        dst = _write_text(tmp_path / "B" / "video.mp4", "a much longer destination")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert src.exists()
        assert dst.read_text() == "a much longer destination"
        assert len(actions) == 1
        assert "DIFFERENT" in actions[0].action
        assert not actions[0].is_delete
        assert "CONFLICT" in actions[0].action

    def test_different_content_same_size_keeps_both(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "AAAA")
        dst = _write_text(tmp_path / "B" / "f.txt", "BBBB")
        sync(tmp_path / "A", tmp_path / "B")

        assert src.exists()
        assert dst.read_text() == "BBBB"
        assert (tmp_path / "A" / "f.txt").read_text() == "AAAA"


class TestNoCrossNameDedup:
    def test_different_filenames_same_content_are_not_deleted(self, tmp_path: Path) -> None:
        """Files with different names must not be treated as duplicates."""
        src = _write_text(tmp_path / "A" / "report.pdf", "same data")
        _write_text(tmp_path / "B" / "notes.pdf", "same data")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert src.exists()
        assert (tmp_path / "A" / "report.pdf").read_text() == "same data"
        assert (tmp_path / "B" / "notes.pdf").read_text() == "same data"
        assert all(not a.is_delete for a in actions)
        assert (tmp_path / "B" / "report.pdf").exists()

    def test_files_only_in_b_are_untouched(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "a.txt", "a")
        _write_text(tmp_path / "B" / "extra_only_in_b.txt", "untouched")
        sync(tmp_path / "A", tmp_path / "B")

        assert (tmp_path / "B" / "extra_only_in_b.txt").exists()


class TestMixedScenario:
    def test_mixed_actions(self, tmp_path: Path) -> None:
        a = tmp_path / "A"
        b = tmp_path / "B"
        _write_text(a / "same.txt", "identical")
        _write_text(b / "same.txt", "identical")
        _write_text(a / "conflict.txt", "source version")
        _write_text(b / "conflict.txt", "destination version")
        _write_text(a / "new.txt", "brand new")

        actions = sync(a, b)

        actions_by_name = {a.relative_path.name: a.action for a in actions}
        assert "DELETE" in actions_by_name["same.txt"]
        assert "DIFFERENT" in actions_by_name["conflict.txt"]
        assert "COPY" in actions_by_name["new.txt"]

        assert not (a / "same.txt").exists()
        assert (a / "conflict.txt").exists()
        assert (b / "conflict.txt").read_text() == "destination version"
        assert (b / "new.txt").read_text() == "brand new"
