from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rope.refactor.importutils.importinfo import FromImport, NormalImport

from add_param_annotations import add_param_annotations
from conftest import create_project, get_diffs

CAPSYS_ANNOTATIONS = {"capsys": "pytest.CaptureFixture[str]"}
CAPSYS_IMPORTS: dict[str, NormalImport | FromImport] = {
    "capsys": NormalImport((("pytest", None),)),
}

TMP_PATH_ANNOTATIONS = {"tmp_path": "Path"}
TMP_PATH_IMPORTS: dict[str, NormalImport | FromImport] = {
    "tmp_path": FromImport("pathlib", 0, (("Path", None),)),
}

ALL_ANNOTATIONS = {**CAPSYS_ANNOTATIONS, **TMP_PATH_ANNOTATIONS}
ALL_IMPORTS = {**CAPSYS_IMPORTS, **TMP_PATH_IMPORTS}


def test_annotates_capsys(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(capsys):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(CAPSYS_ANNOTATIONS, CAPSYS_IMPORTS)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+import pytest" in diffs[0]
    assert "-def test_foo(capsys):" in diffs[0]
    assert "+def test_foo(capsys: pytest.CaptureFixture[str]):" in diffs[0]
    proj.close()


def test_annotates_tmp_path(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(tmp_path):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(TMP_PATH_ANNOTATIONS, TMP_PATH_IMPORTS)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+from pathlib import Path" in diffs[0]
    assert "-def test_foo(tmp_path):" in diffs[0]
    assert "+def test_foo(tmp_path: Path):" in diffs[0]
    proj.close()


def test_annotates_both_params(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(capsys, tmp_path):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(ALL_ANNOTATIONS, ALL_IMPORTS)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+import pytest" in diffs[0]
    assert "+from pathlib import Path" in diffs[0]
    assert (
        "+def test_foo(capsys: pytest.CaptureFixture[str], tmp_path: Path):" in diffs[0]
    )
    proj.close()


def test_skips_already_annotated(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        import pytest


        def test_foo(capsys: pytest.CaptureFixture[str]):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(CAPSYS_ANNOTATIONS, CAPSYS_IMPORTS)
    refactor(ctx)

    assert len(ctx._pending) == 0
    proj.close()


def test_skips_non_matching_params(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(x: int):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(ALL_ANNOTATIONS, ALL_IMPORTS)
    refactor(ctx)

    assert len(ctx._pending) == 0
    proj.close()


def test_handles_nested_functions(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_outer(capsys):
            def inner(tmp_path):
                pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(ALL_ANNOTATIONS, ALL_IMPORTS)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+def test_outer(capsys: pytest.CaptureFixture[str]):" in diffs[0]
    assert "+    def inner(tmp_path: Path):" in diffs[0]
    proj.close()


def test_handles_async_functions(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        async def test_foo(tmp_path):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(TMP_PATH_ANNOTATIONS, TMP_PATH_IMPORTS)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+async def test_foo(tmp_path: Path):" in diffs[0]
    proj.close()


def test_processes_multiple_files(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_a.py",
        dedent("""\
        def test_a(capsys):
            pass
    """),
    )
    proj.create_file(
        "test_b.py",
        dedent("""\
        def test_b(tmp_path):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(ALL_ANNOTATIONS, ALL_IMPORTS)
    refactor(ctx)

    assert len(ctx._pending) == 2
    proj.close()


def test_exclude_glob(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(capsys):
            pass
    """),
    )
    proj.create_file(
        "test_bar.py",
        dedent("""\
        def test_bar(capsys):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(
        CAPSYS_ANNOTATIONS, CAPSYS_IMPORTS, exclude=["test_bar.py"]
    )
    refactor(ctx)

    assert len(ctx._pending) == 1
    assert ctx._pending[0].resource.path == "test_foo.py"
    proj.close()


def test_include_glob(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(capsys):
            pass
    """),
    )
    proj.create_file(
        "helper.py",
        dedent("""\
        def setup(capsys):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(
        CAPSYS_ANNOTATIONS, CAPSYS_IMPORTS, include=["test_*.py"]
    )
    refactor(ctx)

    assert len(ctx._pending) == 1
    assert ctx._pending[0].resource.path == "test_foo.py"
    proj.close()


def test_no_imports_needed(tmp_path: Path) -> None:
    """Annotations that use builtins (str, int) don't need imports."""
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        def test_foo(name):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations({"name": "str"})
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "+def test_foo(name: str):" in diffs[0]
    proj.close()


def test_merges_with_existing_from_import(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "test_foo.py",
        dedent("""\
        from pathlib import PurePath


        def test_foo(tmp_path):
            pass
    """),
    )

    ctx = proj.make_context(directory=tmp_path)
    refactor = add_param_annotations(TMP_PATH_ANNOTATIONS, TMP_PATH_IMPORTS)
    refactor(ctx)

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "Path" in diffs[0]
    assert "+def test_foo(tmp_path: Path):" in diffs[0]
    proj.close()
