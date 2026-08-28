"""Core synchronization logic for Smart File Sync."""

from pathlib import Path

from smart_file_sync.comparator import CompareResult, compare_files
from smart_file_sync.operations import copy_file, delete_file


def sync(source: Path, destination: Path, dry_run: bool = False) -> None:
    """Synchronize files from source directory to destination directory.

    Args:
        source: Path to the source directory.
        destination: Path to the destination directory.
        dry_run: If True, only print actions without performing them.
    """
    for item in source.rglob("*"):
        if item.is_dir():
            continue

        relative = item.relative_to(source)
        dest_file = destination / relative

        result = compare_files(item, dest_file)

        if result == CompareResult.IDENTICAL:
            if dry_run:
                print(f"IDENTICAL  {relative}")
                print(f"           -> DELETE SOURCE")
            else:
                delete_file(item)
                print(f"DELETED    {relative}")

        elif result == CompareResult.DIFFERENT:
            if dry_run:
                print(f"DIFFERENT  {relative}")
                print(f"           -> KEEP SOURCE")
            else:
                print(f"KEPT       {relative}")

        elif result == CompareResult.NEW:
            if dry_run:
                print(f"NEW        {relative}")
                print(f"           -> COPY TO DESTINATION")
            else:
                copy_file(item, dest_file)
                print(f"COPIED     {relative}")
