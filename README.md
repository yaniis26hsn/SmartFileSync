# Smart File Sync

> **Warning:** Always back up important files before running a real synchronization. The program can delete files from the source directory. Although it is designed to be safe, test it with `--dry-run` first and never use it on data you cannot afford to lose.

A lightweight, standard-library-only Python utility that synchronizes files from a **source** directory **A** into a **destination** directory **B**.

Unlike simple file-copy tools that treat same-named files as unconditional conflicts, **Smart File Sync compares actual file contents**. When a file in `A` and a file with the same relative path in `B` are byte-for-byte identical, the destination copy is kept and the source copy is deleted, freeing space without losing data.

## Features

* Compare files by their **actual contents**, not just their names.
* Detect identical contents using **SHA-256** hashing.
* Use file **size** as a fast preliminary comparison to avoid hashing when files are obviously different.
* Copy files that are missing from the destination.
* Keep both copies when the files are different (never overwrites anything).
* Delete the **source** file only when an identical destination file exists.
* Recursive directory support.
* Optional duplicate-content detection (**`--delete-duplicates`**) that finds source files whose contents match a destination file even when the names differ.
* `--dry-run` mode to preview every operation without modifying files.
* `--verbose` mode with detailed explanations for each decision.
* Symlinks are **skipped, never followed**.
* Refuses to operate when source and destination are nested inside one another.
* No external Python dependencies.

## How A → B Synchronization Works

Given:

```text
A/
├── photo.jpg
├── video.mp4
└── document.pdf

B/
├── photo.jpg
└── video.mp4
```

The program walks every file under `A` and compares it with the file at the same relative path under `B`.

The comparison follows this order:

```text
Find file with same relative path in B?
        │
        ▼
Does the destination file exist?
    │              │
   No             Yes
    │              │
  COPY          Same size?
   A→B        │          │
             No         Yes
              │          │
          DIFFERENT   SHA-256
                       │
                 ┌─────┴─────┐
                Same      Different
                 │            │
            IDENTICAL      DIFFERENT
             (delete A)    (keep A)
```

Checking size first avoids computing hashes when files are obviously different.

### Behavior Cases

**File missing in destination**

```text
A/document.pdf
B/document.pdf → does not exist
```

The file is **copied** from `A` to `B` (`COPY`).

**Same path + identical contents**

```text
A/photo.jpg → SHA-256: ABC123...
B/photo.jpg → SHA-256: ABC123...
```

Same size and same hash means identical contents. The **destination file is kept and the source file is deleted** (`IDENTICAL`).

**Same path + different contents**

```text
A/video.mp4 → 500 MB
B/video.mp4 → 450 MB
```

The files are considered different, either by size or by hash. **Neither file is modified** and the conflict is reported (`CONFLICT`).

**Different names + identical contents**

During normal synchronization this is not touched (a file is only compared with the same relative path in `B`). To delete source files whose **contents** match a destination file regardless of name, use the separate `--delete-duplicates` pass.

## How SHA-256 Is Used

* Each file's contents are read in chunks and reduced to a SHA-256 digest.
* Two files are considered **identical** only when they have the *same size* **and** the *same SHA-256 hash*.
* Size is checked first so hashes are rarely computed for files that differ in length.
* Every file is hashed at most once per pass; results are cached.

Because deletion requires both stat **and** hashing to succeed and match, a file is never deleted on a failed or partial read.

## Command-Line Options

```
usage: smart-file-sync [-h] [--dry-run] [--verbose] [--delete-duplicates]
                       source destination
```

| Option | Description |
| ------ | ----------- |
| `source` | Path to the source directory to synchronize from. |
| `destination` | Path to the destination directory. Created automatically if missing. |
| `--dry-run` | Analyze files and show what would happen without modifying anything. |
| `--verbose` | Show detailed information about each file and why it was classified. |
| `--delete-duplicates` | Detect source files whose contents match a destination file and delete them after confirmation. This is a separate pass from normal synchronization. |

## Safety Guarantees

The program only ever deletes **source** files, and only under strictly verified conditions:

1. A file with the corresponding name exists in the destination.
2. Both files have the same size.
3. Both files have the **same SHA-256 hash** (requiring a successful read of both).

Therefore:

```text
Same name + same size ≠ identical file

Same name + same size + same SHA-256
                ↓
          Identical contents
```

Additional guarantees:

