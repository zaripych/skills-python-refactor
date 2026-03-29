"""Integration tests for move_module.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import (
    instantiate_project_from_fixture,
    read_directory_structure_sorted,
)

import move_module
from rope_bootstrap import run


def test_apply(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename=None,
            dry_run=False,
            diff=False,
        ),
    )

    structure = read_directory_structure_sorted(project)
    assert "myapp/features/status.py" in structure
    assert "myapp/handlers/status.py" not in structure
    assert "myapp/features/__init__.py" not in structure

    assert (project / "myapp/features/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)

    assert (project / "myapp/handlers/__init__.py").read_text() == dedent("""\
        from myapp.features.status import handle_status

        __all__ = ["handle_status"]
    """)


def test_apply_with_rename(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename="handler",
            dry_run=False,
            diff=False,
        ),
    )

    structure = read_directory_structure_sorted(project)
    assert "myapp/features/handler.py" in structure
    assert "myapp/handlers/status.py" not in structure
    assert "myapp/features/status.py" not in structure
    assert "myapp/features/__init__.py" not in structure

    assert (project / "myapp/features/handler.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)

    assert (project / "myapp/handlers/__init__.py").read_text() == dedent("""\
        from myapp.features.handler import handle_status

        __all__ = ["handle_status"]
    """)
