"""Tests for _format_diff — paths, line numbers, and alignment."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import create_project
from rope_bootstrap import PendingWrite, _format_diff


def test_shows_move_paths(tmp_path: Path) -> None:
    """_format_diff should show old path in a/ and new path in b/."""
    proj = create_project(tmp_path)
    proj.create_file("old.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "old.py")

    pw = PendingWrite(
        resource=resource,
        original="x = 1\n",
        new_source="x = 2\n",
        new_path="pkg/old.py",
    )
    diff = _format_diff(pw)

    assert "a/old.py" in diff
    assert "b/pkg/old.py" in diff
    proj.close()


def test_same_path_when_no_move(tmp_path: Path) -> None:
    """Without a move, both sides show the same path."""
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")

    pw = PendingWrite(
        resource=resource,
        original="x = 1\n",
        new_source="x = 2\n",
    )
    diff = _format_diff(pw)

    assert "a/foo.py" in diff
    assert "b/foo.py" in diff
    proj.close()


def _content_lines(diff: str) -> list[str]:
    """Strip header lines, return only numbered content lines."""
    return [l for l in diff.splitlines() if not l.startswith(("---", "+++", "@@"))]


def test_line_numbers_on_change(tmp_path: Path) -> None:
    """Removals show old line number, additions show new line number."""
    proj = create_project(tmp_path)
    proj.create_file(
        "nums.py",
        dedent("""\
            a = 1
            b = 2
            c = 3
        """),
    )

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "nums.py")

    pw = PendingWrite(
        resource=resource,
        original=dedent("""\
            a = 1
            b = 2
            c = 3
        """),
        new_source=dedent("""\
            a = 1
            b = 999
            c = 3
        """),
    )
    content = _content_lines(_format_diff(pw))

    assert content[0].startswith("1\u2192") and "a = 1" in content[0]
    assert content[1].startswith("2\u2192") and "-b = 2" in content[1]
    assert content[2].startswith("2\u2192") and "+b = 999" in content[2]
    assert content[3].startswith("3\u2192") and "c = 3" in content[3]
    proj.close()


def test_line_numbers_on_insertion(tmp_path: Path) -> None:
    """Inserted lines show new line number; surrounding context stays correct."""
    proj = create_project(tmp_path)
    proj.create_file(
        "ins.py",
        dedent("""\
            a = 1
            b = 2
        """),
    )

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "ins.py")

    pw = PendingWrite(
        resource=resource,
        original=dedent("""\
            a = 1
            b = 2
        """),
        new_source=dedent("""\
            a = 1
            new_line = 0
            b = 2
        """),
    )
    content = _content_lines(_format_diff(pw))

    assert content[0].startswith("1\u2192")
    assert content[1].startswith("2\u2192") and "+new_line = 0" in content[1]
    assert content[2].startswith("2\u2192")
    proj.close()


def test_line_numbers_new_file(tmp_path: Path) -> None:
    """A new file (empty original) shows new line numbers on every line."""
    proj = create_project(tmp_path)
    proj.create_file("new.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "new.py")

    pw = PendingWrite(
        resource=resource,
        original="",
        new_source=dedent("""\
            from pathlib import Path

            def hello():
                pass
        """),
    )
    content = _content_lines(_format_diff(pw))

    assert content[0].startswith("1\u2192") and "+from pathlib" in content[0]
    assert content[1].startswith("2\u2192")
    assert content[2].startswith("3\u2192") and "+def hello" in content[2]
    assert content[3].startswith("4\u2192") and "+    pass" in content[3]
    proj.close()


def test_line_numbers_multidigit_alignment(tmp_path: Path) -> None:
    """Multi-digit line numbers are right-aligned."""
    proj = create_project(tmp_path)
    original = "".join(f"line{i} = {i}\n" for i in range(1, 16))
    new = original.replace("line12 = 12\n", "line12 = 99\n")
    proj.create_file("wide.py", original)

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "wide.py")

    pw = PendingWrite(resource=resource, original=original, new_source=new)
    content = _content_lines(_format_diff(pw))

    removal = [l for l in content if "-line12 = 12" in l]
    assert len(removal) == 1
    assert removal[0].startswith("12\u2192")

    addition = [l for l in content if "+line12 = 99" in l]
    assert len(addition) == 1
    assert addition[0].startswith("12\u2192")
    proj.close()
