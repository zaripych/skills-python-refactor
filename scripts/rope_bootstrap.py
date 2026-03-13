"""Bootstrap for rope refactor scripts.

Handles project setup, dry-run mode, git safety checks, and diff output.
Every refactor script imports this and calls `run()` with a refactor function.

Usage in refactor scripts:

    from rope_bootstrap import run, RefactorContext

    def setup_args(parser):
        parser.add_argument("directory", type=Path, help="Directory to scan")

    def refactor(ctx: RefactorContext) -> None:
        for f in sorted(ctx.args.directory.rglob("*.py")):
            resource = ctx.get_resource(f)
            source = resource.read()
            # ... compute new_source ...
            ctx.write(resource, new_source)

    if __name__ == "__main__":
        run(refactor, description="My refactor script", setup_args=setup_args)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rope.base.change import Change, ChangeContents, ChangeSet
from rope.base.fscommands import FileSystemCommands, FileContent, unicode_to_file_data
from rope.base.project import Project
from rope.base.resources import File
from rope.contrib.changestack import ChangeStack


class SetupArgsFn(Protocol):
    """Callback to add script-specific arguments to the parser."""

    def __call__(self, parser: ArgumentParser) -> None: ...


class RefactorFn(Protocol):
    """Refactor callback. Use ctx.write() to queue changes — never call
    resource.write() directly, as that bypasses dry-run, diff, and backup."""

    def __call__(self, ctx: RefactorContext) -> None: ...


class OverlayFSCommands:
    """Wraps real fscommands, redirecting writes to an in-memory overlay.
    Reads check the overlay first, falling back to disk."""

    def __init__(self, real: FileSystemCommands) -> None:
        self._real = real
        self._overlay: dict[str, FileContent] = {}

    def read(self, path: str) -> FileContent:
        if path in self._overlay:
            return self._overlay[path]
        return self._real.read(path)

    def write(self, path: str, data: FileContent) -> None:
        self._overlay[path] = data

    def create_file(self, path: str) -> None:
        self._overlay[path] = FileContent(b"")

    def create_folder(self, path: str) -> None:
        self._real.create_folder(path)

    def move(self, path: str, new_location: str) -> None:
        if path in self._overlay:
            self._overlay[new_location] = self._overlay.pop(path)
        else:
            self._overlay[new_location] = self._real.read(path)

    def remove(self, path: str) -> None:
        self._overlay.pop(path, None)

    def commit(self) -> None:
        """Flush all in-memory changes to disk."""
        for path, data in self._overlay.items():
            self._real.write(path, data)
        self._overlay.clear()


@dataclass
class PendingWrite:
    resource: File
    original: str
    new_source: str


@dataclass
class RefactorContext:
    """Passed to refactor functions. Uses ChangeStack with an in-memory
    filesystem overlay so writes are visible to subsequent reads without
    touching disk until commit()."""

    project: Project
    args: Namespace
    dry_run: bool
    _stack: ChangeStack = field(init=False)
    _fs: OverlayFSCommands = field(init=False)
    _pending: list[PendingWrite] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._fs = OverlayFSCommands(self.project.fscommands)
        self.project.fscommands = self._fs  # type: ignore[assignment]
        self._stack = ChangeStack(self.project)

    def get_resource(self, file_path: Path) -> File:
        rel = str(file_path.resolve().relative_to(self.project.address))
        return self.project.get_resource(rel)

    def find_files(
        self,
        directory: Path,
        patterns: Iterable[str] = (),
        include: Iterable[str] = (),
        exclude: Iterable[str] = (),
    ) -> list[Path]:
        """Find .py files, optionally containing ``patterns``, filtered by globs.

        When ``patterns`` is non-empty, uses ripgrep (falling back to grep)
        to pre-filter to only files containing a match. The result is then
        intersected with include/exclude globs.

        When ``patterns`` is empty, returns all glob-matched files.
        """
        pattern_list = list(patterns)
        include_list = list(include)
        exclude_list = list(exclude)

        # Step 1: glob-based file set
        if include_list:
            allowed: set[Path] = set()
            for pattern in include_list:
                allowed.update(directory.glob(pattern))
        else:
            allowed = set(directory.rglob("*.py"))
        for pattern in exclude_list:
            allowed -= set(directory.glob(pattern))

        print(f"  glob: {len(allowed)} .py file(s) in {directory}")
        if include_list:
            print(f"    include: {include_list}")
        if exclude_list:
            print(f"    exclude: {exclude_list}")

        if not pattern_list:
            return sorted(allowed)

        # Step 2: text pre-filter with rg, falling back to grep
        candidates = self._grep_files(directory, pattern_list)
        result = sorted(candidates & allowed)
        excluded_by_grep = allowed - candidates
        print(
            f"  grep: {len(candidates)} file(s) contain {pattern_list}, "
            f"{len(excluded_by_grep)} excluded"
        )

        return result

    def _grep_files(self, directory: Path, patterns: list[str]) -> set[Path]:
        """Find .py files containing any pattern using rg, falling back to grep."""
        regex = "|".join(patterns)

        rg = shutil.which("rg")
        if rg:
            cmd = [rg, "-l", "--type=py", regex, str(directory)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"  search: rg {regex}")
            if result.returncode == 1:  # no matches
                return set()
            result.check_returncode()
            return {Path(line) for line in result.stdout.splitlines() if line}

        grep = shutil.which("grep")
        if grep:
            cmd = [grep, "-rlE", "--include=*.py", regex, str(directory)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"  search: grep -rlE {regex}")
            if result.returncode == 1:  # no matches
                return set()
            result.check_returncode()
            return {Path(line) for line in result.stdout.splitlines() if line}

        raise FileNotFoundError(
            "Neither rg (ripgrep) nor grep found on PATH. "
            "Install ripgrep or ensure grep is available."
        )

    def write(self, resource: File, new_source: str) -> None:
        """Queue a file write. The change is visible to subsequent reads
        via the in-memory overlay — nothing touches disk until commit()."""
        original = resource.read()
        if new_source != original:
            self._pending.append(PendingWrite(resource, original, new_source))
            change = ChangeSet(f"Change <{resource.path}>")
            change.add_change(ChangeContents(resource, new_source))
            self._stack.push(change)

    def do(self, changes: Change) -> None:
        """Apply a rope Change (e.g. from Rename, Move, Extract).
        Captures ChangeContents into _pending for diff/backup tracking,
        then pushes onto the ChangeStack so reads see the result."""
        for change in self._iter_changes(changes):
            if isinstance(change, ChangeContents):
                original = change.resource.read()
                self._pending.append(
                    PendingWrite(change.resource, original, change.new_contents)
                )
        self._stack.push(changes)

    def _iter_changes(self, changes: Change) -> list[Change]:
        """Flatten a Change tree into leaf changes."""
        if isinstance(changes, ChangeSet):
            result: list[Change] = []
            for child in changes.changes:
                result.extend(self._iter_changes(child))
            return result
        return [changes]

    def commit(self) -> None:
        """Flush all accumulated changes to disk."""
        self._fs.commit()


def _in_git_repo(cwd: Path) -> bool:
    """Check if cwd is inside a git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        cwd=cwd,
    )
    return result.returncode == 0


