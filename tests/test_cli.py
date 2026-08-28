"""Unit tests for the command-line interface of Smart File Sync."""

from pathlib import Path

import pytest

from smart_file_sync.main import (
    EXIT_ERROR,
    EXIT_OK,
    _format_action,
    _validate,
    parse_args,
    run,
)
from smart_file_sync.sync import SyncAction, SyncStatus


def _make_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_text(path: Path, text: str) -> Path:
    _make_dir(path.parent)
    path.write_text(text, encoding="utf-8")
    return path


class TestParseArgs:
    def test_parses_source_and_destination(self) -> None:
        ns = parse_args(["A", "B"])
        assert ns.source == Path("A")
        assert ns.destination == Path("B")
        assert ns.dry_run is False
        assert ns.verbose is False

    def test_parses_dry_run_flag(self) -> None:
        ns = parse_args(["A", "B", "--dry-run"])
        assert ns.dry_run is True

    def test_parses_verbose_flag(self) -> None:
        ns = parse_args(["A", "B", "--verbose"])
        assert ns.verbose is True

    def test_parses_all_flags_together(self) -> None:
        ns = parse_args(["A", "B", "--dry-run", "--verbose"])
        assert ns.dry_run is True
        assert ns.verbose is True

    def test_parses_delete_duplicates_flag(self) -> None:
        ns = parse_args(["A", "B", "--delete-duplicates"])
        assert ns.delete_duplicates is True

    def test_delete_duplicates_default_off(self) -> None:
        ns = parse_args(["A", "B"])
        assert ns.delete_duplicates is False


