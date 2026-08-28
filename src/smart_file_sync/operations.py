"""File operation utilities for Smart File Sync."""

import shutil

from pathlib import Path


def copy_file(source: Path, destination: Path) -> None:
    """Copy a file from source to destination.

    Args:
        source: Path to the source file.
        destination: Path to the destination file.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def delete_file(file_path: Path) -> None:
    """Delete a file.

    Args:
        file_path: Path to the file to delete.
    """
    file_path.unlink()
