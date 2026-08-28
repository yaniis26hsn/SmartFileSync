"""Command-line interface for Smart File Sync."""

import argparse

import sys

from pathlib import Path

from smart_file_sync.sync import SyncAction, SyncStatus, sync


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="smart-file-sync",
        description="Safely synchronize files from a source directory to a destination directory.",
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to the source directory.",
    )
    parser.add_argument(
        "destination",
        type=Path,
        help="Path to the destination directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze files and show what would happen without modifying anything.",
    )
    return parser.parse_args(argv)


def _format_action(action: SyncAction) -> str:
    """Format a SyncAction into a human-readable output line.

    Args:
        action: The action to format.

    Returns:
        A single formatted line describing the operation.
    """
    status = action.status.ljust(10)
    if action.status == SyncStatus.COPY:
        return f"{status} {action.source} -> {action.destination}"
    if action.status == SyncStatus.IDENTICAL:
        suffix = action.message if action.message else "would delete source"
        return f"{status} {action.source} -> {action.destination} -> {suffix}"
    if action.status == SyncStatus.CONFLICT:
        return f"{status} {action.source} -> {action.destination} -> files differ"
    return f"{status} {action.source} -> {action.destination} -> {action.message}"


def main(argv: list[str] | None = None) -> None:
    """Entry point for the CLI.

    Args:
        argv: Optional list of arguments to parse. Defaults to sys.argv.
    """
    args = parse_args(argv)

    if not args.source.exists():
        print(f"Error: Source directory '{args.source}' does not exist.")
        sys.exit(1)

    if not args.source.is_dir():
        print(f"Error: Source '{args.source}' is not a directory.")
        sys.exit(1)

    if args.dry_run:
        print("--- DRY RUN ---\n")

    actions: list[SyncAction] = sync(args.source, args.destination, dry_run=args.dry_run)

    for action in actions:
        print(_format_action(action))

    if args.dry_run:
        print("\n--- END DRY RUN ---")


if __name__ == "__main__":
    main()