class TestValidation:
    def test_missing_source(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        assert _validate(missing, tmp_path / "B") is not None

    def test_source_is_file(self, tmp_path: Path) -> None:
        f = _write_text(tmp_path / "file.txt", "x")
        assert _validate(f, tmp_path / "B") is not None

    def test_same_directory(self, tmp_path: Path) -> None:
        d = _make_dir(tmp_path / "A")
        assert _validate(d, d) is not None

    def test_same_directory_different_spelling(self, tmp_path: Path) -> None:
        d = _make_dir(tmp_path / "A")
        assert _validate(d, tmp_path / ".\\A") is not None

    def test_valid_source_and_destination(self, tmp_path: Path) -> None:
        d = _make_dir(tmp_path / "A")
        assert _validate(d, tmp_path / "B") is None

    def test_destination_nested_inside_source(self, tmp_path: Path) -> None:
        d = _make_dir(tmp_path / "A")
        assert _validate(d, d / "backup") is not None

    def test_source_nested_inside_destination(self, tmp_path: Path) -> None:
        outer = _make_dir(tmp_path / "outer")
        assert _validate(outer / "inner", outer) is not None


class TestFormatAction:
    def _action(
        self, status: str, name: str = "f.txt", reason: str = ""
    ) -> SyncAction:
        return SyncAction(
            relative_path=Path(name),
            status=status,
            source=Path("A") / name,
            destination=Path("B") / name,
            reason=reason,
        )

    def test_copy_format(self) -> None:
        line = _format_action(self._action(SyncStatus.COPY))
        assert "COPY" in line
        assert line.replace("\\", "/").endswith("A/f.txt -> B/f.txt")

    def test_identical_format(self) -> None:
        line = _format_action(
            self._action(SyncStatus.IDENTICAL, name="photo.jpg", reason="same hash")
        )
        assert "IDENTICAL" in line
        assert "photo.jpg" in line
        assert "would delete source" in line

    def test_identical_verbose_shows_reason(self) -> None:
        line = _format_action(
            self._action(SyncStatus.IDENTICAL, name="photo.jpg", reason="same hash"),
            verbose=True,
        )
        assert "IDENTICAL" in line
        assert "same hash" in line

    def test_identical_falls_back_to_default_when_no_reason(self) -> None:
        line = _format_action(self._action(SyncStatus.IDENTICAL, name="photo.jpg"))
        assert "would delete source" in line

    def test_conflict_format(self) -> None:
        line = _format_action(self._action(SyncStatus.CONFLICT, name="video.mp4"))
        assert "CONFLICT" in line
        assert "video.mp4" in line
        assert "files differ" in line

    def test_verbose_adds_reason(self) -> None:
        action = self._action(SyncStatus.CONFLICT, reason="different size")
        line = _format_action(action, verbose=True)
        assert "different size" in line


class TestRunExitCodes:
    def test_missing_source_exits_error(self, tmp_path: Path, capsys) -> None:
        code = run([str(tmp_path / "missing"), str(tmp_path / "B")])
        assert code == EXIT_ERROR
        assert "does not exist" in capsys.readouterr().err

    def test_source_is_file_exits_error(self, tmp_path: Path, capsys) -> None:
        f = _write_text(tmp_path / "file.txt", "x")
        code = run([str(f), str(tmp_path / "B")])
        assert code == EXIT_ERROR
        assert "not a directory" in capsys.readouterr().err

    def test_same_directory_exits_error(self, tmp_path: Path, capsys) -> None:
        d = _make_dir(tmp_path / "A")
        code = run([str(d), str(d)])
        assert code == EXIT_ERROR
        assert "same directory" in capsys.readouterr().err

    def test_nested_directory_exits_error(self, tmp_path: Path, capsys) -> None:
        a = _make_dir(tmp_path / "A")
        code = run([str(a), str(a / "backup")])
        captured = capsys.readouterr()
        assert code == EXIT_ERROR
        assert "nested" in captured.err

    def test_successful_sync_exits_ok(self, tmp_path: Path, capsys) -> None:
        a = _make_dir(tmp_path / "A")
        _write_text(a / "file.txt", "hello")
        code = run([str(a), str(tmp_path / "B")])
        assert code == EXIT_OK
        assert (tmp_path / "B" / "file.txt").read_text() == "hello"


class TestDestinationCreation:
    def test_destination_created_automatically(self, tmp_path: Path) -> None:
        a = _make_dir(tmp_path / "A")
        _write_text(a / "nested" / "file.txt", "x")
        code = run([str(a), str(tmp_path / "B")])
        assert code == EXIT_OK
        assert (tmp_path / "B" / "nested" / "file.txt").exists()

    def test_destination_not_created_in_dry_run(self, tmp_path: Path, capsys) -> None:
        a = _make_dir(tmp_path / "A")
        _write_text(a / "file.txt", "x")
        code = run([str(a), str(tmp_path / "B"), "--dry-run"])
        assert code == EXIT_OK
        assert not (tmp_path / "B").exists()


class TestVerbose:
    def test_verbose_reports_reason(self, tmp_path: Path, capsys) -> None:
        a = _make_dir(tmp_path / "A")
        _write_text(a / "new.txt", "content")
        code = run([str(a), str(tmp_path / "B"), "--verbose"])
        captured = capsys.readouterr().out
        assert code == EXIT_OK
        assert "COPY" in captured
        assert "no file with this relative path exists" in captured

    def test_verbose_conflict_shows_size_reason(self, tmp_path: Path, capsys) -> None:
        a = _make_dir(tmp_path / "A")
        _write_text(a / "f.txt", "short")
        b = _make_dir(tmp_path / "B")
        _write_text(b / "f.txt", "a much longer destination")
        run([str(a), str(b), "--verbose"])
        captured = capsys.readouterr().out
        assert "different size" in captured

    def test_default_output_has_no_reason(self, tmp_path: Path, capsys) -> None:
        a = _make_dir(tmp_path / "A")
        _write_text(a / "f.txt", "short")
        b = _make_dir(tmp_path / "B")
        _write_text(b / "f.txt", "a much longer destination")
        run([str(a), str(b)])
        captured = capsys.readouterr().out
        assert "different size" not in captured


class TestDedupeCLI:
    def test_dedupe_dry_run_reports_without_deleting(
        self, tmp_path: Path, capsys
    ) -> None:
        a = _make_dir(tmp_path / "A")
        src = _write_text(a / "photos" / "photo1.jpg", "same bytes")
        b = _make_dir(tmp_path / "B")
        _write_text(b / "backup" / "vacation.jpg", "same bytes")

        code = run([str(a), str(b), "--dry-run", "--delete-duplicates"])

        captured = capsys.readouterr().out
        assert code == EXIT_OK
        assert "DUPLICATE CONTENT" in captured
        assert "would delete source" in captured
        assert src.exists()

    def test_normal_sync_does_not_delete_different_name_duplicate(
        self, tmp_path: Path
    ) -> None:
        """Without --delete-duplicates, same-content/different-name files are kept."""
        a = _make_dir(tmp_path / "A")
        src = _write_text(a / "photo1.jpg", "same bytes")
        b = _make_dir(tmp_path / "B")
        _write_text(b / "photo2.jpg", "same bytes")

        code = run([str(a), str(b)])

        assert code == EXIT_OK
        assert src.exists()
        assert (b / "photo1.jpg").exists()
        assert (b / "photo2.jpg").exists()

    def test_delete_duplicates_mode_skips_normal_sync_copy(
        self, tmp_path: Path, capsys
    ) -> None:
        """--delete-duplicates is a separate pass; it does not run normal copy."""
        a = _make_dir(tmp_path / "A")
        _write_text(a / "brand.txt", "unique")
        b = _make_dir(tmp_path / "B")

        code = run([str(a), str(b), "--dry-run", "--delete-duplicates"])

        captured = capsys.readouterr().out
        assert code == EXIT_OK
        assert not (b / "brand.txt").exists()
        assert "COPY" not in captured
