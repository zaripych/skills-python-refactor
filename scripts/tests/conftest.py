"""Test harness for rope refactor scripts.

Provides helpers to create temporary rope projects and assert on generated patches.
"""

from __future__ import annotations

collect_ignore_glob = ["fixtures/**"]

import os
import shutil
import subprocess
import sys
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

# Make scripts importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from rope.base.project import Project
from rope_bootstrap import FileDiff, RefactorContext, _format_diff

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
_IGNORED_DIRS = {".venv", "__pycache__", ".ropeproject", ".git"}


@dataclass
class RopeTestProject:
    """A temporary rope project for testing refactor scripts."""

    root: Path
    project: Project

    def create_file(self, rel_path: str, content: str) -> Path:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def make_context(self, **extra_args: object) -> RefactorContext:
        args = Namespace(project_root=self.root, **extra_args)
        with patch("rope_bootstrap._compute_state_hash", return_value="test0000"):
            return RefactorContext(project=self.project, args=args, dry_run=False)

    def close(self) -> None:
        self.project.close()


def create_project(tmp_path: Path) -> RopeTestProject:
    """Create a temporary rope project rooted at tmp_path."""
    return RopeTestProject(root=tmp_path, project=Project(str(tmp_path)))


def get_diffs(ctx: RefactorContext) -> list[str]:
    """Return unified diffs for all recorded file diffs."""
    return [_format_diff(d) for d in ctx._diffs]


def read_directory_structure_sorted(root: Path) -> list[str]:
    """Return sorted list of relative file paths, excluding build artifacts."""
    files = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        if any(part in _IGNORED_DIRS for part in rel.parts):
            continue
        files.append(str(rel))
    return sorted(files)


def snapshot_state(root: Path) -> dict[str, str]:
    """Capture file paths and contents for before/after comparison."""
    return {
        rel: (root / rel).read_text() for rel in read_directory_structure_sorted(root)
    }


def instantiate_project_from_fixture(fixture_name: str, tmp_path: Path) -> Path:
    """Copy a fixture to tmp_path, init git, run uv sync, commit."""
    fixture_src = FIXTURES_DIR / fixture_name
    project = tmp_path / fixture_name
    shutil.copytree(fixture_src, project)

    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test.com",
    }
    subprocess.run(["git", "init"], cwd=project, capture_output=True, check=True)
    subprocess.run(["uv", "sync"], cwd=project, capture_output=True, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=project,
        capture_output=True,
        check=True,
        env=git_env,
    )
    return project
