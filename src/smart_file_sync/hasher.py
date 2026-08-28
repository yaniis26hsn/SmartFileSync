"""File hashing utilities using SHA-256."""

from pathlib import Path

import hashlib


def sha256_file(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute the SHA-256 hash of a file.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Size of each read chunk in bytes.

    Returns:
        Hexadecimal digest of the file's SHA-256 hash.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()
