"""Test refactoring in idiomatic Python layout (src/ + tests/)."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture, snapshot_state

import move_globals
import move_module
from rope_bootstrap import run


def _assert_no_src_prefix(project: Path) -> None:
    """Assert no file contains src-prefixed imports."""
    for path in project.rglob("*.py"):
        content = path.read_text()
        rel = path.relative_to(project)
        assert "src.myapp" not in content, f"{rel} contains src-prefixed import"


def test_move_global_in_idiomatic_layout(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-idiomatic-layout", tmp_path)

    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "src/myapp/models.py",
            symbols=["DeviceInfo"],
            dest="myapp.handlers.status",
            source_root=None,
            dry_run=False,
            diff=False,
        ),
    )

    _assert_no_src_prefix(project)

    # tests/test_models.py should be updated to import from the new location
    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from myapp.handlers.status import DeviceInfo
        def test_device_info():
            d = DeviceInfo(name="a", address="b")
            assert d.name == "a"
    """)

    # Source module should be empty after moving the only symbol
    assert (project / "src/myapp/models.py").read_text() == ""

    # Destination should contain the moved symbol
    status = (project / "src/myapp/handlers/status.py").read_text()
    assert "class DeviceInfo:" in status
    assert "def handle_status(device: DeviceInfo)" in status


def test_move_global_to_new_module_scaffolds_under_src(tmp_path: Path) -> None:
    """Moving to a brand-new module should scaffold under src/, not project root."""
    project = instantiate_project_from_fixture("fixture-idiomatic-layout", tmp_path)

    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "src/myapp/models.py",
            symbols=["DeviceInfo"],
            dest="myapp.features.new_mod",
            source_root=None,
            dry_run=False,
            diff=False,
        ),
    )

    _assert_no_src_prefix(project)

    # New module must be under src/, not at project root
    assert (project / "src/myapp/features/new_mod.py").exists()
    assert not (project / "myapp").exists(), (
        "scaffolded at project root instead of src/"
    )

    # Destination should contain the moved symbol
    new_mod = (project / "src/myapp/features/new_mod.py").read_text()
    assert "class DeviceInfo:" in new_mod


def test_move_module_in_idiomatic_layout(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-idiomatic-layout", tmp_path)

    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "src/myapp/handlers/status.py",
            dest_dir="src/myapp/features",
            rename="handler",
            dry_run=False,
            diff=False,
        ),
    )

    _assert_no_src_prefix(project)

    assert (project / "src/myapp/features/handler.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo


        def handle_status(device: DeviceInfo) -> str:
            return device.name
    """)

    assert (project / "src/myapp/handlers/__init__.py").read_text() == dedent("""\
        from myapp.features.handler import handle_status

        __all__ = ["handle_status"]
    """)


def test_move_module_dry_run_in_idiomatic_layout(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-idiomatic-layout", tmp_path)
    before = snapshot_state(project)

    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "src/myapp/handlers/status.py",
            dest_dir="src/myapp/features",
            rename="handler",
            dry_run=False,
            diff=True,
        ),
    )

    assert before == snapshot_state(project)
