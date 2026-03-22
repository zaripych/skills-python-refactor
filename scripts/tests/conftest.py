"""Test harness for rope refactor scripts.

Provides helpers to create temporary rope projects and assert on generated patches.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path

# Make scripts importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from rope.base.project import Project
from rope_bootstrap import RefactorContext, _format_diff


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
        return RefactorContext(project=self.project, args=args, dry_run=False)

    def close(self) -> None:
        self.project.close()


def create_project(tmp_path: Path) -> RopeTestProject:
    """Create a temporary rope project rooted at tmp_path."""
    return RopeTestProject(root=tmp_path, project=Project(str(tmp_path)))


def get_diffs(ctx: RefactorContext) -> list[str]:
    """Return unified diffs for all pending writes."""
    return [_format_diff(pw) for pw in ctx._pending]
