"""Undo or redo refactor runs by scanning rope's change history for tagged changesets.

Usage:
    uv run python refactor_history.py undo --project-root /path/to/project
    uv run python refactor_history.py redo --project-root /path/to/project
    uv run python refactor_history.py undo --hash abc12345
    uv run python refactor_history.py undo --list

Each refactor run tags its changesets with [refactor:<hash>]. By default,
undo/redo targets the most recent run at the top of the relevant stack.
Use --hash to target a specific run, or --list to show all runs in history.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import extract_refactor_hash, resolve_project_root

from rope.base.project import Project


def _get_history_list(project: Project, action: str) -> list:
    if action == "undo":
        return project.history.undo_list
    return project.history.redo_list


def _apply(project: Project, action: str) -> None:
    if action == "undo":
        project.history.undo()
    else:
        project.history.redo()


def list_runs(project: Project, action: str) -> list[tuple[str, int, list[str]]]:
    """Return (hash, count, descriptions) for each refactor run in history."""
    runs: list[tuple[str, int, list[str]]] = []
    seen_hashes: dict[str, int] = {}

    for change in reversed(_get_history_list(project, action)):
        h = extract_refactor_hash(change.description)
        if h is None:
            continue
        if h not in seen_hashes:
            seen_hashes[h] = len(runs)
            runs.append((h, 0, []))
        idx = seen_hashes[h]
        runs[idx] = (
            runs[idx][0],
            runs[idx][1] + 1,
            runs[idx][2] + [change.description],
        )

    return runs


def find_top_hash(project: Project, action: str) -> str | None:
    """Find the hash of the most recent refactor run at the top of the stack."""
    for change in reversed(_get_history_list(project, action)):
        h = extract_refactor_hash(change.description)
        if h is not None:
            return h
    return None


def apply_by_hash(project: Project, action: str, target_hash: str) -> int:
    """Apply (undo or redo) all changesets with matching hash from the top of the stack.

    Returns the number of changesets applied.
    """
    count = 0
    history_list = _get_history_list(project, action)
    while history_list:
        change = history_list[-1]
        h = extract_refactor_hash(change.description)
        if h != target_hash:
            break
        _apply(project, action)
        count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for refactor history (undo/redo)."""
    parser = argparse.ArgumentParser(description="Undo or redo a refactor run")
    parser.add_argument("action", choices=["undo", "redo"], help="Action to perform")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Rope project root (default: git repository root)",
    )
    parser.add_argument(
        "--hash",
        type=str,
        default=None,
        help="Target a specific refactor hash (default: most recent)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all refactor runs in history",
    )
    return parser


def main(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = build_parser().parse_args()

    action = args.action
    past_tense = "Undone" if action == "undo" else "Redone"

    project_root = resolve_project_root(args.project_root)
    project = Project(str(project_root))

    if args.list:
        runs = list_runs(project, action)
        if not runs:
            print(f"No refactor runs found in {action} history.")
        else:
            for h, count, descs in runs:
                print(f"  {h}  ({count} changeset(s))")
                for d in descs[:3]:
                    print(f"    {d}")
                if count > 3:
                    print(f"    ... and {count - 3} more")
        project.close()
        return

    target = args.hash
    if target is None:
        target = find_top_hash(project, action)
        if target is None:
            print(f"No refactor runs found in {action} history.")
            project.close()
            return

    count = apply_by_hash(project, action, target)
    if count == 0:
        print(f"No changesets with hash {target} found at top of {action} stack.")
        print("Use --list to see available runs.")
    else:
        print(f"{past_tense} {count} changeset(s) for refactor run {target}.")

    project.close()


if __name__ == "__main__":
    main()
