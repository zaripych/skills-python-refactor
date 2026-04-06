"""Integration tests for move_module.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

import pytest
from conftest import instantiate_project_from_fixture, read_directory_structure_sorted

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
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/status.py",
        "myapp/handlers/__init__.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

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
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/handler.py",
        "myapp/handlers/__init__.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

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


def test_move_package_without_init_files(tmp_path: Path) -> None:
    """Move a package whose parent directories lack __init__.py.

    ensure_packages must scaffold __init__.py for the package itself (so
    MoveModule accepts it) and for all imported packages (so rope's modname
    resolves full dotted paths).
    """
    project = instantiate_project_from_fixture("fixture-without-init-files", tmp_path)

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "pyproject.toml",
        "todoapp/__init__.py",
        "todoapp/api/__init__.py",
        "todoapp/api/routes.py",
        "todoapp/models.py",
        "todoapp/services/tasks/crud.py",
        "todoapp/services/tasks/validation.py",
        "uv.lock",
    ]

    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/services/tasks",
            dest_dir="todoapp/api",
            rename=None,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "pyproject.toml",
        "todoapp/__init__.py",
        "todoapp/api/__init__.py",
        "todoapp/api/routes.py",
        "todoapp/api/tasks/__init__.py",
        "todoapp/api/tasks/crud.py",
        "todoapp/api/tasks/validation.py",
        "todoapp/models.py",
        "uv.lock",
    ]

    assert (project / "todoapp/api/tasks/crud.py").read_text() == dedent("""\
        from todoapp.models import Task


        def create_task(title: str) -> Task:
            return Task(title=title, done=False)
    """)

    assert (project / "todoapp/api/tasks/validation.py").read_text() == dedent("""\
        from todoapp.models import Task


        def validate_task(task: Task) -> bool:
            return bool(task.title)
    """)

    assert (project / "todoapp/api/routes.py").read_text() == dedent("""\
        from todoapp.models import Task
        from todoapp.api.tasks.crud import create_task
        from todoapp.api.tasks.validation import validate_task


        def handle_create(title: str) -> Task:
            task = create_task(title)
            validate_task(task)
            return task
    """)


def test_move_untracked_file(tmp_path: Path) -> None:
    """Move a module that exists on disk but is not tracked by git.

    Rope's GITCommands.move() uses ``git mv`` which fails for untracked
    files.  The bootstrap must ``git add`` untracked sources before applying
    so the move succeeds.
    """
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # Create a new module after the initial commit — it's untracked.
    # Also add an import of it so we can verify import rewriting.
    diagnostics = project / "myapp/diagnostics.py"
    diagnostics.write_text(
        dedent("""\
        from myapp.models import DeviceStatus


        def check_battery(status: DeviceStatus) -> bool:
            return status.battery > 20
    """)
    )

    utils = project / "myapp/utils.py"
    utils.write_text(
        dedent("""\
        from myapp.models import DeviceInfo
        from myapp.diagnostics import check_battery


        def format_device(device: DeviceInfo) -> str:
            return f"{device.name} ({device.address})"
    """)
    )

    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=diagnostics,
            dest_dir="myapp/features",
            rename=None,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/diagnostics.py",
        "myapp/handlers/__init__.py",
        "myapp/handlers/status.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    assert (project / "myapp/features/diagnostics.py").read_text() == dedent("""\
        from myapp.models import DeviceStatus


        def check_battery(status: DeviceStatus) -> bool:
            return status.battery > 20
    """)

    assert (project / "myapp/utils.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.features.diagnostics import check_battery


        def format_device(device: DeviceInfo) -> str:
            return f"{device.name} ({device.address})"
    """)


