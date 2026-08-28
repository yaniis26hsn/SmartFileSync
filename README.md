# Smart File Sync

> **Warning:** This script is currently under testing. Do not use it on critical or important files. Always keep backups before running synchronization.

A lightweight Python utility for safely synchronizing files between two directories.

Unlike traditional file-copy operations that treat files with the same name as conflicts, **Smart File Sync compares the actual file contents**. When a file in the source directory and a file with the same name in the destination directory are identical, the source file is deleted and the destination file is kept.

## Features

* Compare files by their actual contents.
* Detect identical files using **SHA-256**.
* Use file size as a quick preliminary comparison.
* Copy files that don't exist in the destination.
* Keep files that are different.
* Delete the source file when an identical destination file already exists.
* Recursive directory support.
* Dry-run mode to preview operations without modifying files.
* Command-line interface.
* No external Python dependencies.

## How It Works

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

The program compares the files in `A` with the corresponding files in `B`.

### Case 1 — File doesn't exist in B

```text
A/document.pdf
B/document.pdf → doesn't exist
```

Action:

```text
COPY A/document.pdf → B/document.pdf
```

### Case 2 — Same name, different size

```text
A/video.mp4 → 500 MB
B/video.mp4 → 450 MB
```

The files are considered different.

The source file is **not deleted**.

### Case 3 — Same name and same size

The program calculates the SHA-256 hash of both files.

```text
A/photo.jpg → SHA-256: ABC123...
B/photo.jpg → SHA-256: ABC123...
```

The files contain exactly the same data.

Action:

```text
DELETE A/photo.jpg
KEEP B/photo.jpg
```

### Case 4 — Same name and same size, different hash

```text
A/photo.jpg → SHA-256: ABC123...
B/photo.jpg → SHA-256: XYZ789...
```

The files are different even though their names and sizes are identical.

Action:

```text
KEEP A/photo.jpg
KEEP B/photo.jpg
```

## Comparison Strategy

The comparison follows this order:

```text
Same filename?
       │
       ▼
Same size?
   │       │
  No      Yes
   │       │
Different  SHA-256
           │
       ┌───┴───┐
      Same   Different
       │         │
    Identical  Different
       │         │
   Delete A   Keep A
```

Checking the file size first avoids calculating hashes when the files are obviously different.

## Technology Stack

| Technology | Purpose                                |
| ---------- | -------------------------------------- |
| Python 3.x | Main programming language              |
| `pathlib`  | File and directory management          |
| `hashlib`  | SHA-256 file hashing                   |
| `shutil`   | File copying                           |
| `argparse` | Command-line interface                 |
| `os`       | Operating-system filesystem operations |

All libraries are part of Python's standard library.

## Requirements

* Python 3.10+
* Windows, Linux, or macOS

No external packages are required.

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/smart-file-sync.git
```

Enter the project directory:

```bash
cd smart-file-sync
```

Run the program:

```bash
python main.py
```

## Usage

Basic usage:

```bash
python main.py <source> <destination>
```

Example:

```bash
python main.py "C:\Users\User\Documents\A" "D:\Backup\B"
```

### Dry Run

Use dry-run mode to see what would happen without modifying any files:

```bash
python main.py A B --dry-run
```

Example output:

```text
IDENTICAL  A/photo.jpg
           → DELETE SOURCE

DIFFERENT  A/video.mp4
           → KEEP SOURCE

NEW        A/document.pdf
           → COPY TO DESTINATION
```

## Safety

Because the program can delete files from the source directory, **dry-run mode should be used before performing a real synchronization**.

The program should only delete a source file when:

1. A file with the corresponding name exists in the destination.
2. Both files have the same size.
3. Both files have the same SHA-256 hash.

Therefore:

```text
Same name + same size ≠ identical file

Same name + same size + same SHA-256
                ↓
          Identical contents
```

## Project Structure

```text
smart-file-sync/
│
├── main.py
├── file_compare.py
├── file_operations.py
├── README.md
└── .gitignore
```

### `main.py`

Handles the command-line interface and program execution.

### `file_compare.py`

Contains the logic for:

* Comparing file sizes.
* Calculating SHA-256 hashes.
* Determining whether two files have identical contents.

### `file_operations.py`

Handles:

* Copying files.
* Deleting source files.
* Directory operations.

## Future Improvements

Possible future features:

* Progress bars for large files.
* Parallel hashing for better performance.
* Logging to a file.
* Backup/recovery system before deletion.
* File modification-date comparison.
* Handling filename conflicts interactively.
* Synchronization statistics.
* Configuration file.
* Graphical user interface.
* Duplicate-file detection even when filenames are different.
* Support for synchronization in both directions.

## License

This project is licensed under the MIT License.
