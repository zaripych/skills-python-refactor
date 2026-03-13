from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from conftest import create_project


def test_no_patterns_returns_all_py_files(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "x = 1\n")
    proj.create_file("b.py", "y = 2\n")
    proj.create_file("c.txt", "not python\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path)

    assert len(files) == 2
    assert all(f.suffix == ".py" for f in files)
    proj.close()


def test_no_patterns_respects_include(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("test_foo.py", "x = 1\n")
    proj.create_file("helper.py", "y = 2\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path, include=["test_*.py"])

    assert len(files) == 1
    assert files[0].name == "test_foo.py"
    proj.close()


def test_no_patterns_respects_exclude(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "x = 1\n")
    proj.create_file("b.py", "y = 2\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path, exclude=["b.py"])

    assert len(files) == 1
    assert files[0].name == "a.py"
    proj.close()


def test_patterns_filter_by_content(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("has_it.py", "capsys = 1\n")
    proj.create_file("no_match.py", "x = 1\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path, patterns=["capsys"])

    assert len(files) == 1
    assert files[0].name == "has_it.py"
    proj.close()


def test_patterns_intersected_with_globs(tmp_path: Path) -> None:
    """Grep matches are excluded if they don't pass include/exclude globs."""
    proj = create_project(tmp_path)
    proj.create_file("test_foo.py", "capsys here\n")
    proj.create_file("helper.py", "capsys here too\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path, patterns=["capsys"], include=["test_*.py"])

    assert len(files) == 1
    assert files[0].name == "test_foo.py"
    proj.close()


def test_patterns_excluded_by_glob(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "capsys here\n")
    proj.create_file("b.py", "capsys here\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path, patterns=["capsys"], exclude=["b.py"])

    assert len(files) == 1
    assert files[0].name == "a.py"
    proj.close()


def test_patterns_no_matches_returns_empty(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "x = 1\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path, patterns=["nonexistent_symbol"])

    assert files == []
    proj.close()


def test_returns_sorted(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("c.py", "x\n")
    proj.create_file("a.py", "x\n")
    proj.create_file("b.py", "x\n")

    ctx = proj.make_context()
    files = ctx.find_files(tmp_path)

    assert files == sorted(files)
    proj.close()


def test_grep_falls_back_to_grep_when_rg_missing(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "capsys = 1\n")
    proj.create_file("b.py", "x = 1\n")

    ctx = proj.make_context()

    original_which = shutil.which

    def no_rg(cmd: str) -> str | None:
        if cmd == "rg":
            return None
        return original_which(cmd)

    with patch("rope_bootstrap.shutil.which", side_effect=no_rg):
        files = ctx.find_files(tmp_path, patterns=["capsys"])

    assert len(files) == 1
    assert files[0].name == "a.py"
    proj.close()


def test_grep_raises_when_neither_rg_nor_grep(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "capsys = 1\n")

    ctx = proj.make_context()

    with patch("rope_bootstrap.shutil.which", return_value=None):
        try:
            ctx.find_files(tmp_path, patterns=["capsys"])
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError as e:
            assert "rg" in str(e)
            assert "grep" in str(e)

    proj.close()


def test_prints_search_info(tmp_path: Path, capsys: object) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "capsys = 1\n")
    proj.create_file("b.py", "x = 1\n")

    ctx = proj.make_context()
    ctx.find_files(tmp_path, patterns=["capsys"])

    captured = capsys.readouterr()  # type: ignore[union-attr]
    assert "glob:" in captured.out
    assert "grep:" in captured.out
    assert "search:" in captured.out
    proj.close()


def test_no_patterns_prints_glob_only(tmp_path: Path, capsys: object) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "x = 1\n")

    ctx = proj.make_context()
    ctx.find_files(tmp_path)

    captured = capsys.readouterr()  # type: ignore[union-attr]
    assert "glob:" in captured.out
    assert "grep:" not in captured.out
    proj.close()
