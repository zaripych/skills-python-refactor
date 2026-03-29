"""Tests for bootstrap cross-cutting concerns (dry-run, arg parsing)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from conftest import instantiate_project_from_fixture, snapshot_state

import move_globals
import move_module
from rope_bootstrap import build_parser, run


# -- dry-run preserves state --


def test_move_module_dry_run_preserves_state(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    before = snapshot_state(project)
    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename=None,
            dry_run=False,
            diff=True,
        ),
    )
    assert before == snapshot_state(project)


def test_move_module_with_rename_dry_run_preserves_state(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    before = snapshot_state(project)
    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename="handler",
            dry_run=False,
            diff=True,
        ),
    )
    assert before == snapshot_state(project)


def test_move_globals_dry_run_preserves_state(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    before = snapshot_state(project)
    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            dest="myapp.utils",
            symbols=["DeviceStatus"],
            dry_run=False,
            diff=True,
        ),
    )
    assert before == snapshot_state(project)


# -- argument parsing --


def test_parse_base_args_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.project_root is None
    assert args.dry_run is False
    assert args.diff is False


def test_parse_base_args_all_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["--project-root", "/tmp/proj", "--dry-run", "--diff"])
    assert args.project_root == Path("/tmp/proj")
    assert args.dry_run is True
    assert args.diff is True


def test_parse_move_module_args() -> None:
    parser = build_parser(setup_args=move_module.setup_args)
    args = parser.parse_args(["src/foo.py", "dest/bar", "--rename", "baz"])
    assert args.source == Path("src/foo.py")
    assert args.dest_dir == "dest/bar"
    assert args.rename == "baz"


def test_parse_move_module_args_no_rename() -> None:
    parser = build_parser(setup_args=move_module.setup_args)
    args = parser.parse_args(["src/foo.py", "dest/bar"])
    assert args.source == Path("src/foo.py")
    assert args.dest_dir == "dest/bar"
    assert args.rename is None


def test_parse_move_globals_args() -> None:
    parser = build_parser(setup_args=move_globals.setup_args)
    args = parser.parse_args(["src/models.py", "pkg.utils", "Foo", "Bar"])
    assert args.source == Path("src/models.py")
    assert args.dest == "pkg.utils"
    assert args.symbols == ["Foo", "Bar"]
