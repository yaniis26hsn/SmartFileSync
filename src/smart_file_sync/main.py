"""Command-line interface for Smart File Sync."""

import argparse

import os

import sys

from pathlib import Path

from smart_file_sync.dedupe import (
    DedupeOutcome,
    DuplicateMatch,
    delete_duplicates,
)
from smart_file_sync.sync import SyncAction, SyncStatus, sync

EXIT_OK = 0
EXIT_ERROR = 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate the shape of command-line arguments.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="smart-file-sync",
        description=(
            "Safely synchronize files from a source directory into a "
            "destination directory."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to the source directory to synchronize from.",
    )
    parser.add_argument(
        "destination",
        type=Path,
        help="Path to the destination directory. Created automatically if missing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze files and show what would happen without modifying anything.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed information about each file and why it was classified.",
    )
    parser.add_argument(
        "--delete-duplicates",
        action="store_true",
        help=(
            "Detect source files whose contents match a destination file and "
            "delete them after confirmation. This is a separate pass from "
            "normal synchronization."
        ),
    )
    return parser.parse_args(argv)


def _validate(source: Path, destination: Path) -> str | None:
    """Validate source and destination paths.

    Args:
        source: Path to the source directory.
        destination: Path to the destination directory.

    Returns:
        An error message if validation fails, otherwise None.
    """
    if not source.exists():
        return f"Source directory does not exist: {source}"
    if not source.is_dir():
        return f"Source is not a directory: {source}"
    try:
        same = os.path.samefile(source, destination)
    except FileNotFoundError:
        same = source.resolve() == destination.resolve()
    except OSError:
        same = False
    if same:
        return f"Source and destination resolve to the same directory: {source}"
    return None


def _format_action(action: SyncAction, verbose: bool = False) -> str:
    """Format a SyncAction into a human-readable output line.

    Args:
        action: The action to format.
        verbose: If True, include the detailed reason for the decision.

    Returns:
        A single formatted line describing the operation.
    """
    status = action.status.ljust(10)
    base = f"{status} {action.source} -> {action.destination}"

    if action.status == SyncStatus.IDENTICAL:
        suffix = action.reason if verbose else "would delete source"
        line = f"{base} -> {suffix}"
    elif action.status == SyncStatus.CONFLICT:
        line = f"{base} -> files differ"
    elif action.status == SyncStatus.ERROR:
        line = f"{base} -> ERROR: {action.error}"
    elif action.status == SyncStatus.COPY:
        line = base
    else:
        line = base

    if verbose and action.status not in (SyncStatus.IDENTICAL,) and action.reason:
        line = f"{line}\n           - {action.reason}"

    return line


def _format_duplicate(outcome: DedupeOutcome) -> str:
    """Format a dedupe outcome into a human-readable block.

    Args:
        outcome: The outcome to format.

    Returns:
        A multi-line string describing the duplicate-content match and action.
    """
    match = outcome.match
    if outcome.would_delete:
        action = "would delete source"
    elif outcome.deleted:
        action = "deleted source"
    elif outcome.error is not None:
        action = f"error: {outcome.error}"
    else:
        action = "keep source (rejected)"

    return (
        f"DUPLICATE CONTENT\n"
        f"  Source:      {match.source}\n"
        f"  Destination: {match.destination}\n"
        f"  Action:      {action}"
    )


def _run_dedupe(args: argparse.Namespace) -> int:
    """Run the opt-in duplicate-content deletion pass.

    Args:
        args: Parsed command-line arguments.

    Returns:
        EXIT_OK on success, EXIT_ERROR on any filesystem error.
    """
    if args.dry_run:
        print("--- DRY RUN ---\n")

    try:
        outcomes: list[DedupeOutcome] = delete_duplicates(
            args.source,
            args.destination,
            dry_run=args.dry_run,
        )
    except OSError as exc:
        print(f"Error during duplicate detection: {exc}", file=sys.stderr)
        return EXIT_ERROR

    for outcome in outcomes:
        print(_format_duplicate(outcome))

    if args.dry_run:
        print("\n--- END DRY RUN ---")

    return EXIT_OK


def run(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.

    Returns:
        EXIT_OK on success, EXIT_ERROR on any validation or filesystem error.
    """
    args = parse_args(argv)

    error = _validate(args.source, args.destination)
    if error is not None:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_ERROR

    if args.delete_duplicates:
        return _run_dedupe(args)

    try:
        if not args.dry_run and not args.destination.is_dir():
            args.destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"Error: could not create destination directory "
            f"'{args.destination}': {exc}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if args.dry_run:
        print("--- DRY RUN ---\n")

    try:
        actions: list[SyncAction] = sync(
            args.source, args.destination, dry_run=args.dry_run
        )
    except OSError as exc:
        print(f"Error during synchronization: {exc}", file=sys.stderr)
        return EXIT_ERROR

    for action in actions:
        print(_format_action(action, verbose=args.verbose))

    if args.dry_run:
        print("\n--- END DRY RUN ---")

    return EXIT_OK


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point that exits with the run result code.

    Unexpected exceptions are reported as a clear message rather than a raw
    traceback, while preserving the error exit code.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.
    """
    try:
        code = run(argv)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        code = 130
    except Exception as exc:  # noqa: BLE001 - top-level safety net
        print(f"Unexpected error: {exc}", file=sys.stderr)
        code = EXIT_ERROR
    sys.exit(code)


if __name__ == "__main__":
    main()
