"""Integration tests for add_param_annotations.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture

from add_param_annotations import add_param_annotations
from rope.refactor.importutils.importinfo import FromImport, NormalImport
from rope_bootstrap import run


def test_annotates_capsys(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "import pytest" not in (project / "test_capsys.py").read_text()

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_capsys.py").read_text() == dedent("""\
        import pytest
        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_annotates_tmp_path(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "from pathlib import Path" not in (project / "test_tmp_path.py").read_text()

    run(
        add_param_annotations(
            {"tmp_path": "Path"},
            {"tmp_path": FromImport("pathlib", 0, (("Path", None),))},
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_tmp_path.py").read_text() == dedent("""\
        from pathlib import Path
        def test_foo(tmp_path: Path):
            pass
    """)


def test_annotates_both_params(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "import pytest" not in (project / "test_both.py").read_text()

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
            dry_run=False,
            diff=False,
        ),
    )

    content = (project / "test_both.py").read_text()
    assert "import pytest" in content
    assert "from pathlib import Path" in content
    assert (
        "def test_foo(capsys: pytest.CaptureFixture[str], tmp_path: Path):" in content
    )


def test_skips_already_annotated(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_already_annotated.py").read_text() == dedent("""\
        import pytest


        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_skips_non_matching_params(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    before = (project / "test_non_matching.py").read_text()
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
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_non_matching.py").read_text() == before


def test_handles_nested_functions(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "import pytest" not in (project / "test_nested.py").read_text()

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
            dry_run=False,
            diff=False,
        ),
    )

    content = (project / "test_nested.py").read_text()
    assert "import pytest" in content
    assert "from pathlib import Path" in content
    assert "def test_outer(capsys: pytest.CaptureFixture[str]):" in content
    assert "    def inner(tmp_path: Path):" in content


def test_handles_async_functions(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "from pathlib import Path" not in (project / "test_async.py").read_text()

    run(
        add_param_annotations(
            {"tmp_path": "Path"},
            {"tmp_path": FromImport("pathlib", 0, (("Path", None),))},
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_async.py").read_text() == dedent("""\
        from pathlib import Path
        async def test_foo(tmp_path: Path):
            pass
    """)


def test_exclude_glob(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "import pytest" not in (project / "test_capsys.py").read_text()
    before_excluded = (project / "test_exclude_me.py").read_text()

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
            exclude=["test_exclude_me.py"],
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_exclude_me.py").read_text() == before_excluded
    assert (project / "test_capsys.py").read_text() == dedent("""\
        import pytest
        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_include_glob(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "import pytest" not in (project / "test_capsys.py").read_text()
    before_helper = (project / "helper.py").read_text()

    run(
        add_param_annotations(
            {"capsys": "pytest.CaptureFixture[str]"},
            {"capsys": NormalImport((("pytest", None),))},
            include=["test_*.py"],
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "helper.py").read_text() == before_helper
    assert (project / "test_capsys.py").read_text() == dedent("""\
        import pytest
        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """)


def test_builtin_annotation_no_import(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    assert "name: str" not in (project / "test_builtin.py").read_text()

    run(
        add_param_annotations({"name": "str"}),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    assert (project / "test_builtin.py").read_text() == dedent("""\
        def test_foo(name: str):
            pass
    """)


def test_merges_with_existing_from_import(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-annotations", tmp_path)
    content = (project / "test_existing_import.py").read_text()
    assert "PurePath" in content
    assert "tmp_path: Path" not in content

    run(
        add_param_annotations(
            {"tmp_path": "Path"},
            {"tmp_path": FromImport("pathlib", 0, (("Path", None),))},
        ),
        args=Namespace(
            project_root=project,
            dry_run=False,
            diff=False,
        ),
    )

    content = (project / "test_existing_import.py").read_text()
    assert "def test_foo(tmp_path: Path):" in content
    assert "from pathlib import Path, PurePath" in content or (
        "from pathlib import PurePath, Path" in content
    )