* The **destination directory is never deleted** and no destination file is ever overwritten.
* In `--dry-run` mode **nothing is modified** — no deletes, no copies, and the destination directory is not even created.
* If a single file cannot be safely compared, copied, or deleted, it is reported as an error and left untouched; other files are still processed.
* Interaction errors are never fatal — an unexpected error becomes a clear message, and no traceback is dumped to the user.
* Errors in one file do not stop unrelated files from being processed.

## Symlink Handling

* **Symbolic links are skipped, never followed.** Both symlinked files and symlinked directories are ignored during traversal.
* This prevents a symlinked directory inside the source from escaping the source, recursing into the destination, or otherwise being walked.
* Only real regular files are considered for comparison, copying, or deletion.

## Source/Destination Nesting Restriction

Smart File Sync **refuses to run** when `source` and `destination` are the same directory or when one is nested inside the other.

If you try:

```bash
python -m smart_file_sync A A/backup
```

or

```bash
python -m smart_file_sync A/backup A
```

the program aborts with an error and exit code `1` rather than risk walking into (or deleting files from) the destination directory.

## Known TOCTOU Limitation

Hashing and deletion are separate operations. In the small window between computing a file's SHA-256 and deleting it, another process could modify the source file in place. Because the digest is already computed, the program could delete a file whose contents have since changed.

This is an inherent limitation of a single-pass command-line tool. For the highest safety, run against data that is not being concurrently modified, and rely on `--dry-run` and backups.

## Installation

Requires **Python 3.10+**. The runtime uses only the Python standard library; `pytest` is required only for development/testing.

Clone the repository:

```bash
git clone https://github.com/yaniishsn/smart-file-sync.git
cd smart-file-sync
```

Install in editable mode with development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Usage Examples

Run a real synchronization:

```bash
python -m smart_file_sync SOURCE DESTINATION
```

Preview what would happen without modifying anything:

```bash
python -m smart_file_sync SOURCE DESTINATION --dry-run
```

Run with detailed per-file explanations:

```bash
python -m smart_file_sync SOURCE DESTINATION --verbose
```

Detect and (after confirmation) delete source files whose contents duplicate a destination file:

```bash
python -m smart_file_sync SOURCE DESTINATION --delete-duplicates
```

Preview the duplicate-content detection without deleting anything:

```bash
python -m smart_file_sync SOURCE DESTINATION --delete-duplicates --dry-run
```

A console script is also installed, so you can run:

```bash
smart-file-sync SOURCE DESTINATION
```

### Dry-run example output

```text
--- DRY RUN ---

IDENTICAL  A/photo.jpg -> B/photo.jpg -> would delete source
COPY       A/document.pdf -> B/document.pdf
CONFLICT   A/video.mp4 -> B/video.mp4 -> files differ

--- END DRY RUN ---
```

With `--verbose`, each line additionally explains why the decision was made (for example, the matching SHA-256 digest for an `IDENTICAL` file).

## Project Structure

```text
smart-file-sync/
│
├── src/smart_file_sync/
│   ├── __init__.py          # Package marker
│   ├── __main__.py          # Enables `python -m smart_file_sync`
│   ├── main.py              # CLI entry point, argument parsing, validation
│   ├── sync.py              # Core A → B synchronization logic and SyncAction
│   ├── comparator.py        # Compares a source/destination file pair
│   ├── hasher.py            # Chunked SHA-256 file hashing
│   ├── operations.py        # File copy and delete primitives
│   ├── dedupe.py            # Optional --delete-duplicates pass
│   └── pathutil.py          # Safe symlink-avoiding walker and nesting check
│
├── tests/                   # pytest test suite
│   ├── test_cli.py
│   ├── test_comparator.py
│   ├── test_dedupe.py
│   ├── test_errors.py
│   ├── test_hasher.py
│   ├── test_pathutil.py
│   └── test_sync.py
│
├── pyproject.toml           # Project metadata and packaging
├── README.md
├── LICENSE
└── .gitignore
```

## Testing

Run the full test suite from the project root:

```bash
python -m pytest -q
```

The suite covers the CLI, synchronization logic, comparator, hasher, duplicate detection, error handling, and path safety (including symlink skipping and nesting rejection).

## Requirements and Dependencies

* Python 3.10+
* Windows, Linux, or macOS
* No runtime third-party packages — only the Python standard library (`argparse`, `hashlib`, `os`, `pathlib`, `shutil`, `sys`).
* Development/test dependency: `pytest` (installed via `pip install -e ".[dev]"`).

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0). See the [LICENSE](LICENSE) file for the full terms.

The AGPL-3.0 is a strong copyleft license. If you modify the software and make it available to users over a network, you must offer them access to the corresponding source code.
