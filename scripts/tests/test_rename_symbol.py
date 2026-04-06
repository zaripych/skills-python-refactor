"""Integration tests for rename_symbol.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

import pytest

from conftest import instantiate_project_from_fixture

import rename_symbol
from rope_bootstrap import run


def test_rename_function(tmp_path: Path) -> None:
    """Rename a function — all call sites and imports should be rewritten."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    # Before: create_task exists
    assert "def create_task(" in (project / "todoapp/services/tasks.py").read_text()
    assert (
        "from todoapp.services.tasks import complete_task, create_task"
        in (project / "tests/test_tasks.py").read_text()
    )

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/services/tasks.py",
            line=4,
            old_name="create_task",
            new_name="add_task",
            diff=False,
        ),
    )

    assert (project / "todoapp/services/tasks.py").read_text() == dedent("""\
        from todoapp.models import MAX_TITLE_LENGTH, Priority, Task


        def add_task(title: str, priority: Priority = Priority.MEDIUM) -> Task:
            if len(title) > MAX_TITLE_LENGTH:
                raise ValueError(f"Title exceeds {MAX_TITLE_LENGTH} characters")
            return Task(title=title, priority=priority)


        def complete_task(task: Task) -> Task:
            return Task(title=task.title, priority=task.priority, done=True)


        def summarize(task: Task) -> str:
            return task.summarize()
    """)

    assert (project / "tests/test_tasks.py").read_text() == dedent("""\
        from todoapp.models import Priority, Task
        from todoapp.services.tasks import complete_task, add_task, summarize


        def test_create_task():
            task = add_task("Buy milk", Priority.LOW)
            assert task == Task(title="Buy milk", priority=Priority.LOW)


        def test_complete_task():
            task = add_task("Buy milk")
            done = complete_task(task)
            assert done.done is True


        def test_summarize():
            task = add_task("Buy milk", Priority.HIGH)
            assert summarize(task) == "[pending] Buy milk (high)"
    """)


def test_rename_class(tmp_path: Path) -> None:
    """Rename a dataclass — all type annotations and references should be rewritten."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            line=15,
            old_name="Task",
            new_name="TodoItem",
            diff=False,
        ),
    )

    assert (project / "todoapp/models.py").read_text() == dedent("""\
        from dataclasses import dataclass
        from enum import Enum


        class Priority(Enum):
            LOW = "low"
            MEDIUM = "medium"
            HIGH = "high"


        MAX_TITLE_LENGTH = 200


        @dataclass
        class TodoItem:
            title: str
            priority: Priority
            done: bool = False

            def summarize(self) -> str:
                status = "done" if self.done else "pending"
                return f"[{status}] {self.title} ({self.priority.value})"
    """)

    assert (project / "todoapp/services/tasks.py").read_text() == dedent("""\
        from todoapp.models import MAX_TITLE_LENGTH, Priority, TodoItem


        def create_task(title: str, priority: Priority = Priority.MEDIUM) -> TodoItem:
            if len(title) > MAX_TITLE_LENGTH:
                raise ValueError(f"Title exceeds {MAX_TITLE_LENGTH} characters")
            return TodoItem(title=title, priority=priority)


        def complete_task(task: TodoItem) -> TodoItem:
            return TodoItem(title=task.title, priority=task.priority, done=True)


        def summarize(task: TodoItem) -> str:
            return task.summarize()
    """)

    assert (project / "tests/test_tasks.py").read_text() == dedent("""\
        from todoapp.models import Priority, TodoItem
        from todoapp.services.tasks import complete_task, create_task, summarize


        def test_create_task():
            task = create_task("Buy milk", Priority.LOW)
            assert task == TodoItem(title="Buy milk", priority=Priority.LOW)


        def test_complete_task():
            task = create_task("Buy milk")
            done = complete_task(task)
            assert done.done is True


        def test_summarize():
            task = create_task("Buy milk", Priority.HIGH)
            assert summarize(task) == "[pending] Buy milk (high)"
    """)


def test_rename_constant(tmp_path: Path) -> None:
    """Rename a module-level constant — all references should be rewritten."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            line=11,
            old_name="MAX_TITLE_LENGTH",
            new_name="TITLE_LIMIT",
            diff=False,
        ),
    )

    assert "TITLE_LIMIT = 200" in (project / "todoapp/models.py").read_text()
    assert "MAX_TITLE_LENGTH" not in (project / "todoapp/models.py").read_text()

    tasks_content = (project / "todoapp/services/tasks.py").read_text()
    assert "TITLE_LIMIT" in tasks_content
    assert "MAX_TITLE_LENGTH" not in tasks_content


