"""Unit tests for the core A -> B synchronization logic and dry-run safety."""

from pathlib import Path

import pytest

from smart_file_sync.sync import SyncAction, SyncStatus, sync


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _snapshot(root: Path) -> dict[Path, bytes]:
    """Return a map of relative path -> contents for all files under root."""
    snap: dict[Path, bytes] = {}
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        if p.is_file():
            snap[p.relative_to(root)] = p.read_bytes()
    return snap


class TestNewFiles:
    def test_copies_file_to_destination(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "document.pdf", "content")
        dest_dir = tmp_path / "B"
        actions = sync(tmp_path / "A", dest_dir)

        assert dest_dir.joinpath("document.pdf").read_text() == "content"
        assert src.exists()
        assert len(actions) == 1
        assert actions[0].relative_path == Path("document.pdf")
        assert actions[0].status == SyncStatus.COPY
        assert not actions[0].is_delete

    def test_preserves_relative_directory_structure(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "sub" / "nested" / "file.txt", "deep")
        dest_dir = tmp_path / "B"
        sync(tmp_path / "A", dest_dir)

        assert dest_dir.joinpath("sub", "nested", "file.txt").read_text() == "deep"


class TestIdenticalFiles:
    def test_deletes_source_keeps_destination(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "photo.jpg", "same data")
        dst = _write_text(tmp_path / "B" / "photo.jpg", "same data")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert not src.exists()
        assert dst.read_text() == "same data"
        assert len(actions) == 1
        assert actions[0].status == SyncStatus.IDENTICAL
        assert actions[0].is_delete is True

    def test_identical_in_nested_directory(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "A" / "sub" / "img.png", b"\x01\x02\x03")
        dst = _write(tmp_path / "B" / "sub" / "img.png", b"\x01\x02\x03")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert not src.exists()
        assert dst.read_bytes() == b"\x01\x02\x03"
        assert actions[0].relative_path == Path("sub") / "img.png"
        assert actions[0].is_delete

    def test_dry_run_marks_delete_but_does_not_delete(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same")
        _write_text(tmp_path / "B" / "f.txt", "same")
        actions = sync(tmp_path / "A", tmp_path / "B", dry_run=True)

        assert src.exists()
        assert len(actions) == 1
        assert actions[0].status == SyncStatus.IDENTICAL
        assert actions[0].is_delete is True


class TestDifferentFiles:
    def test_different_sizes_keeps_both(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "video.mp4", "short")
        dst = _write_text(tmp_path / "B" / "video.mp4", "a much longer destination")
        actions = sync(tmp_path / "A", tmp_path / "B")

        assert src.exists()
        assert dst.read_text() == "a much longer destination"
        assert len(actions) == 1
        assert actions[0].status == SyncStatus.CONFLICT
        assert not actions[0].is_delete

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


class TestDryRunSafety:
    def test_dry_run_leaves_both_directories_unchanged(self, tmp_path: Path) -> None:
        a = tmp_path / "A"
        b = tmp_path / "B"
        _write_text(a / "new.txt", "new content")
        _write_text(a / "same.txt", "identical")
        _write(a / "binary.dat", b"\x00\x01\x02")
        _write_text(a / "sub" / "nested" / "deep.txt", "deep file")
        _write_text(a / "conflict.txt", "source version")
        _write_text(b / "same.txt", "identical")
        _write_text(b / "conflict.txt", "dest version")

        before_a = _snapshot(a)
        before_b = _snapshot(b)

        actions = sync(a, b, dry_run=True)

        assert _snapshot(a) == before_a
        assert _snapshot(b) == before_b

        statuses = {act.status for act in actions}
        assert SyncStatus.COPY in statuses
        assert SyncStatus.IDENTICAL in statuses
        assert SyncStatus.CONFLICT in statuses

    def test_dry_run_does_not_create_destination_directory(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "file.txt", "content")
        dest_dir = tmp_path / "B"
        sync(tmp_path / "A", dest_dir, dry_run=True)

        assert not dest_dir.exists()

    def test_dry_run_does_not_copy_nested_structure(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "sub" / "file.txt", "content")
        dest_dir = tmp_path / "B"
        sync(tmp_path / "A", dest_dir, dry_run=True)

        assert not dest_dir.exists()

    def test_dry_run_reports_copy_for_new_file(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "doc.pdf", "content")
        dest_dir = tmp_path / "B"
        actions = sync(tmp_path / "A", dest_dir, dry_run=True)

        assert len(actions) == 1
        assert actions[0].status == SyncStatus.COPY
        assert not actions[0].is_delete


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

        actions_by_name = {act.relative_path.name: act.status for act in actions}
        assert actions_by_name["same.txt"] == SyncStatus.IDENTICAL
        assert actions_by_name["conflict.txt"] == SyncStatus.CONFLICT
        assert actions_by_name["new.txt"] == SyncStatus.COPY

        assert not (a / "same.txt").exists()
        assert (a / "conflict.txt").exists()
        assert (b / "conflict.txt").read_text() == "destination version"
        assert (b / "new.txt").read_text() == "brand new"


class TestSourceValidation:
    def test_missing_source_raises_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            sync(missing, tmp_path / "B")

    def test_source_file_not_directory_raises(self, tmp_path: Path) -> None:
        file_source = _write_text(tmp_path / "A", "i am a file")
        with pytest.raises(NotADirectoryError):
            sync(file_source, tmp_path / "B")


class TestNestedDirectories:
    def test_destination_inside_source_raises(self, tmp_path: Path) -> None:
        a = tmp_path / "A"
        a.mkdir()
        _write_text(a / "f.txt", "x")
        nested_dest = a / "backup"
        with pytest.raises(ValueError, match="nested"):
            sync(a, nested_dest)

    def test_source_inside_destination_raises(self, tmp_path: Path) -> None:
        outer = tmp_path / "outer"
        inner = outer / "inner"
        _write_text(outer / "root.txt", "x")
        _write_text(inner / "f.txt", "y")
        with pytest.raises(ValueError, match="nested"):
            sync(inner, outer)

    def test_sibling_directories_work(self, tmp_path: Path) -> None:
        a = tmp_path / "A"
        b = tmp_path / "B"
        _write_text(a / "f.txt", "x")
        actions = sync(a, b)
        assert actions[0].status == SyncStatus.COPY
