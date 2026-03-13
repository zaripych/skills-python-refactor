from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

from rope.refactor.importutils.importinfo import NormalImport

from conftest import create_project, get_diffs
from add_imports import add_import


def _uses_pytest(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "pytest"
        for node in ast.walk(tree)
    )


PYTEST_IMPORT = NormalImport((("pytest", None),))


def test_adds_import_pytest(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo():
            pytest.raises(ValueError)
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_import(PYTEST_IMPORT, _uses_pytest)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+import pytest" in diffs[0]
    proj.close()


def test_skips_when_already_imported(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        import pytest


        def test_foo():
            pytest.raises(ValueError)
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_import(PYTEST_IMPORT, _uses_pytest)
    refactor(ctx)

    assert len(ctx._pending) == 0
    proj.close()


def test_skips_when_no_pytest_usage(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo():
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_import(PYTEST_IMPORT, _uses_pytest)
    refactor(ctx)

    assert len(ctx._pending) == 0
    proj.close()


def test_detects_pytest_mark(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        @pytest.mark.slow
        def test_foo():
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_import(PYTEST_IMPORT, _uses_pytest)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+import pytest" in diffs[0]
    proj.close()


def test_processes_multiple_files(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_a.py",
        dedent("""\
        def test_a():
            pytest.raises(ValueError)
    """),
    )
    proj.create_file(
        "test_b.py",
        dedent("""\
        @pytest.mark.slow
        def test_b():
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_import(PYTEST_IMPORT, _uses_pytest)
    refactor(ctx)

    assert len(ctx._pending) == 2
    proj.close()


def test_skips_non_pytest_attribute(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo():
            os.path.exists("x")
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_import(PYTEST_IMPORT, _uses_pytest)
    refactor(ctx)

    assert len(ctx._pending) == 0
    proj.close()
