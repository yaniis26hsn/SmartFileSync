"""File comparison logic for Smart File Sync."""

from enum import Enum

from pathlib import Path

from smart_file_sync.hasher import sha256_file


class CompareResult(Enum):
    """Result of comparing two files."""

    IDENTICAL = "identical"
    DIFFERENT = "different"
    NEW = "new"


def compare_files(source: Path, destination: Path) -> CompareResult:
    """Compare a source file against a destination file.

    Uses file size as a quick check, then SHA-256 hash for confirmation.

    Args:
        source: Path to the source file.
        destination: Path to the destination file.

    Returns:
        CompareResult indicating whether files are identical, different, or new.
    """
    if not destination.exists():
        return CompareResult.NEW

    if source.stat().st_size != destination.stat().st_size:
        return CompareResult.DIFFERENT

    if sha256_file(source) != sha256_file(destination):
        return CompareResult.DIFFERENT

    return CompareResult.IDENTICAL
