"""Core synchronization logic for Smart File Sync."""

from dataclasses import dataclass

from pathlib import Path

from smart_file_sync.comparator import CompareResult, compare_files
from smart_file_sync.operations import copy_file, delete_file


class SyncStatus:
    """Canonical status labels used to communicate synchronization decisions."""

    COPY = "COPY"
    IDENTICAL = "IDENTICAL"
    CONFLICT = "CONFLICT"
    SKIP = "SKIP"


@dataclass(frozen=True)
class SyncAction:
    """A single synchronization decision for a file.

    Attributes:
        relative_path: Path of the file relative to the source directory.
        status: One of the SyncStatus labels.
        source: Path to the source file.
        destination: Path to the destination file.
        is_delete: Whether this action deletes the source file.
        message: Optional extra detail shown alongside the status.
    """

    relative_path: Path
    status: str
    source: Path
    destination: Path
    is_delete: bool = False
    message: str = ""


def sync(source: Path, destination: Path, dry_run: bool = False) -> list[SyncAction]:
    """Synchronize files from source directory A to destination directory B.

    For every file in the source directory:

    - If the corresponding file (same relative path) does not exist in B, it
      is copied from A to B (status ``COPY``).
    - If a file with the same relative path exists in B and is identical
      (same size and same SHA-256 hash), the destination file is kept and the
      source file is deleted (status ``IDENTICAL``).
    - If the files are different, neither is deleted or overwritten; the
      conflict is reported (status ``CONFLICT``).
    - ``SKIP`` is reserved for items that are intentionally left untouched.

    Args:
        source: Path to the source directory (A).
        destination: Path to the destination directory (B).
        dry_run: If True, actions are reported but no files are modified and no
            destination directories are created.

    Returns:
        A list of SyncAction describing what was (or would be) done.

    Raises:
        FileNotFoundError: If the source directory does not exist.
        NotADirectoryError: If ``source`` exists but is not a directory.
    """
    if not source.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source}")
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
            if not dry_run:
                delete_file(item)
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.IDENTICAL,
                    source=item,
                    destination=dest_file,
                    is_delete=True,
                    message="would delete source" if dry_run else "deleted source",
                )
            )

        elif result == CompareResult.DIFFERENT:
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.CONFLICT,
                    source=item,
                    destination=dest_file,
                    message="files differ",
                )
            )

        elif result == CompareResult.NEW:
            if not dry_run:
                copy_file(item, dest_file)
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.COPY,
                    source=item,
                    destination=dest_file,
                )
            )

    return actions
