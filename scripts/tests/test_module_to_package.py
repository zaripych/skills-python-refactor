"""Integration tests for module_to_package.py."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture, read_directory_structure_sorted

import module_to_package
from rope_bootstrap import run


BEFORE_FILES = [
    ".gitignore",
    "myapp/__init__.py",
    "myapp/handlers/__init__.py",
    "myapp/handlers/status.py",
    "myapp/models.py",
    "pyproject.toml",
    "tests/__init__.py",
    "tests/test_models.py",
    "uv.lock",
]

AFTER_FILES = [
    ".gitignore",
    "myapp/__init__.py",
    "myapp/handlers/__init__.py",
    "myapp/handlers/status.py",
    "myapp/models/info.py",
    "myapp/models/status.py",
    "pyproject.toml",
    "tests/__init__.py",
    "tests/test_models.py",
    "uv.lock",
]

MAPPING = json.dumps({"DeviceInfo": "info", "DeviceStatus": "status"})


def test_apply(tmp_path: Path) -> None:
    """Convert models.py to a package, moving DeviceInfo and DeviceStatus to submodules.

    DeviceInfo references DeviceType (unspecified in mapping), so DeviceType
    should be auto-assigned to the same submodule as DeviceInfo.
    """
    project = instantiate_project_from_fixture("fixture-to-package", tmp_path)

    # -- before state --
    assert read_directory_structure_sorted(project) == BEFORE_FILES

    assert (project / "myapp/models.py").read_text() == dedent("""\
        from dataclasses import dataclass
        from enum import Enum


        class DeviceType(Enum):
            SENSOR = "sensor"
            ACTUATOR = "actuator"


        @dataclass
        class DeviceInfo:
            name: str
            address: str
            device_type: DeviceType


        @dataclass
        class DeviceStatus:
            online: bool
            battery: int
    """)

    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo, DeviceStatus


        def handle_status(device: DeviceInfo) -> DeviceStatus:
            return DeviceStatus(online=True, battery=100)
    """)

    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo, DeviceType


        def test_device_info():
            device = DeviceInfo(
                name="sensor1", address="00:11:22", device_type=DeviceType.SENSOR
            )
            assert device.name == "sensor1"
    """)

    # -- apply refactor --
    run(
        module_to_package.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            mapping=MAPPING,
            source_root=None,
            diff=False,
        ),
    )

    # -- after state --
    assert read_directory_structure_sorted(project) == AFTER_FILES

    # DeviceInfo moved to info.py, DeviceType came along as a dependency
    assert (project / "myapp/models/info.py").read_text() == dedent("""\
        from dataclasses import dataclass
        from enum import Enum


        class DeviceType(Enum):
            SENSOR = "sensor"
            ACTUATOR = "actuator"


        @dataclass
        class DeviceInfo:
            name: str
            address: str
            device_type: DeviceType
    """)

    # DeviceStatus moved to status.py
    assert (project / "myapp/models/status.py").read_text() == dedent("""\
        from dataclasses import dataclass


        @dataclass
        class DeviceStatus:
            online: bool
            battery: int
    """)

    # Callers should have their imports rewritten
    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models.info import DeviceInfo
        from myapp.models.status import DeviceStatus


        def handle_status(device: DeviceInfo) -> DeviceStatus:
            return DeviceStatus(online=True, battery=100)
    """)

    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from myapp.models.info import DeviceInfo
        from myapp.models.info import DeviceType


        def test_device_info():
            device = DeviceInfo(
                name="sensor1", address="00:11:22", device_type=DeviceType.SENSOR
            )
            assert device.name == "sensor1"
    """)


def test_directory_contents_after_diff_then_apply(tmp_path: Path) -> None:
    """Running --diff then apply should succeed — diff must fully clean up."""
    project = instantiate_project_from_fixture("fixture-to-package", tmp_path)

    common_args = dict(
        project_root=project,
        source=project / "myapp/models.py",
        mapping=MAPPING,
        source_root=None,
    )

    # -- before state --
    assert read_directory_structure_sorted(project) == BEFORE_FILES

    # --diff run: should leave no artifacts
    run(
        module_to_package.refactor,
        args=Namespace(**common_args, diff=True),
    )

    # -- after diff: identical to before --
    assert read_directory_structure_sorted(project) == BEFORE_FILES

    # Real apply should succeed (no leftover directory blocking ModuleToPackage)
    run(
        module_to_package.refactor,
        args=Namespace(**common_args, diff=False),
    )

    # -- after apply --
    assert read_directory_structure_sorted(project) == AFTER_FILES


def test_directory_contents_with_leftover_empty_directory(tmp_path: Path) -> None:
    """Apply succeeds even if the target package directory already exists (empty leftover)."""
    project = instantiate_project_from_fixture("fixture-to-package", tmp_path)

    # Simulate a leftover empty directory from a previous interrupted run
    (project / "myapp/models").mkdir()

    # -- before state (models.py coexists with empty models/) --
    assert read_directory_structure_sorted(project) == BEFORE_FILES

    run(
        module_to_package.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/models.py",
            mapping=MAPPING,
            source_root=None,
            diff=False,
        ),
    )

    # -- after state --
    assert read_directory_structure_sorted(project) == AFTER_FILES
