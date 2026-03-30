"""Bootstrap for rope refactor scripts.

Handles project setup, dry-run mode, and diff output.
Every refactor script imports this and calls `run()` with a refactor function.

Usage in refactor scripts:

    from rope_bootstrap import run, RefactorContext
    from rope.refactor.rename import Rename

    def setup_args(parser):
        parser.add_argument("source", type=Path, help="Source file")

    def refactor(ctx: RefactorContext) -> None:
        resource = ctx.get_resource(ctx.args.source)
        pymodule = ctx.project.get_pymodule(resource)
        source = resource.read()
        line_start = pymodule.lines.get_line_start(line_number)
        offset = line_start + source[line_start:].index("symbol_name")
        changes = Rename(ctx.project, resource, offset).get_changes("new_name")
        ctx.do(changes)

    if __name__ == "__main__":
        run(refactor, description="My refactor script", setup_args=setup_args)
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rope.base.change import Change, ChangeContents, ChangeSet, MoveResource
from rope.base.project import Project
from rope.base.resources import File

# Prefix used to tag ChangeSet descriptions with a refactor run hash.
# Format: [refactor:<8-char-hex>] <original description>
REFACTOR_TAG_PREFIX = "[refactor:"


class SetupArgsFn(Protocol):
    """Callback to add script-specific arguments to the parser."""

    def __call__(self, parser: ArgumentParser) -> None: ...


class RefactorFn(Protocol):
    """Refactor callback. Use ctx.do() to apply changes — never call
    resource.write() directly, as that bypasses diff tracking and undo."""

    def __call__(self, ctx: RefactorContext) -> None: ...


@dataclass
class FileDiff:
    """A recorded content change for diff display."""

    path: str
    original: str | None  # None for new files
    new_source: str | None  # None for removals
    new_path: str | None = None  # set if file was moved/renamed
    step: int = 0  # which ctx.do() call produced this diff


@dataclass
class GitSnapshot:
    """Captures git working tree state for undo verification."""

    _tree: str | None
    _cwd: Path

    @classmethod
    def capture(cls, cwd: Path) -> GitSnapshot:
        """Snapshot current state: staged, unstaged, and untracked files."""
        tree = cls._capture_tree(cwd)
        return cls(_tree=tree, _cwd=cwd)

    @classmethod
    def unavailable(cls, cwd: Path) -> GitSnapshot:
        """Return a no-op snapshot when not in a git repo."""
        return cls(_tree=None, _cwd=cwd)

    @staticmethod
    def _capture_tree(cwd: Path) -> str | None:
        """Create a stash commit and return its tree hash (timestamp-independent)."""
        stash = subprocess.run(
            ["git", "stash", "create", "--include-untracked"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        commit_sha = stash.stdout.strip()
        if not commit_sha:
            return None
        tree = subprocess.run(
            ["git", "rev-parse", f"{commit_sha}^{{tree}}"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return tree.stdout.strip() or None

    def verify(self) -> list[str]:
        """Compare current state to snapshot. Returns difference descriptions.
        Empty list means undo was perfect."""
        if self._tree is None:
            # No git or clean tree at capture time — nothing to compare against
            return []

        current_tree = self._capture_tree(self._cwd)

        if self._tree == current_tree:
            return []

        if current_tree is None:
            # Tree is now clean but wasn't at capture — that's unexpected after undo
            return [f"Working tree is clean but snapshot tree {self._tree[:8]} existed"]

        result = subprocess.run(
            ["git", "diff", self._tree, current_tree, "--stat"],
            capture_output=True,
            text=True,
            cwd=self._cwd,
        )
        if result.stdout.strip():
            return result.stdout.strip().splitlines()
        return []


def _compute_state_hash(project_root: Path) -> str:
    """Compute a hash identifying the current codebase state.

    Combines git HEAD and git status to produce an 8-char hex prefix.
    This tags ChangeSets so undo/redo scripts can identify all changes
    from a single refactor run.

    Returns an empty string if not in a git repo.
    """
    git_root = _git_repo_root(project_root)
    if git_root is None:
        return ""

    h = hashlib.sha256()

    # Git HEAD (identifies the codebase version)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=git_root,
    )
    h.update(head.stdout.strip().encode())

    # Git status (identifies uncommitted state)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=git_root,
    )
    h.update(status.stdout.encode())

    return h.hexdigest()[:8]


@dataclass
class RefactorContext:
    """Passed to refactor functions. All changes are applied to disk
    immediately via project.do() and can be undone via undo_all()."""

    project: Project
    args: Namespace
    dry_run: bool
    _checkpoint: int = field(init=False)
    _diffs: list[FileDiff] = field(default_factory=list)
    _step: int = field(init=False, default=0)
    _state_hash: str = field(init=False, default="")
    _scaffolded_inits: list[Path] = field(default_factory=list)
    _scaffolded_modules: list[Path] = field(default_factory=list)
    _scaffolded_dirs: list[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._checkpoint = len(self.project.history.undo_list)
        project_root = Path(self.project.root.real_path)
        self._state_hash = _compute_state_hash(project_root)

    def get_resource(self, file_path: str | Path) -> File:
        path = Path(file_path)
        if path.is_absolute():
            rel = str(path.relative_to(self.project.address))
        else:
            rel = str(path)
        return self.project.get_resource(rel)

    def ensure_package(self, dest_dir: str) -> None:
        """Create directories and __init__.py files needed for rope import resolution.

        Creates scaffolding directly on the filesystem — not through rope's
        Change API — so it never enters rope's undo history. Call
        cleanup_scaffolding() to remove them after the refactor (or undo).

        Skips __init__.py creation for directories that rope recognises as
        source folders (both user-configured and auto-discovered), since adding
        __init__.py would turn them into packages and break import resolution
        (e.g. ``src/`` would produce ``src.myapp.x`` imports).
        """
        project_root = Path(self.project.root.real_path)
        source_folders = {sf.path for sf in self.project.get_source_folders()}
        parts = Path(dest_dir).parts

        for i in range(len(parts)):
            current = Path(*parts[: i + 1])
            full = project_root / current

            if not full.exists():
                full.mkdir()
                self._scaffolded_dirs.append(full)
                print(f"  Created directory: {current}")

            if str(current) in source_folders:
                continue

            init = full / "__init__.py"
            if not init.exists():
                init.touch()
                self._scaffolded_inits.append(init)
                print(f"  Created __init__.py: {current / '__init__.py'}")

        self.project.validate()

    def _resolve_source_root(
        self, dotted_name: str, source_root: Path | None
    ) -> Path | None:
        """Resolve the source folder for scaffolding a new module.

        1. If source_root is provided, use it directly.
        2. Try to find the top-level package via rope's find_module and
           determine which source folder contains it.
        3. If still unknown: use the sole source folder, or raise if ambiguous.
        """
        if source_root is not None:
            return source_root

        project_root = Path(self.project.root.real_path)
        parts = dotted_name.split(".")
        top_resource = self.project.find_module(parts[0])
        if top_resource is not None:
            for sf in self.project.get_source_folders():
                if sf.contains(top_resource):
                    return Path(sf.real_path).relative_to(project_root)

        source_folders = self.project.get_source_folders()
        if len(source_folders) == 1:
            return Path(source_folders[0].real_path).relative_to(project_root)

        if len(source_folders) > 1:
            names = [sf.path for sf in source_folders]
            raise ValueError(
                f"Multiple source folders {names} and top-level package "
                f"'{parts[0]}' not found in any. Pass source_root to ensure_module()."
            )

        raise ValueError(
            "No source folders found in the project. "
            "Pass source_root to ensure_module()."
        )

    def ensure_module(self, dotted_name: str, source_root: Path | None = None) -> Path:
        """Ensure a dotted module path exists on disk, creating packages and leaf file.

        Creates intermediate directories + __init__.py via ensure_package(),
        then creates the leaf .py file if needed. Everything is scaffolding.
        Returns the absolute path to the leaf module file.

        Args:
            source_root: Source folder relative to project root (e.g. Path("src")).
                If None, resolved automatically from rope's source folders.
        """
        dest_resource = self.project.find_module(dotted_name)
        if dest_resource is not None:
            return Path(self.project.root.real_path) / dest_resource.path

        project_root = Path(self.project.root.real_path)
        parts = dotted_name.split(".")
        base = self._resolve_source_root(dotted_name, source_root)

        if len(parts) > 1:
            pkg_parts = Path(*parts[:-1])
            pkg_dir = str(base / pkg_parts) if base else str(pkg_parts)
            self.ensure_package(pkg_dir)

        leaf_filename = parts[-1] + ".py"
        leaf_parts = (
            Path(*parts[:-1]) / leaf_filename if len(parts) > 1 else Path(leaf_filename)
        )
        leaf_path = (
            project_root / base / leaf_parts if base else project_root / leaf_parts
        )

        if not leaf_path.exists():
            leaf_path.touch()
            self._scaffolded_modules.append(leaf_path)
            self.project.validate()
            print(f"  Created module: {leaf_path.relative_to(project_root)}")

        return leaf_path

    def cleanup_scaffolding(self, *, keep_modules: bool = False) -> None:
        """Remove scaffolded files and empty directories.

        Always removes __init__.py files and empty directories.
        Only removes leaf module files when keep_modules is False — on
        real applies rope has written content into them.
        """
        if not keep_modules:
            for f in reversed(self._scaffolded_modules):
                if f.exists():
                    f.unlink()
        self._scaffolded_modules.clear()
        for f in reversed(self._scaffolded_inits):
            if f.exists():
                f.unlink()
        self._scaffolded_inits.clear()
        for d in reversed(self._scaffolded_dirs):
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
        self._scaffolded_dirs.clear()
        self.project.validate()

    def find_files(
        self,
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
        directory = Path(self.project.root.real_path)
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

    def do(self, changes: Change) -> None:
        """Apply a rope Change to disk and record diffs for display.

        Tags the change description with [refactor:<hash>] so undo/redo
        scripts can identify all changes from a single refactor run.
        """
        self._step += 1

        # Tag the change with our run hash
        if self._state_hash and hasattr(changes, "description"):
            tag = f"{REFACTOR_TAG_PREFIX}{self._state_hash}]"
            if not changes.description.startswith(REFACTOR_TAG_PREFIX):
                changes.description = f"{tag} {changes.description}"

        leaves = self._iter_changes(changes)

        # Collect moves and snapshot originals before applying
        moves: dict[str, str] = {}
        snapshots: dict[str, str] = {}
        for leaf in leaves:
            if isinstance(leaf, MoveResource):
                moves[leaf.resource.path] = leaf.new_resource.path
        for leaf in leaves:
            if isinstance(leaf, ChangeContents):
                try:
                    snapshots[leaf.resource.path] = leaf.resource.read()
                except (FileNotFoundError, AttributeError) as e:
                    print(f"  Warning: could not read {leaf.resource.path}: {e}")
                    snapshots[leaf.resource.path] = ""

        self.project.do(changes)

        # Record diffs
        for path, original in snapshots.items():
            actual_path = moves.get(path, path)
            resource = self.project.get_resource(actual_path)
            self._diffs.append(
                FileDiff(
                    path=path,
                    original=original,
                    new_source=resource.read(),
                    new_path=moves.get(path),
                    step=self._step,
                )
            )

    def undo_all(self, *, drop: bool = False, verbose: bool = False) -> None:
        """Undo all changes back to the checkpoint, then remove scaffolding.

        Args:
            drop: If True, undone changes are not kept in redo history.
                Use drop=True for failed refactors (partial garbage).
                Use drop=False for dry-run (valid changes, keep for redo).
            verbose: If True, print each changeset being undone.
        """
        to_undo = len(self.project.history.undo_list) - self._checkpoint
        if verbose:
            print(
                f"  Undo: {to_undo} change(s) to undo "
                f"(history={len(self.project.history.undo_list)}, "
                f"checkpoint={self._checkpoint})"
            )
        if to_undo <= 0:
            self.cleanup_scaffolding()
            return
        undone = 0
        while len(self.project.history.undo_list) > self._checkpoint:
            change = self.project.history.undo_list[-1]
            # Access description before undo — forces rope to resolve lazy state
            desc = getattr(change, "description", str(change))
            self.project.history.undo(drop=drop)
            undone += 1
            if verbose:
                print(f"  [{undone}/{to_undo}] Undone: {desc}")
        self.cleanup_scaffolding()

    def _iter_changes(self, changes: Change) -> list[Change]:
        """Flatten a Change tree into leaf changes."""
        if isinstance(changes, ChangeSet):
            result: list[Change] = []
            for child in changes.changes:
                result.extend(self._iter_changes(child))
            return result
        return [changes]


def extract_refactor_hash(description: str) -> str | None:
    """Extract the refactor hash from a tagged change description.

    Returns the 8-char hex hash, or None if the description is not tagged.
    """
    if description.startswith(REFACTOR_TAG_PREFIX):
        end = description.find("]", len(REFACTOR_TAG_PREFIX))
        if end == -1:
            return None
        return description[len(REFACTOR_TAG_PREFIX) : end]
    return None


def _git_repo_root(cwd: Path) -> Path | None:
    """Return the git repository root, or None if not in a repo."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return None


