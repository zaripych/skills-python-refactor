"""Integration tests for refactor_history.py (undo/redo)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from conftest import instantiate_project_from_fixture, snapshot_state

import move_globals
import move_module
import refactor_history
from rope_bootstrap import run


# -- undo / redo --


def test_undo_after_move_globals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    before = snapshot_state(project)

    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            dest="myapp.utils",
            symbols=["DeviceStatus"],
            source_root=None,
            diff=False,
        ),
    )

    refactor_history.main(
        Namespace(action="undo", project_root=project, hash=None, list=False)
    )
    assert "Undone" in capsys.readouterr().out
    assert before == snapshot_state(project)


def test_redo_after_undo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            dest="myapp.utils",
            symbols=["DeviceStatus"],
            source_root=None,
            diff=False,
        ),
    )
    applied = snapshot_state(project)

    refactor_history.main(
        Namespace(action="undo", project_root=project, hash=None, list=False)
    )
    refactor_history.main(
        Namespace(action="redo", project_root=project, hash=None, list=False)
    )
    assert "Redone" in capsys.readouterr().out
    assert applied == snapshot_state(project)


def test_undo_after_move_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    before = snapshot_state(project)

    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename="handler",
            diff=False,
        ),
    )

    refactor_history.main(
        Namespace(action="undo", project_root=project, hash=None, list=False)
    )
    assert "Undone" in capsys.readouterr().out
    assert before == snapshot_state(project)


def test_list_then_undo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    before = snapshot_state(project)

    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            dest="myapp.utils",
            symbols=["DeviceStatus"],
            source_root=None,
            diff=False,
        ),
    )
    capsys.readouterr()  # clear output from refactor

    # List should show the refactor run
    refactor_history.main(Namespace(action="list", project_root=project, hash=None))
    list_output = capsys.readouterr().out
    assert "changeset(s)" in list_output

    # Undo should restore original state
    refactor_history.main(Namespace(action="undo", project_root=project, hash=None))
    assert "Undone" in capsys.readouterr().out
    assert before == snapshot_state(project)


# -- argument parsing --


def test_parse_undo() -> None:
    args = refactor_history.build_parser().parse_args(["undo"])
    assert args.action == "undo"
    assert args.project_root is None
    assert args.hash is None


def test_parse_redo_with_hash() -> None:
    args = refactor_history.build_parser().parse_args(
        ["redo", "--hash", "abc12345", "--project-root", "/tmp/proj"]
    )
    assert args.action == "redo"
    assert args.hash == "abc12345"
    assert args.project_root == Path("/tmp/proj")


def test_parse_list() -> None:
    args = refactor_history.build_parser().parse_args(["list"])
    assert args.action == "list"
