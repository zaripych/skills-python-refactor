"""Integration tests for add_imports.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import instantiate_project_from_fixture

from add_imports import add_import, _uses_pytest
from rope.refactor.importutils.importinfo import NormalImport
from rope_bootstrap import run

PYTEST_IMPORT = NormalImport((("pytest", None),))


def test_adds_import_where_needed(tmp_path: Path) -> None:
    project = instantiate_project_from_fixture("fixture-add-imports", tmp_path)

    # Verify files that should change don't have the import yet
    assert "import pytest" not in (project / "test_needs_import.py").read_text()
    assert "import pytest" not in (project / "test_mark.py").read_text()

    run(
        add_import(PYTEST_IMPORT, _uses_pytest),
        args=Namespace(
            project_root=project,
            diff=False,
        ),
    )

    # Files that use pytest without importing it get the import added
    assert (project / "test_needs_import.py").read_text() == dedent("""\
        import pytest
        def test_foo():
            pytest.raises(ValueError)
    """)

    assert (project / "test_mark.py").read_text() == dedent("""\
        import pytest
        @pytest.mark.slow
        def test_foo():
            pass
    """)

    # File that already imports pytest is unchanged
    assert (project / "test_already_imported.py").read_text() == dedent("""\
        import pytest


        def test_foo():
            pytest.raises(ValueError)
    """)

    # Files that don't use pytest are unchanged
    assert (project / "test_no_usage.py").read_text() == dedent("""\
        def test_foo():
            pass
    """)

    assert (project / "test_other_attr.py").read_text() == dedent("""\
        def test_foo():
            os.path.exists("x")
    """)
