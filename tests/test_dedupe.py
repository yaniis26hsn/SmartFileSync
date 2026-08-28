"""Unit tests for the opt-in duplicate-content detection feature."""

from pathlib import Path

import pytest

from smart_file_sync.dedupe import (
    DedupeOutcome,
    DuplicateMatch,
    delete_duplicates,
    find_duplicates,
)


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestFindDuplicates:
    def test_same_content_different_filename(self, tmp_path: Path) -> None:
        a = _write_text(tmp_path / "A" / "photo1.jpg", "same bytes")
        b = _write_text(tmp_path / "B" / "photo2.jpg", "same bytes")
        matches = find_duplicates(tmp_path / "A", tmp_path / "B")
        assert len(matches) == 1
        assert matches[0].source == a
        assert matches[0].destination == b

    def test_same_content_different_relative_path(self, tmp_path: Path) -> None:
        a = _write_text(tmp_path / "A" / "photos" / "photo1.jpg", "same bytes")
        b = _write_text(tmp_path / "B" / "backup" / "vacation.jpg", "same bytes")
        matches = find_duplicates(tmp_path / "A", tmp_path / "B")
        assert len(matches) == 1
        assert matches[0].source == a
        assert matches[0].destination == b

    def test_same_size_but_different_content_is_not_duplicate(
        self, tmp_path: Path
    ) -> None:
        _write(tmp_path / "A" / "a.bin", b"\x00" * 1024)
        _write(tmp_path / "B" / "b.bin", b"\xff" * 1024)
        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []

    def test_different_size_is_not_duplicate(self, tmp_path: Path) -> None:
        _write(tmp_path / "A" / "a.txt", b"short")
        _write(tmp_path / "B" / "b.txt", b"a longer destination")
        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []

    def test_no_duplicates_cross_directories_but_same_size(self, tmp_path: Path) -> None:
        _write(tmp_path / "A" / "one.txt", b"AAAA")
        _write(tmp_path / "B" / "two.txt", b"BBBB")
        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []

    def test_multiple_duplicate_files(self, tmp_path: Path) -> None:
        d1 = _write_text(tmp_path / "A" / "dup1.jpg", "duplicate content")
        d2 = _write_text(tmp_path / "A" / "dup2.jpg", "duplicate content")
        _write_text(tmp_path / "B" / "orig.jpg", "duplicate content")
        matches = find_duplicates(tmp_path / "A", tmp_path / "B")
        sources = {m.source for m in matches}
        assert sources == {d1, d2}

    def test_distinct_hashes_split_properly(self, tmp_path: Path) -> None:
        a1 = _write_text(tmp_path / "A" / "f1.txt", "content one")
        a2 = _write_text(tmp_path / "A" / "f2.txt", "content two")
        _write_text(tmp_path / "B" / "one.txt", "content one")
        _write_text(tmp_path / "B" / "two.txt", "content two")
        sources = {m.source for m in find_duplicates(tmp_path / "A", tmp_path / "B")}
        assert sources == {a1, a2}

    def test_empty_destination_produces_no_matches(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "f.txt", "content")
        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []

    def test_only_source_files_within_a_no_match(self, tmp_path: Path) -> None:
        """Two identical files both in A (no matching destination) are not reported."""
        _write_text(tmp_path / "A" / "x.txt", "same")
        _write_text(tmp_path / "A" / "y.txt", "same")
        assert find_duplicates(tmp_path / "A", tmp_path / "B") == []


class TestDeleteDuplicatesDryRun:
    def test_dry_run_never_deletes(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")
        outcomes = delete_duplicates(tmp_path / "A", tmp_path / "B", dry_run=True)
        assert src.exists()
        assert len(outcomes) == 1
        assert outcomes[0].would_delete is True
        assert outcomes[0].deleted is False

    def test_dry_run_does_not_ask_confirmation(self, tmp_path: Path, monkeypatch) -> None:
        _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")

        def unexpected(match):
            raise AssertionError("confirm should not be called in dry-run")

        delete_duplicates(
            tmp_path / "A", tmp_path / "B", dry_run=True, confirm=unexpected
        )

    def test_dry_run_reports_would_delete(self, tmp_path: Path) -> None:
        _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")
        outcomes = delete_duplicates(tmp_path / "A", tmp_path / "B", dry_run=True)
        outcome = outcomes[0]
        assert outcome.would_delete is True
        assert outcome.error is None


class TestDeleteDuplicatesConfirmation:
    def test_user_confirms_deletion(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        dst = _write_text(tmp_path / "B" / "orig.jpg", "same")

        outcomes = delete_duplicates(
            tmp_path / "A",
            tmp_path / "B",
            confirm=lambda match: True,
        )

        assert not src.exists()
        assert dst.exists()
        assert len(outcomes) == 1
        assert outcomes[0].deleted is True
        assert outcomes[0].would_delete is False

    def test_user_rejects_keeps_source(self, tmp_path: Path) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        dst = _write_text(tmp_path / "B" / "orig.jpg", "same")

        outcomes = delete_duplicates(
            tmp_path / "A",
            tmp_path / "B",
            confirm=lambda match: False,
        )

        assert src.exists()
        assert dst.exists()
        assert len(outcomes) == 1
        assert outcomes[0].deleted is False
        assert outcomes[0].error is None

    def test_destination_never_deleted_even_when_confirmed(
        self, tmp_path: Path
    ) -> None:
        _write_text(tmp_path / "A" / "dup.jpg", "same")
        dst = _write_text(tmp_path / "B" / "orig.jpg", "same")
        delete_duplicates(
            tmp_path / "A", tmp_path / "B", confirm=lambda match: True
        )
        assert dst.exists()


class TestDeleteDuplicatesFailures:
    def test_deletion_failure_is_reported_not_raised(self, tmp_path: Path, monkeypatch) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")

        import smart_file_sync.dedupe as dedupe_module

        def failing_delete(path):
            raise PermissionError("denied")

        monkeypatch.setattr(dedupe_module, "delete_file", failing_delete)
        outcomes = delete_duplicates(
            tmp_path / "A", tmp_path / "B", confirm=lambda m: True
        )

        assert src.exists()
        assert len(outcomes) == 1
        assert outcomes[0].deleted is False
        assert outcomes[0].error is not None


class TestHashFailure:
    def test_hash_failure_does_not_report_nor_delete(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        src = _write_text(tmp_path / "A" / "dup.jpg", "same")
        _write_text(tmp_path / "B" / "orig.jpg", "same")

        import smart_file_sync.dedupe as dedupe_module

        def failing_hash(path):
            raise PermissionError("cannot read")

        monkeypatch.setattr(dedupe_module, "sha256_file", failing_hash)

        matches = find_duplicates(tmp_path / "A", tmp_path / "B")
        assert matches == []

        outcomes = delete_duplicates(
            tmp_path / "A", tmp_path / "B", confirm=lambda m: True
        )
        assert outcomes == []
        assert src.exists()
