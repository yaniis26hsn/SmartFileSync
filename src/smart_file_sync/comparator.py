"""File comparison logic for Smart File Sync."""

from dataclasses import dataclass, field

from enum import Enum

from pathlib import Path

from smart_file_sync.hasher import sha256_file


class CompareResult(Enum):
    """Result of comparing two files."""

    IDENTICAL = "identical"
    DIFFERENT = "different"
    NEW = "new"
    ERROR = "error"


@dataclass(frozen=True)
class FileComparison:
    """Outcome of comparing two files, including the reason.

    Attributes:
        result: The classification of the comparison.
        reason: A human-readable explanation of why the files were classified
            the way they were.
        error: Set to a message when ``result`` is ``ERROR``, else empty.
    """

    result: CompareResult
    reason: str = ""
    error: str = field(default="")


def _error(reason: str, error: str) -> FileComparison:
    """Build a FileComparison describing a comparison failure."""
    return FileComparison(result=CompareResult.ERROR, reason=reason, error=error)


def _compare(source: Path, destination: Path) -> FileComparison:
    """Compare two files by size and SHA-256 hash, returning a reason.

    The comparison never reports files as identical unless both files could be
    stat'd and hashed successfully and produced equal hashes. Any stat or
    hashing failure yields an ``ERROR`` result instead of a risky guess.

    Args:
        source: Path to the source file.
        destination: Path to the destination file.

    Returns:
        A FileComparison describing the result and the reason.
    """
    try:
        if not destination.exists():
            return FileComparison(
                result=CompareResult.NEW,
                reason="no file with this relative path exists in the destination",
            )
    except OSError as exc:
        return _error("could not check the destination file", str(exc))

    try:
        source_size = source.stat().st_size
    except OSError as exc:
        return _error("could not read the source file size", str(exc))

    try:
        destination_size = destination.stat().st_size
    except OSError as exc:
        return _error("could not read the destination file size", str(exc))

    if source_size != destination_size:
        return FileComparison(
            result=CompareResult.DIFFERENT,
            reason=(
                f"different size (source {source_size} bytes, "
                f"destination {destination_size} bytes)"
            ),
        )

    try:
        source_hash = sha256_file(source)
    except OSError as exc:
        return _error("could not hash the source file", str(exc))

    try:
        destination_hash = sha256_file(destination)
    except OSError as exc:
        return _error("could not hash the destination file", str(exc))

    if source_hash != destination_hash:
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
        CompareResult indicating whether files are identical, different, new,
        or errored.
    """
    return _compare(source, destination).result
