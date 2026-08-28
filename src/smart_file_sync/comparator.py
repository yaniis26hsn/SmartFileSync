"""File comparison logic for Smart File Sync."""

from dataclasses import dataclass

from enum import Enum

from pathlib import Path

from smart_file_sync.hasher import sha256_file


class CompareResult(Enum):
    """Result of comparing two files."""

    IDENTICAL = "identical"
    DIFFERENT = "different"
    NEW = "new"


@dataclass(frozen=True)
class FileComparison:
    """Outcome of comparing two files, including the reason.

    Attributes:
        result: The classification of the comparison.
        reason: A human-readable explanation of why the files were classified
            the way they were.
    """

    result: CompareResult
    reason: str


def _compare(source: Path, destination: Path) -> FileComparison:
    """Compare two files by size and SHA-256 hash, returning a reason.

    Args:
        source: Path to the source file.
        destination: Path to the destination file.

    Returns:
        A FileComparison describing the result and the reason.
    """
    if not destination.exists():
        return FileComparison(
            result=CompareResult.NEW,
            reason="no file with this relative path exists in the destination",
        )

    source_size = source.stat().st_size
    destination_size = destination.stat().st_size

    if source_size != destination_size:
        return FileComparison(
            result=CompareResult.DIFFERENT,
            reason=(
                f"different size (source {source_size} bytes, "
                f"destination {destination_size} bytes)"
            ),
        )

    if sha256_file(source) != sha256_file(destination):
        return FileComparison(
            result=CompareResult.DIFFERENT,
            reason="same size but different SHA-256 hash",
        )

    return FileComparison(
        result=CompareResult.IDENTICAL,
        reason="same size and same SHA-256 hash",
    )


def compare_files(source: Path, destination: Path) -> CompareResult:
    """Compare a source file against a destination file.

    Convenience wrapper around the detailed comparison that only returns the
    classification. Uses file size as a quick check, then SHA-256 for
    confirmation.

    Args:
        source: Path to the source file.
        destination: Path to the destination file.

    Returns:
        CompareResult indicating whether files are identical, different, or new.
    """
    return _compare(source, destination).result
