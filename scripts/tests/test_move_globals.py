"""Integration tests for move_globals.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture

import move_globals
from rope_bootstrap import run


def test_apply(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)
    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            dest="myapp.utils",
            symbols=["DeviceStatus"],
            source_root=None,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "myapp/models.py").read_text() == dedent("""\
        from dataclasses import dataclass


        @dataclass
        class DeviceInfo:
            name: str
            address: str


    """)

    assert (project / "myapp/utils.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from dataclasses import dataclass


        @dataclass
        class DeviceStatus:
            online: bool
            battery: int


        def format_device(device: DeviceInfo) -> str:
            return f"{device.name} ({device.address})"
    """)
