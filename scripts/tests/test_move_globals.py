"""Integration tests for move_globals.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture, read_directory_structure_sorted

import move_globals
from rope_bootstrap import run


def test_apply(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-move", tmp_path)

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


def test_move_to_existing_module_without_init_files(tmp_path: Path) -> None:
    """Move a symbol to an existing module whose parent packages lack __init__.py.

    Without ensure_package on existing destinations, rope generates broken bare
    imports like ``from crud import create_task`` instead of fully qualified ones.
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

    assert (project / "todoapp/models.py").read_text() == dedent("""\
        from dataclasses import dataclass


        @dataclass
        class Task:
            title: str
            done: bool


        @dataclass
        class Priority:
            level: int
            label: str
    """)

    assert (project / "todoapp/services/tasks/crud.py").read_text() == dedent("""\
        from todoapp.models import Task


        def create_task(title: str) -> Task:
            return Task(title=title, done=False)
    """)

    assert (project / "todoapp/api/routes.py").read_text() == dedent("""\
        from todoapp.models import Task
        from todoapp.services.tasks.crud import create_task
        from todoapp.services.tasks.validation import validate_task


        def handle_create(title: str) -> Task:
            task = create_task(title)
            validate_task(task)
            return task
    """)

    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            dest="todoapp.services.tasks.crud",
            symbols=["Priority"],
            source_root=None,
            diff=False,
        ),
    )

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

    assert (project / "todoapp/models.py").read_text() == dedent("""\
        from dataclasses import dataclass


        @dataclass
        class Task:
            title: str
            done: bool


    """)

    assert (project / "todoapp/services/tasks/crud.py").read_text() == dedent("""\
        from todoapp.models import Task
        from dataclasses import dataclass


        @dataclass
        class Priority:
            level: int
            label: str


        def create_task(title: str) -> Task:
            return Task(title=title, done=False)
    """)

    assert (project / "todoapp/api/routes.py").read_text() == dedent("""\
        from todoapp.models import Task
        from todoapp.services.tasks.crud import create_task
        from todoapp.services.tasks.validation import validate_task


        def handle_create(title: str) -> Task:
            task = create_task(title)
            validate_task(task)
            return task
    """)


def test_move_from_source_without_init_files(tmp_path: Path) -> None:
    """Move a symbol from a module whose parent packages lack __init__.py.

    Without ensure_package on the source's parents, rope's modname() can't
    walk the full dotted path and generates bare imports like
    ``from crud import create_task`` in the destination.
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

    assert (project / "todoapp/services/tasks/crud.py").read_text() == dedent("""\
        from todoapp.models import Task


        def create_task(title: str) -> Task:
            return Task(title=title, done=False)
    """)

    assert (project / "todoapp/api/routes.py").read_text() == dedent("""\
        from todoapp.models import Task
        from todoapp.services.tasks.crud import create_task
        from todoapp.services.tasks.validation import validate_task


        def handle_create(title: str) -> Task:
            task = create_task(title)
            validate_task(task)
            return task
    """)

    run(
        move_globals.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/services/tasks/crud.py",
            dest="todoapp.api.routes",
            symbols=["create_task"],
            source_root=None,
            diff=False,
        ),
    )

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

    assert (project / "todoapp/services/tasks/crud.py").read_text() == ""

    assert (project / "todoapp/api/routes.py").read_text() == dedent("""\
        from todoapp.models import Task
        from todoapp.services.tasks.validation import validate_task


        def create_task(title: str) -> Task:
            return Task(title=title, done=False)


        def handle_create(title: str) -> Task:
            task = create_task(title)
            validate_task(task)
            return task
    """)
