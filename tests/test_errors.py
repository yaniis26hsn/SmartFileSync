"""Unit tests for filesystem error-handling robustness."""

from pathlib import Path

import pytest

from smart_file_sync.comparator import CompareResult, compare_files
from smart_file_sync.sync import SyncStatus, sync
from smart_file_sync.dedupe import delete_duplicates, find_duplicates
from smart_file_sync.main import EXIT_ERROR, EXIT_OK, run


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestComparatorStatFailure:
    def test_source_stat_failure_never_identical(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same data")
        dst = _write_text(tmp_path / "B" / "f.txt", "same data")

        real_stat = Path.stat

        def broken_stat_for_source(self, **kwargs):
            if self == src:
                raise PermissionError("denied")
            return real_stat(self, **kwargs)

        monkeypatch.setattr(Path, "stat", broken_stat_for_source)

        result = compare_files(src, dst)
        assert result == CompareResult.ERROR


class TestComparatorHashFailure:
    def test_source_hash_failure_never_identical(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same data")
        dst = _write_text(tmp_path / "B" / "f.txt", "same data")

        import smart_file_sync.comparator as comparator_module

        def failing_hash(path):
            raise PermissionError("cannot read")

        monkeypatch.setattr(comparator_module, "sha256_file", failing_hash)

        assert compare_files(src, dst) == CompareResult.ERROR

    def test_destination_hash_failure_never_identical(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same data")
        dst = _write_text(tmp_path / "B" / "f.txt", "same data")

        import smart_file_sync.comparator as comparator_module

        calls = 0

        def failing_dest_hash(path):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise PermissionError("cannot read")
            return "hash"

        monkeypatch.setattr(comparator_module, "sha256_file", failing_dest_hash)

        assert compare_files(src, dst) == CompareResult.ERROR


class TestSyncNoFalseDelete:
    def test_source_hash_failure_does_not_delete(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same")
        _write_text(tmp_path / "B" / "f.txt", "same")

        import smart_file_sync.comparator as comparator_module

        def failing_hash(path):
            raise PermissionError("cannot read")

        monkeypatch.setattr(comparator_module, "sha256_file", failing_hash)

        actions = sync(tmp_path / "A", tmp_path / "B")

        assert src.exists()
        assert len(actions) == 1
        assert actions[0].status == SyncStatus.ERROR

    def test_stat_failure_does_not_delete(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same")
        _write_text(tmp_path / "B" / "f.txt", "same")

        real_stat = Path.stat

        def broken_stat_for_source(self, **kwargs):
            if self == src:
                raise PermissionError("denied")
            return real_stat(self, **kwargs)

        monkeypatch.setattr(Path, "stat", broken_stat_for_source)

        actions = sync(tmp_path / "A", tmp_path / "B")

        assert real_stat(src)
        assert actions[0].status == SyncStatus.ERROR

    def test_copy_failure_does_not_delete_source(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "content")
        dest_dir = tmp_path / "B"

        import smart_file_sync.sync as sync_module

        def failing_copy(source, destination):
            raise PermissionError("cannot copy")

        monkeypatch.setattr(sync_module, "copy_file", failing_copy)

        actions = sync(tmp_path / "A", dest_dir)

        assert src.exists()
        assert not (dest_dir / "f.txt").exists()
        assert actions[0].status == SyncStatus.ERROR

    def test_delete_failure_reported_and_source_kept(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "same")
        _write_text(tmp_path / "B" / "f.txt", "same")

        import smart_file_sync.sync as sync_module

        def failing_delete(path):
            raise PermissionError("cannot delete")

        monkeypatch.setattr(sync_module, "delete_file", failing_delete)

        actions = sync(tmp_path / "A", tmp_path / "B")

        assert src.exists()
        assert (tmp_path / "B" / "f.txt").exists()
        assert actions[0].status == SyncStatus.ERROR


class TestSyncErrorIsolation:
    def test_one_bad_file_does_not_stop_others(self, tmp_path: Path, monkeypatch) -> None:
        a = tmp_path / "A"
        b = tmp_path / "B"
        good = _write_text(a / "good.txt", "fresh content")
        bad = _write_text(a / "bad.txt", "more content")

        import smart_file_sync.sync as sync_module

        original_copy = sync_module.copy_file

        def failing_copy_for_bad(source, destination):
            if source == bad:
                raise PermissionError("cannot copy")
            return original_copy(source, destination)

        monkeypatch.setattr(sync_module, "copy_file", failing_copy_for_bad)

        actions = sync(a, b)

        by_name = {act.relative_path.name: act.status for act in actions}
        assert by_name["good.txt"] == SyncStatus.COPY
        assert by_name["bad.txt"] == SyncStatus.ERROR
        assert (b / "good.txt").exists()
        assert bad.exists()


class TestDestinationDisappeared:
    def test_destination_missing_becomes_new_and_is_copied(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "f.txt", "content")
        dest_dir = tmp_path / "B"
        actions = sync(tmp_path / "A", dest_dir)
        assert actions[0].status == SyncStatus.COPY
        assert (dest_dir / "f.txt").read_text() == "content"
        assert src.exists()


class TestDedupeErrors:
    def test_hash_failure_no_match_no_delete(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")

        import smart_file_sync.dedupe as dedupe_module

        def failing_hash(path):
            raise PermissionError("cannot read")

        monkeypatch.setattr(dedupe_module, "sha256_file", failing_hash)

        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []
        outcomes = delete_duplicates(
            tmp_path / "A", tmp_path / "B", confirm=lambda m: True
        )
        assert outcomes == []
        assert src.exists()

    def test_stat_failure_no_match_no_delete(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")

        real_stat = Path.stat

        def broken_stat(self, **kwargs):
            raise OSError("cannot stat")

        monkeypatch.setattr(Path, "stat", broken_stat)

        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []
        assert real_stat(src)


class TestCliErrorExit:
    def test_sync_oserror_returns_error_and_clear_message(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        a = tmp_path / "A"
        a.mkdir()

        import smart_file_sync.main as main_module

        def raising_sync(source, destination, dry_run=False):
            raise PermissionError("access denied on sync")

        monkeypatch.setattr(main_module, "sync", raising_sync)

        code = main_module.run([str(a), str(tmp_path / "B")])
        captured = capsys.readouterr()
        assert code == EXIT_ERROR
        assert "Error during synchronization" in captured.err

    def test_unexpected_exception_no_traceback(self, tmp_path: Path, monkeypatch) -> None:
        a = tmp_path / "A"
        a.mkdir()

        import smart_file_sync.main as main_module

        def raising_sync(source, destination, dry_run=False):
            raise RuntimeError("boom")

        monkeypatch.setattr(main_module, "sync", raising_sync)

        exit_codes: list[int] = []
        monkeypatch.setattr(
            main_module.sys, "exit", lambda code: exit_codes.append(code)
        )

        main_module.main([str(a), str(tmp_path / "B")])

        assert exit_codes and exit_codes[0] == EXIT_ERROR

    def test_success_exits_ok(self, tmp_path: Path) -> None:
        a = tmp_path / "A"
        a.mkdir()
        _write_text(a / "f.txt", "x")
        code = run([str(a), str(tmp_path / "B")])
        assert code == EXIT_OK
