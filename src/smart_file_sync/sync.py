"""Core synchronization logic for Smart File Sync."""

from dataclasses import dataclass, field

from pathlib import Path

from smart_file_sync.comparator import CompareResult, _compare
from smart_file_sync.operations import copy_file, delete_file


class SyncStatus:
    """Canonical status labels used to communicate synchronization decisions."""

    COPY = "COPY"
    IDENTICAL = "IDENTICAL"
    CONFLICT = "CONFLICT"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SyncAction:
    """A single synchronization decision for a file.

    Attributes:
        relative_path: Path of the file relative to the source directory.
        status: One of the SyncStatus labels.
        source: Path to the source file.
        destination: Path to the destination file.
        is_delete: Whether this action deletes the source file.
        reason: Optional detailed explanation of why this decision was made.
        error: A message describing a failure when status is ``ERROR``.
    """

    relative_path: Path
    status: str
    source: Path
    destination: Path
    is_delete: bool = False
    reason: str = ""
    error: str = field(default="")


def _collect_files(source: Path) -> list[Path]:
    """Return candidate paths under source, skipping unreadable entries.

    Args:
        source: Root directory to walk.

    Returns:
        A list of paths, which may include directories (skipped later).
    """
    entries: list[Path] = []
    try:
        for candidate in source.rglob("*"):
            entries.append(candidate)
    except OSError:
        pass
    return entries


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
    - If a file cannot be safely compared, copied, or deleted, an ``ERROR``
      action is reported and the file is left untouched.

    A source file is deleted only when the comparison returned ``IDENTICAL``,
    which requires successful stat and hashing of both files. One problematic
    file does not stop unrelated files from being processed.

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
    for item in _collect_files(source):
        relative = item.relative_to(source)

        try:
            if item.is_dir():
                continue
        except OSError as exc:
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.ERROR,
                    source=item,
                    destination=destination / relative,
                    error=f"could not inspect entry: {exc}",
                )
            )
            continue

        dest_file = destination / relative

        comparison = _compare(item, dest_file)
        result = comparison.result

        if result == CompareResult.ERROR:
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.ERROR,
                    source=item,
                    destination=dest_file,
                    error=comparison.error,
                )
            )
            continue

        if result == CompareResult.IDENTICAL:
            if not dry_run:
                try:
                    delete_file(item)
                except OSError as exc:
                    actions.append(
                        SyncAction(
                            relative_path=relative,
                            status=SyncStatus.ERROR,
                            source=item,
                            destination=dest_file,
                            error=f"could not delete source file: {exc}",
                        )
                    )
                    continue
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.IDENTICAL,
                    source=item,
                    destination=dest_file,
                    is_delete=True,
                    reason=comparison.reason,
                )
            )

        elif result == CompareResult.DIFFERENT:
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.CONFLICT,
                    source=item,
                    destination=dest_file,
                    reason=comparison.reason,
                )
            )

        elif result == CompareResult.NEW:
            if not dry_run:
                try:
                    copy_file(item, dest_file)
                except OSError as exc:
                    actions.append(
                        SyncAction(
                            relative_path=relative,
                            status=SyncStatus.ERROR,
                            source=item,
                            destination=dest_file,
                            error=f"could not copy source file: {exc}",
                        )
                    )
                    continue
            actions.append(
                SyncAction(
                    relative_path=relative,
                    status=SyncStatus.COPY,
                    source=item,
                    destination=dest_file,
                    reason=comparison.reason,
                )
            )

    return actions