def test_rename_enum_class(tmp_path: Path) -> None:
    """Rename an enum class — all references and imports should be rewritten."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            line=5,
            old_name="Priority",
            new_name="Urgency",
            diff=False,
        ),
    )

    models_content = (project / "todoapp/models.py").read_text()
    assert "class Urgency(Enum):" in models_content
    assert "Priority" not in models_content

    tasks_content = (project / "todoapp/services/tasks.py").read_text()
    assert "Urgency" in tasks_content
    assert "Priority" not in tasks_content


def test_rename_enum_member(tmp_path: Path) -> None:
    """Rename an enum member — all qualified references should be rewritten."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            line=7,
            old_name="MEDIUM",
            new_name="NORMAL",
            diff=False,
        ),
    )

    models_content = (project / "todoapp/models.py").read_text()
    assert "NORMAL = " in models_content
    assert "MEDIUM" not in models_content

    tasks_content = (project / "todoapp/services/tasks.py").read_text()
    assert "Priority.NORMAL" in tasks_content
    assert "Priority.MEDIUM" not in tasks_content


def test_rename_symbol_not_found_on_line(tmp_path: Path) -> None:
    """Error when the symbol doesn't exist on the specified line."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    with pytest.raises(ValueError, match="not found on line"):
        run(
            rename_symbol.refactor,
            args=Namespace(
                project_root=project,
                source=project / "todoapp/models.py",
                line=1,
                old_name="Task",
                new_name="TodoItem",
                diff=False,
            ),
        )


def test_rename_diff_mode(tmp_path: Path) -> None:
    """Diff mode should not modify any files."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    before = (project / "todoapp/models.py").read_text()

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            line=15,
            old_name="Task",
            new_name="TodoItem",
            diff=True,
        ),
    )

    assert (project / "todoapp/models.py").read_text() == before


def test_rename_method(tmp_path: Path) -> None:
    """Rename a method on a class — call sites via self and external callers should be rewritten."""
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/models.py",
            line=20,
            old_name="summarize",
            new_name="describe",
            diff=False,
        ),
    )

    models_content = (project / "todoapp/models.py").read_text()
    assert "def describe(self) -> str:" in models_content
    assert "summarize" not in models_content

    # The module-level summarize function is not renamed, but the method
    # call task.summarize() is rewritten via annotation-aware type hinting
    tasks_content = (project / "todoapp/services/tasks.py").read_text()
    assert "def summarize(task: Task) -> str:" in tasks_content
    assert "task.describe()" in tasks_content


def test_rename_shadowed_symbol(tmp_path: Path) -> None:
    """Rename only the targeted symbol when another symbol shares the same name.

    services/tasks.py has a module-level `summarize` function, and
    models.py has a `Task.summarize` method. Renaming the module-level
    function should not touch the method.
    """
    project = instantiate_project_from_fixture("fixture-rename-symbol", tmp_path)

    run(
        rename_symbol.refactor,
        args=Namespace(
            project_root=project,
            source=project / "todoapp/services/tasks.py",
            line=14,
            old_name="summarize",
            new_name="get_summary",
            diff=False,
        ),
    )

    # The module-level function is renamed
    tasks_content = (project / "todoapp/services/tasks.py").read_text()
    assert "def get_summary(task: Task) -> str:" in tasks_content
    # But the method call inside it still uses the original method name
    assert "task.summarize()" in tasks_content

    # The method on Task is untouched
    models_content = (project / "todoapp/models.py").read_text()
    assert "def summarize(self) -> str:" in models_content

    # The test file import is updated
    tests_content = (project / "tests/test_tasks.py").read_text()
    assert "get_summary" in tests_content
    assert "from todoapp.services.tasks import" in tests_content
