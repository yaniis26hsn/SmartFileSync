"""Optional duplicate-content detection for Smart File Sync.

This module implements a separate, opt-in pass that can delete source files
whose *contents* are identical to a destination file, regardless of filename
or relative path. It is never activated by normal A -> B synchronization; it
only runs when the ``--delete-duplicates`` flag is provided.
"""

from dataclasses import dataclass

from pathlib import Path

from typing import Callable

from smart_file_sync.hasher import sha256_file
from smart_file_sync.operations import delete_file
from smart_file_sync.pathutil import paths_are_nested, walk_files


@dataclass(frozen=True)
class DuplicateMatch:
    """A source file whose content matches a destination file.

    Attributes:
        source: Path to the source file (a deletion candidate).
        destination: Path to the destination file (never deleted).
        size: Size in bytes shared by both files.
        sha256: The shared SHA-256 hash of both files.
    """

    source: Path
    destination: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class DedupeOutcome:
    """The result of processing a duplicate-content match.

    Attributes:
        match: The duplicate match that was processed.
        would_delete: Whether the source would be deleted (dry-run).
        deleted: Whether the source file was actually deleted.
        error: A non-empty message if something went wrong, else None.
    """

    match: DuplicateMatch
    would_delete: bool = False
    deleted: bool = False
    error: str | None = None


def _iter_files(root: Path) -> list[Path]:
    """Return all regular files under root, skipping symlinks and unreadable entries."""
    return walk_files(root)


def find_duplicates(source: Path, destination: Path) -> list[DuplicateMatch]:
    """Find source files whose content matches a destination file.

    Only files sharing the same size are ever hashed. Each file is hashed at
    most once. A source file is reported as a duplicate only when a destination
    file with identical content exists. Symlinks are never followed.

    Args:
        source: Root of the source directory.
        destination: Root of the destination directory.

    Returns:
        A list of DuplicateMatch for every source file that duplicates the
        content of a destination file.

    Raises:
        ValueError: If ``source`` and ``destination`` are the same or nested.
    """
    if paths_are_nested(source, destination):
        raise ValueError(
            "Source and destination directories must not be the same or nested: "
            f"{source}, {destination}"
        )

    by_size: dict[int, list[tuple[str, Path]]] = {}
    for kind, root in (("source", source), ("dest", destination)):
        for path in _iter_files(root):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            by_size.setdefault(size, []).append((kind, path))

    cache: dict[Path, str] = {}
    matches: list[DuplicateMatch] = []

    for size, items in by_size.items():
        has_source = any(kind == "source" for kind, _ in items)
        has_dest = any(kind == "dest" for kind, _ in items)
        if not (has_source and has_dest):
            continue

        by_hash: dict[str, list[tuple[str, Path]]] = {}
        for kind, path in items:
            try:
                digest = cache.get(path) or sha256_file(path)
            except OSError:
                continue
            cache[path] = digest
            by_hash.setdefault(digest, []).append((kind, path))

        for digest, group in by_hash.items():
            dests = [p for k, p in group if k == "dest"]
            sources = [p for k, p in group if k == "source"]
            if not dests or not sources:
                continue
            first_dest = dests[0]
            for src in sources:
                matches.append(
                    DuplicateMatch(
                        source=src,
                        destination=first_dest,
                        size=size,
                        sha256=digest,
                    )
                )

    return matches


def _default_confirm(match: DuplicateMatch) -> bool:
    """Default confirmation prompt for deleting a source file.

    Returns False (keep the file) if no confirmation can be obtained.
    """
    try:
        answer = input(
            f"Delete duplicate source '{match.source}' "
            f"(destination '{match.destination}' is kept)? [y/N] "
        )
    except (OSError, EOFError):
        return False
    return answer.strip().lower() in ("y", "yes")


def delete_duplicates(
    source: Path,
    destination: Path,
    dry_run: bool = False,
    confirm: Callable[[DuplicateMatch], bool] | None = None,
) -> list[DedupeOutcome]:
    """Find and (if confirmed) delete duplicate-content source files.

    In dry-run mode nothing is deleted and no confirmation is requested.

    Args:
        source: Root of the source directory.
        destination: Root of the destination directory.
        dry_run: If True, only report; never delete or ask for confirmation.
        confirm: Callable deciding whether a source file may be deleted. When
            None, an interactive prompt is used.

    Returns:
        A list of DedupeOutcome describing what happened for each match.
    """
    matches = find_duplicates(source, destination)
    ask = confirm or _default_confirm

    outcomes: list[DedupeOutcome] = []
    for match in matches:
        if dry_run:
            outcomes.append(
                DedupeOutcome(match=match, would_delete=True, deleted=False)
            )
            continue

        try:
            approved = ask(match)
        except (OSError, EOFError) as exc:
            outcomes.append(
                DedupeOutcome(match=match, deleted=False, error=str(exc))
            )
            continue

        if not approved:
            outcomes.append(DedupeOutcome(match=match, deleted=False))
            continue

        try:
            delete_file(match.source)
            outcomes.append(DedupeOutcome(match=match, deleted=True))
        except OSError as exc:
            outcomes.append(
                DedupeOutcome(match=match, deleted=False, error=str(exc))
            )

    return outcomes