def test_destination_collision_without_rename_aborts(tmp_path: Path) -> None:
    """Moving to a directory that already has a file with the same name must abort."""
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # Create a conflicting file at the destination
    features = project / "myapp/features"
    features.mkdir(parents=True, exist_ok=True)
    (features / "__init__.py").touch()
    (features / "status.py").write_text("# existing production module\n")

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/__init__.py",
        "myapp/features/status.py",
        "myapp/handlers/__init__.py",
        "myapp/handlers/status.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    with pytest.raises(ValueError, match="Destination already exists"):
        run(
            move_module.refactor,
            args=Namespace(
                project_root=project,
                source=project / "myapp/handlers/status.py",
                dest_dir="myapp/features",
                rename=None,
                diff=False,
            ),
        )

    # Original files must be untouched
    assert (features / "status.py").read_text() == "# existing production module\n"
    assert (project / "myapp/handlers/status.py").exists()


def test_destination_collision_with_rename_succeeds(tmp_path: Path) -> None:
    """When --rename is given and destination has a name collision, rename first then move."""
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # Create a conflicting file at the destination
    features = project / "myapp/features"
    features.mkdir(parents=True, exist_ok=True)
    (features / "__init__.py").touch()
    (features / "status.py").write_text(
        dedent("""\
        # existing production module
        def existing_handler() -> str:
            return "ok"
    """)
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/__init__.py",
        "myapp/features/status.py",
        "myapp/handlers/__init__.py",
        "myapp/handlers/status.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    run(
        move_module.refactor,
        args=Namespace(
            project_root=project,
            source=project / "myapp/handlers/status.py",
            dest_dir="myapp/features",
            rename="status_handler",
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/__init__.py",
        "myapp/features/status.py",
        "myapp/features/status_handler.py",
        "myapp/handlers/__init__.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    # Original destination file must be preserved
    assert (features / "status.py").read_text() == dedent("""\
        # existing production module
        def existing_handler() -> str:
            return "ok"
    """)

    # Moved+renamed file must exist with correct content
    assert (features / "status_handler.py").read_text() == dedent("""\
        from myapp.models import DeviceInfo
        from myapp.utils import format_device


        def handle_status(device: DeviceInfo) -> str:
            return format_device(device)
    """)

    # Imports must be rewritten to the new name
    assert (project / "myapp/handlers/__init__.py").read_text() == dedent("""\
        from myapp.features.status_handler import handle_status

        __all__ = ["handle_status"]
    """)


def test_destination_collision_rename_collides_in_source_aborts(tmp_path: Path) -> None:
    """If rename-before-move would collide in the source directory, abort."""
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # Create conflicting file at destination (triggers rename_before_move)
    features = project / "myapp/features"
    features.mkdir(parents=True, exist_ok=True)
    (features / "__init__.py").touch()
    (features / "status.py").write_text("# existing\n")

    # Create file in source dir with the --rename name
    (project / "myapp/handlers/handler.py").write_text("# blocks rename\n")

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/__init__.py",
        "myapp/features/status.py",
        "myapp/handlers/__init__.py",
        "myapp/handlers/handler.py",
        "myapp/handlers/status.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    with pytest.raises(ValueError, match="Cannot rename before move"):
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


def test_renamed_destination_already_exists_aborts(tmp_path: Path) -> None:
    """If dest_dir/{rename}.py already exists, abort even when source.name doesn't collide."""
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

    # No collision on source.name, but the --rename target exists at destination
    features = project / "myapp/features"
    features.mkdir(parents=True, exist_ok=True)
    (features / "__init__.py").touch()
    (features / "status_handler.py").write_text("# existing module\n")

    assert read_directory_structure_sorted(project) == [
        ".gitignore",
        "myapp/__init__.py",
        "myapp/features/__init__.py",
        "myapp/features/status_handler.py",
        "myapp/handlers/__init__.py",
        "myapp/handlers/status.py",
        "myapp/models.py",
        "myapp/utils.py",
        "pyproject.toml",
        "tests/__init__.py",
        "tests/test_models.py",
        "uv.lock",
    ]

    with pytest.raises(ValueError, match="Destination already exists.*status_handler"):
        run(
            move_module.refactor,
            args=Namespace(
                project_root=project,
                source=project / "myapp/handlers/status.py",
                dest_dir="myapp/features",
                rename="status_handler",
                diff=False,
            ),
        )

    # Both files must be untouched
    assert (features / "status_handler.py").read_text() == "# existing module\n"
    assert (project / "myapp/handlers/status.py").exists()
