"""Filesystem path helpers for safe traversal and validation."""

import os

from pathlib import Path


def walk_files(root: Path) -> list[Path]:
    """Recursively yield regular files under ``root`` without following symlinks.

    Symlinked files and symlinked directories are deliberately skipped so that
    traversal can never escape the intended directory or recurse through a link.

    Args:
        root: The directory to walk.

    Returns:
        A sorted list of regular file paths, or an empty list if the root is not
        an accessible directory.
    """
    files: list[Path] = []

    def _walk(directory: Path) -> None:
        try:
            entries = os.scandir(directory)
        except OSError:
            return
        with entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        _walk(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        files.append(Path(entry.path))
                except OSError:
                    continue

    _walk(root)
    files.sort()
    return files


def _resolve(path: Path) -> Path | None:
    """Return the resolved absolute path, or None if it cannot be resolved."""
    try:
        return path.resolve()
    except OSError:
        return None


def _strictly_within(child: Path, parent: Path) -> bool:
    """Return True if ``child`` is strictly inside ``parent`` (not equal)."""
    try:
        rel = child.relative_to(parent)
    except ValueError:
        return False
    return rel.parts != ()


def paths_are_nested(first: Path, second: Path) -> bool:
    """Return True if either path is strictly contained within the other.

    This is used to reject configurations where the destination directory sits
    inside (or contains) the source directory, which would otherwise cause the
    walk to recurse into the destination or risk deleting files in it.

    Args:
        first: First path.
        second: Second path.

    Returns:
        True if one resolved path strictly contains the other.
    """
    a = _resolve(first)
    b = _resolve(second)
    if a is None or b is None:
        return False
    return _strictly_within(a, b) or _strictly_within(b, a)
