"""Tests for bootstrap cross-cutting concerns (dry-run, arg parsing)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import (
    instantiate_project_from_fixture,
    read_directory_structure_sorted,
    snapshot_state,
)

import move_globals
import move_module
from rope_bootstrap import build_parser, run

FIXTURE_MOVE_STRUCTURE = [
    ".gitignore",
    "myapp/__init__.py",
    "myapp/handlers/__init__.py",
    "myapp/handlers/status.py",
    "myapp/models.py",
    "myapp/utils.py",
    "pyproject.toml",
    "tests/__init__.py",
    "tests/test_models.py",
    "uv.lock",
]


# -- dry-run preserves state --


def test_move_module_dry_run_preserves_state(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_MOVE_STRUCTURE

    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)
    assert (project / "myapp/handlers/__init__.py").read_text() == dedent("""\
        from .status import handle_status

        __all__ = ["handle_status"]
    """)

    before = snapshot_state(project)
    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename=None,
            diff=True,
        ),
    )
    assert snapshot_state(project) == before
    assert read_directory_structure_sorted(project) == FIXTURE_MOVE_STRUCTURE


def test_move_module_with_rename_dry_run_preserves_state(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_MOVE_STRUCTURE

    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)

    before = snapshot_state(project)
    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename="handler",
            diff=True,
        ),
    )
    assert snapshot_state(project) == before
    assert read_directory_structure_sorted(project) == FIXTURE_MOVE_STRUCTURE


def test_move_globals_dry_run_preserves_state(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_MOVE_STRUCTURE

    assert (project / "myapp/models.py").read_text() == dedent("""\
        from dataclasses import dataclass


        @dataclass
        class DeviceInfo:
            name: str
            address: str


        @dataclass
        class DeviceStatus:
            online: bool
            battery: int
    """)
    assert (project / "myapp/utils.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo


        def format_device(device: DeviceInfo) -> str:
            return f"{device.name} ({device.address})"
    """)

    before = snapshot_state(project)
    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            dest="myapp.utils",
            symbols=["DeviceStatus"],
            source_root=None,
            diff=True,
        ),
    )
    assert snapshot_state(project) == before
    assert read_directory_structure_sorted(project) == FIXTURE_MOVE_STRUCTURE


# -- argument parsing --


def test_parse_base_args_defaults() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert vars(args) == {"project_root": None, "diff": False}


def test_parse_base_args_all_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["--project-root", "/tmp/proj", "--diff"])
    assert vars(args) == {"project_root": Path("/tmp/proj"), "diff": True}


def test_parse_move_module_args() -> None:
    parser = build_parser(setup_args=move_module.setup_args)
    args = parser.parse_args(["src/foo.py", "dest/bar", "--rename", "baz"])
    assert vars(args) == {
        "project_root": None,
        "diff": False,
        "source": Path("src/foo.py"),
        "dest_dir": "dest/bar",
        "rename": "baz",
    }


def test_parse_move_module_args_no_rename() -> None:
    parser = build_parser(setup_args=move_module.setup_args)
    args = parser.parse_args(["src/foo.py", "dest/bar"])
    assert vars(args) == {
        "project_root": None,
        "diff": False,
        "source": Path("src/foo.py"),
        "dest_dir": "dest/bar",
        "rename": None,
    }


def test_parse_move_globals_args() -> None:
    parser = build_parser(setup_args=move_globals.setup_args)
    args = parser.parse_args(["src/models.py", "pkg.utils", "Foo", "Bar"])
    assert vars(args) == {
        "project_root": None,
        "diff": False,
        "source": Path("src/models.py"),
        "dest": "pkg.utils",
        "symbols": ["Foo", "Bar"],
        "source_root": None,
    }
