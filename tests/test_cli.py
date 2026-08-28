"""Unit tests for the command-line interface of Smart File Sync."""

from pathlib import Path

from smart_file_sync.main import _format_action, parse_args
from smart_file_sync.sync import SyncAction, SyncStatus


class TestParseArgs:
    def test_parses_source_and_destination(self) -> None:
        ns = parse_args(["A", "B"])
        assert ns.source == Path("A")
        assert ns.destination == Path("B")
        assert ns.dry_run is False

    def test_parses_dry_run_flag(self) -> None:
        ns = parse_args(["A", "B", "--dry-run"])
        assert ns.dry_run is True


class TestFormatAction:
    def _action(self, status: str, name: str = "f.txt", message: str = "") -> SyncAction:
        return SyncAction(
            relative_path=Path(name),
            status=status,
            source=Path("A") / name,
            destination=Path("B") / name,
            message=message,
        )

    def test_copy_format(self) -> None:
        line = _format_action(self._action(SyncStatus.COPY))
        assert "COPY" in line
        assert "f.txt" in line
        assert line.replace("\\", "/").endswith("A/f.txt -> B/f.txt")

    def test_identical_format(self) -> None:
        line = _format_action(self._action(SyncStatus.IDENTICAL, name="photo.jpg"))
        assert "IDENTICAL" in line
        assert "photo.jpg" in line
        assert "would delete source" in line or "delete source" in line

    def test_conflict_format(self) -> None:
        line = _format_action(self._action(SyncStatus.CONFLICT, name="video.mp4"))
        assert "CONFLICT" in line
        assert "video.mp4" in line
        assert "files differ" in line

    def test_skip_format(self) -> None:
        line = _format_action(self._action(SyncStatus.SKIP, message="already in sync"))
        assert "SKIP" in line