def resolve_project_root(project_root: Path | None) -> Path:
    """Resolve the project root, defaulting to the git repository root."""
    if project_root is not None:
        return project_root.resolve()
    detected = _git_repo_root(Path.cwd())
    if detected is None:
        print("Error: not in a git repo. Pass --project-root explicitly.")
        sys.exit(1)
    return detected


def _print_changes(
    diffs: list[FileDiff], show_diff: bool, *, applied: bool = False
) -> None:
    """Print change summary, grouping diffs by step when steps are non-trivial.

    Only shows step headers when there are multiple steps AND at least one
    step produced multiple diffs (i.e., a multi-file operation like MoveModule).
    Single-file-per-step patterns (like add_imports iterating files) stay flat.
    """
    total = len(diffs)
    max_step = max((d.step for d in diffs), default=0)
    # Show step grouping when steps are meaningful (not just one diff per step)
    group_steps = max_step > 1 and total > max_step

    if applied:
        print(f"Applied {total} change(s):")
    elif show_diff:
        print(f"Would apply {total} change(s):")
    else:
        print(f"[dry-run] Would apply {total} change(s):")

    prev_step = 0
    for diff in diffs:
        if group_steps and diff.step != prev_step:
            print(f"  Step {diff.step}:")
            prev_step = diff.step
        if show_diff and not applied:
            sys.stdout.write(_format_diff(diff))
        else:
            label = diff.path
            if diff.new_path:
                label = f"{diff.path} -> {diff.new_path}"
            indent = "    " if group_steps else "  "
            print(f"{indent}{label}")


