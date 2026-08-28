"""Core synchronization logic for Smart File Sync."""

from dataclasses import dataclass

from pathlib import Path

from smart_file_sync.comparator import CompareResult, compare_files
from smart_file_sync.operations import copy_file, delete_file


@dataclass(frozen=True)
class SyncAction:
    """A single synchronization action for a file.

    Attributes:
        relative_path: Path of the file relative to the source directory.
        action: Human-readable description of the action taken.
        is_delete: Whether this action deletes the source file.
    """

    relative_path: Path
    action: str
    is_delete: bool = False


def sync(source: Path, destination: Path, dry_run: bool = False) -> list[SyncAction]:
    """Synchronize files from source directory A to destination directory B.

    For every file in the source directory:

    - If the corresponding file (same relative path) does not exist in B,
      it is copied from A to B.
    - If a file with the same relative path exists in B, file sizes are
      compared first, then SHA-256 hashes when sizes are equal.
    - If files are identical, the destination file B is kept and the source
      file A is deleted.
    - If files are different, neither file is deleted or overwritten; the
      conflict is reported.

    Args:
        source: Path to the source directory (A).
        destination: Path to the destination directory (B).
        dry_run: If True, actions are reported but no files are modified.

    Returns:
        A list of SyncAction describing what was (or would be) done.

    Raises:
        FileNotFoundError: If the source directory does not exist.
    """
    if not source.is_dir():
        raise NotADirectoryError(f"Source is not a directory: {source}")

    actions: list[SyncAction] = []
    for item in sorted(source.rglob("*")):
        if item.is_dir():
            continue

        relative = item.relative_to(source)
        dest_file = destination / relative

        result = compare_files(item, dest_file)

        if result == CompareResult.IDENTICAL:
            if _perform(dry_run):
                delete_file(item)
            actions.append(
                SyncAction(
                    relative_path=relative,
                    action="IDENTICAL -> DELETE SOURCE (keep destination)",
                    is_delete=True,
                )
            )

        elif result == CompareResult.DIFFERENT:
            actions.append(
                SyncAction(
                    relative_path=relative,
                    action="DIFFERENT -> CONFLICT (keep both, do not overwrite)",
                )
            )

        elif result == CompareResult.NEW:
            if _perform(dry_run):
                copy_file(item, dest_file)
            actions.append(
                SyncAction(
                    relative_path=relative,
                    action="NEW -> COPY TO DESTINATION",
                )
            )

    return actions


def _perform(dry_run: bool) -> bool:
    """Return True if a real action should be performed (not a dry run)."""
    return not dry_run