def _check_git_clean(cwd: Path) -> None:
    """Ensure all changes are staged or committed before refactoring."""
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    unstaged = result.stdout.strip()
    if unstaged:
        print("Error: unstaged changes detected. Stage or commit before refactoring.")
        print(unstaged)
        sys.exit(1)


def run(
    refactor_fn: RefactorFn,
    *,
    description: str = "",
    setup_args: SetupArgsFn | None = None,
) -> None:
    """Bootstrap entry point. Parses args, sets up rope, runs the refactor."""
    import argparse

    parser = argparse.ArgumentParser(description=description or "Rope refactor script")
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Rope project root (repository root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show unified diff of changes (implies --dry-run on first run)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create .bak files before writing (for use outside git repos)",
    )
    if setup_args:
        setup_args(parser)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    dry_run = args.dry_run or args.diff
    show_diff = args.diff

    # Safety check: ensure we can revert (skip in dry-run)
    if not dry_run:
        if _in_git_repo(project_root):
            _check_git_clean(project_root)
        elif not args.backup:
            print(
                "Error: not in a git repo. Use --backup to create .bak files, or --dry-run."
            )
            sys.exit(1)

    project = Project(str(project_root))
    ctx = RefactorContext(project=project, args=args, dry_run=dry_run)

    try:
        refactor_fn(ctx)
    except Exception:
        project.close()
        raise

    if not ctx._pending:
        print("No changes needed.")
        project.close()
        return

    if dry_run:
        print(
            f"{'[dry-run] ' if not show_diff else ''}Would modify {len(ctx._pending)} file(s):"
        )
        for pw in ctx._pending:
            if show_diff:
                _print_diff(pw)
            else:
                print(f"  {pw.resource.path}")
    else:
        if args.backup:
            for pw in ctx._pending:
                bak_path = Path(project_root) / (pw.resource.path + ".bak")
                bak_path.write_text(pw.original)
        ctx.commit()
        print(f"Updated {len(ctx._pending)} file(s):")
        for pw in ctx._pending:
            suffix = " (.bak created)" if args.backup else ""
            print(f"  {pw.resource.path}{suffix}")

    project.close()


def _print_diff(pw: PendingWrite) -> None:
    """Print a unified diff for a pending write."""
    import difflib

    path = pw.resource.path
    original_lines = pw.original.splitlines(keepends=True)
    new_lines = pw.new_source.splitlines(keepends=True)
    diff = difflib.unified_diff(original_lines, new_lines, f"a/{path}", f"b/{path}")
    sys.stdout.writelines(diff)