def _verify_snapshot(snapshot: GitSnapshot, context: str) -> None:
    """Warn if undo didn't fully restore the original state."""
    diffs = snapshot.verify()
    if diffs:
        print(f"ERROR: {context} — files differ from pre-refactor state:")
        for line in diffs:
            print(f"  {line}")
        print(
            "This is a bug. Run `git diff` to inspect and `git checkout .` to recover."
        )


def build_parser(
    description: str = "",
    setup_args: SetupArgsFn | None = None,
) -> ArgumentParser:
    """Build the argument parser for a refactor script."""
    parser = ArgumentParser(description=description or "Rope refactor script")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Rope project root (default: git repository root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show unified diff of changes (implies --dry-run)",
    )
    if setup_args:
        setup_args(parser)
    return parser


def run(
    refactor_fn: RefactorFn,
    *,
    description: str = "",
    setup_args: SetupArgsFn | None = None,
    args: Namespace | None = None,
) -> None:
    """Bootstrap entry point. Parses args, sets up rope, runs the refactor."""
    if args is None:
        args = build_parser(description, setup_args).parse_args()

    project_root = resolve_project_root(args.project_root)
    dry_run = args.dry_run or args.diff
    show_diff = args.diff

    project = Project(str(project_root))
    project.prefs.set(
        "max_history_items", 10_000
    )  # ensure dry-run can undo all changes
    ctx = RefactorContext(project=project, args=args, dry_run=dry_run)

    if ctx._state_hash:
        print(f"Refactor run {ctx._state_hash}")

    # Snapshot git state for undo verification (use repo root, not project root)
    git_root = _git_repo_root(project_root)
    if git_root is not None:
        snapshot = GitSnapshot.capture(git_root)
    else:
        snapshot = GitSnapshot.unavailable(project_root)

    try:
        refactor_fn(ctx)
    except Exception:
        ctx.undo_all(drop=True, verbose=True)
        _verify_snapshot(snapshot, "after failed refactor undo")
        project.close()
        raise

    if not ctx._diffs:
        print("No changes needed.")
    elif dry_run:
        _print_changes(ctx._diffs, show_diff)
        ctx.undo_all(verbose=True)
        _verify_snapshot(snapshot, "after dry-run undo")
        print()
        print("To apply, re-run without --diff/--dry-run.")
    else:
        ctx.cleanup_scaffolding(keep_modules=True)
        _print_changes(ctx._diffs, show_diff=False, applied=True)

    project.close()


