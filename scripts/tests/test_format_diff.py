"""Tests for _format_diff — paths, line numbers, and alignment."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, str(Path(__file__).parent.parent))

import re

from rope_bootstrap import FileDiff, _format_diff

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _content_lines(diff: str) -> list[str]:
    """Strip ANSI codes and header lines, return only numbered content lines."""
    plain = _strip_ansi(diff)
    return [ln for ln in plain.splitlines() if not ln.startswith(("---", "+++", "@@"))]


def test_shows_move_paths() -> None:
    """_format_diff should show old path in a/ and new path in b/."""
    fd = FileDiff(
        path="old.py",
        original="x = 1\n",
        new_source="x = 2\n",
        new_path="pkg/old.py",
    )
    diff = _format_diff(fd)

    assert "a/old.py" in diff
    assert "b/pkg/old.py" in diff


def test_same_path_when_no_move() -> None:
    """Without a move, both sides show the same path."""
    fd = FileDiff(
        path="foo.py",
        original="x = 1\n",
        new_source="x = 2\n",
    )
    diff = _format_diff(fd)

    assert "a/foo.py" in diff
    assert "b/foo.py" in diff


def test_line_numbers_on_change() -> None:
    """Removals show old line number, additions show new line number."""
    fd = FileDiff(
        path="nums.py",
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
    content = _content_lines(_format_diff(fd))

    assert content[0].startswith("1\u2192") and "a = 1" in content[0]
    assert content[1].startswith("2\u2192") and "-b = 2" in content[1]
    assert content[2].startswith("2\u2192") and "+b = 999" in content[2]
    assert content[3].startswith("3\u2192") and "c = 3" in content[3]


def test_line_numbers_on_insertion() -> None:
    """Inserted lines show new line number; surrounding context stays correct."""
    fd = FileDiff(
        path="ins.py",
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
    content = _content_lines(_format_diff(fd))

    assert content[0].startswith("1\u2192")
    assert content[1].startswith("2\u2192") and "+new_line = 0" in content[1]
    assert content[2].startswith("2\u2192")


def test_line_numbers_new_file() -> None:
    """A new file (empty original) shows new line numbers on every line."""
    fd = FileDiff(
        path="new.py",
        original="",
        new_source=dedent("""\
            from pathlib import Path

            def hello():
                pass
        """),
    )
    content = _content_lines(_format_diff(fd))

    assert content[0].startswith("1\u2192") and "+from pathlib" in content[0]
    assert content[1].startswith("2\u2192")
    assert content[2].startswith("3\u2192") and "+def hello" in content[2]
    assert content[3].startswith("4\u2192") and "+    pass" in content[3]


def test_line_numbers_multidigit_alignment() -> None:
    """Multi-digit line numbers are right-aligned."""
    original = "".join(f"line{i} = {i}\n" for i in range(1, 16))
    new = original.replace("line12 = 12\n", "line12 = 99\n")

    fd = FileDiff(path="wide.py", original=original, new_source=new)
    content = _content_lines(_format_diff(fd))

    removal = [ln for ln in content if "-line12 = 12" in ln]
    assert len(removal) == 1
    assert removal[0].startswith("12\u2192")

    addition = [ln for ln in content if "+line12 = 99" in ln]
    assert len(addition) == 1
    assert addition[0].startswith("12\u2192")
