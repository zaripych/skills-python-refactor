"""Integration tests for add_param_annotations.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture, read_directory_structure_sorted

from add_param_annotations import add_param_annotations
from rope.refactor.importutils.importinfo import FromImport, NormalImport
from rope_bootstrap import run

FIXTURE_STRUCTURE = [
    "helper.py",
    "pyproject.toml",
    "test_already_annotated.py",
    "test_async.py",
    "test_both.py",
    "test_builtin.py",
    "test_capsys.py",
    "test_exclude_me.py",
    "test_existing_import.py",
    "test_nested.py",
    "test_non_matching.py",
    "test_tmp_path.py",
    "uv.lock",
]


def test_annotates_capsys(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_capsys.py").read_text() == dedent("""\
        def test_foo(capsys):
            pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_capsys.py").read_text() == dedent("""\
        import pytest
        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_annotates_tmp_path(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_tmp_path.py").read_text() == dedent("""\
        def test_foo(tmp_path):
            pass
    """)

    run(
        add_param_annotations(
            {"tmp_path": "Path"},
            {"tmp_path": FromImport("pathlib", 0, (("Path", None),))},
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_tmp_path.py").read_text() == dedent("""\
        from pathlib import Path
        def test_foo(tmp_path: Path):
            pass
    """)


def test_annotates_both_params(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_both.py").read_text() == dedent("""\
        def test_foo(capsys, tmp_path):
            pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]", "tmp_path": "Path"},
            {
                "capsys": NormalImport((("pytest", None),)),
                "tmp_path": FromImport("pathlib", 0, (("Path", None),)),
            },
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_both.py").read_text() == dedent("""\
        import pytest
        from pathlib import Path
        def test_foo(capsys: pytest.CaptureFixture[str], tmp_path: Path):
            pass
    """)


def test_skips_already_annotated(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_already_annotated.py").read_text() == dedent("""\
        import pytest


        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_already_annotated.py").read_text() == dedent("""\
        import pytest


        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_skips_non_matching_params(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_non_matching.py").read_text() == dedent("""\
        def test_foo(x: int):
            pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]", "tmp_path": "Path"},
            {
                "capsys": NormalImport((("pytest", None),)),
                "tmp_path": FromImport("pathlib", 0, (("Path", None),)),
            },
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_non_matching.py").read_text() == dedent("""\
        def test_foo(x: int):
            pass
    """)


def test_handles_nested_functions(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_nested.py").read_text() == dedent("""\
        def test_outer(capsys):
            def inner(tmp_path):
                pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]", "tmp_path": "Path"},
            {
                "capsys": NormalImport((("pytest", None),)),
                "tmp_path": FromImport("pathlib", 0, (("Path", None),)),
            },
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_nested.py").read_text() == dedent("""\
        import pytest
        from pathlib import Path
        def test_outer(capsys: pytest.CaptureFixture[str]):
            def inner(tmp_path: Path):
                pass
    """)


def test_handles_async_functions(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_async.py").read_text() == dedent("""\
        async def test_foo(tmp_path):
            pass
    """)

    run(
        add_param_annotations(
            {"tmp_path": "Path"},
            {"tmp_path": FromImport("pathlib", 0, (("Path", None),))},
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_async.py").read_text() == dedent("""\
        from pathlib import Path
        async def test_foo(tmp_path: Path):
            pass
    """)


def test_exclude_glob(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_capsys.py").read_text() == dedent("""\
        def test_foo(capsys):
            pass
    """)
    assert (project / "test_exclude_me.py").read_text() == dedent("""\
        def test_bar(capsys):
            pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
            exclude=["test_exclude_me.py"],
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_exclude_me.py").read_text() == dedent("""\
        def test_bar(capsys):
            pass
    """)
    assert (project / "test_capsys.py").read_text() == dedent("""\
        import pytest
        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_include_glob(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_capsys.py").read_text() == dedent("""\
        def test_foo(capsys):
            pass
    """)
    assert (project / "helper.py").read_text() == dedent("""\
        def setup(capsys):
            pass
    """)

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
            include=["test_*.py"],
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "helper.py").read_text() == dedent("""\
        def setup(capsys):
            pass
    """)
    assert (project / "test_capsys.py").read_text() == dedent("""\
        import pytest
        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_builtin_annotation_no_import(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_builtin.py").read_text() == dedent("""\
        def test_foo(name):
            pass
    """)

    run(
        add_param_annotations({"name": "str"}),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_builtin.py").read_text() == dedent("""\
        def test_foo(name: str):
            pass
    """)


def test_merges_with_existing_from_import(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_existing_import.py").read_text() == dedent("""\
        from pathlib import PurePath


        def test_foo(tmp_path):
            pass
    """)

    run(
        add_param_annotations(
            {"tmp_path": "Path"},
            {"tmp_path": FromImport("pathlib", 0, (("Path", None),))},
        ),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE
    assert (project / "test_existing_import.py").read_text() == dedent("""\
        from pathlib import PurePath
        from pathlib import Path


        def test_foo(tmp_path: Path):
            pass
    """)