# ANSI color codes for diff output (respect NO_COLOR convention)
if os.environ.get("NO_COLOR") is not None:
    _RED = _GREEN = _CYAN = _BOLD = _DIM = _RESET = ""
else:
    _RED = "\033[31m"
    _GREEN = "\033[32m"
    _CYAN = "\033[36m"
    _BOLD = "\033[1m"
    _DIM = "\033[2m"
    _RESET = "\033[0m"


def _format_diff(diff: FileDiff) -> str:
    """Return a unified diff string with line numbers and ANSI colors."""
    import difflib
    import re

    old_path = diff.path
    new_path = diff.new_path or old_path
    original = diff.original or ""
    new_source = diff.new_source or ""
    original_lines = original.splitlines(keepends=True)
    new_lines = new_source.splitlines(keepends=True)
    raw = difflib.unified_diff(
        original_lines, new_lines, f"a/{old_path}", f"b/{new_path}"
    )

    out: list[str] = []
    old_ln = new_ln = 0
    # Determine width needed for line numbers
    max_ln = max(len(original_lines), len(new_lines))
    w = max(len(str(max_ln)), 1)
    for line in raw:
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)", line)
            if m:
                old_ln = int(m.group(1))
            m2 = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            if m2:
                new_ln = int(m2.group(1))
            out.append(f"{_CYAN}{line}{_RESET}")
        elif line.startswith("---"):
            out.append(f"{_BOLD}{line}{_RESET}")
        elif line.startswith("+++"):
            out.append(f"{_BOLD}{line}{_RESET}")
        elif line.startswith("-"):
            out.append(f"{_DIM}{old_ln:>{w}}\u2192 {_RESET}{_RED}{line}{_RESET}")
            old_ln += 1
        elif line.startswith("+"):
            out.append(f"{_DIM}{new_ln:>{w}}\u2192 {_RESET}{_GREEN}{line}{_RESET}")
            new_ln += 1
        else:
            out.append(f"{_DIM}{old_ln:>{w}}\u2192 {_RESET}{line}")
            old_ln += 1
            new_ln += 1
    return "".join(out)
