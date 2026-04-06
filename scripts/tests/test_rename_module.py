"""Integration tests for rename_module.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture, read_directory_structure_sorted

import rename_module
from rope_bootstrap import run


def test_rename_file_module(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # Before state
    assert read_directory_structure_sorted(project) == [
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

    assert (project / "myapp/utils.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo


        def format_device(device: DeviceInfo) -> str:
            return f"{device.name} ({device.address})"
    """)

    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)

    run(
        rename_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/utils.py",
            new_name="formatting",
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/formatting.py",
        "myapp/handlers/__init__.py",
        "myapp/handlers/status.py",
        "myapp/models.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    assert (project / "myapp/formatting.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo


        def format_device(device: DeviceInfo) -> str:
            return f"{device.name} ({device.address})"
    """)

    # Callers should use the new module name
    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.formatting import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)


def test_rename_package(tmp_path: Path) -> None:
    """Rename a package directory — all imports across the project should be rewritten."""
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # Before state
    assert read_directory_structure_sorted(project) == [
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

    assert (project / "myapp/handlers/__init__.py").read_text() == dedent("""\
        from .status import handle_status

        __all__ = ["handle_status"]
    """)

    assert (project / "myapp/handlers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)

    run(
        rename_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers",
            new_name="controllers",
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/controllers/__init__.py",
        "myapp/controllers/status.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    # Relative imports within the package are preserved as-is
    assert (project / "myapp/controllers/__init__.py").read_text() == dedent("""\
        from .status import handle_status

        __all__ = ["handle_status"]
    """)

    # Submodule content unchanged (its internal imports don't reference the package name)
    assert (project / "myapp/controllers/status.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)
