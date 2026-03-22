"""Tests for move/rename support in RefactorContext.do()."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, str(Path(__file__).parent.parent))

from rope.refactor.move import MoveModule
from rope.refactor.rename import Rename

from conftest import create_project, get_diffs
from rope_bootstrap import PendingOp, PendingWrite


def test_move_module_tracks_ops(tmp_path: Path) -> None:
    """Moving a module via ctx.do() records non-content changes in _ops."""
    proj = create_project(tmp_path)
    proj.create_file("src.py", "x = 1\n")
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "src.py")
    dest = ctx.project.get_resource("pkg")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)

    assert len(ctx._ops) >= 1
    descriptions = [op.description for op in ctx._ops]
    assert any("src" in d.lower() or "move" in d.lower() for d in descriptions)
    proj.close()


def test_move_module_sets_new_path(tmp_path: Path) -> None:
    """Content changes from a move should have new_path set."""
    proj = create_project(tmp_path)
    proj.create_file(
        "mod.py",
        dedent("""\
        def func():
            pass
    """),
    )
    proj.create_file(
        "caller.py",
        dedent("""\
        import mod
        mod.func()
    """),
    )
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "mod.py")
    dest = ctx.project.get_resource("pkg")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)

    # The caller should be updated (import path changes)
    caller_writes = [pw for pw in ctx._pending if pw.resource.path == "caller.py"]
    assert len(caller_writes) == 1
    assert "pkg" in caller_writes[0].new_source

    # The moved module's content change should have new_path set
    mod_writes = [pw for pw in ctx._pending if pw.resource.path == "mod.py"]
    if mod_writes:
        assert mod_writes[0].new_path is not None
        assert "pkg" in mod_writes[0].new_path
    proj.close()


def test_move_does_not_touch_disk(tmp_path: Path) -> None:
    """ctx.do() with a move should not modify files on disk."""
    proj = create_project(tmp_path)
    file_path = proj.create_file("src.py", "x = 1\n")
    proj.create_file("pkg/__init__.py", "")
    mtime_before = os.stat(file_path).st_mtime_ns

    ctx = proj.make_context()
    resource = ctx.get_resource(file_path)
    dest = ctx.project.get_resource("pkg")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)

    assert os.stat(file_path).st_mtime_ns == mtime_before
    assert file_path.read_text() == "x = 1\n"
    proj.close()


def test_do_rename_has_no_ops(tmp_path: Path) -> None:
    """A plain Rename produces ChangeContents only — no _ops."""
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "my_var = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")
    changes = Rename(ctx.project, resource, 0).get_changes("new_var")
    ctx.do(changes)

    assert len(ctx._ops) == 0
    assert len(ctx._pending) == 1
    proj.close()


def test_ops_and_pending_empty_initially(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    ctx = proj.make_context()

    assert ctx._ops == []
    assert ctx._pending == []
    proj.close()


def test_commit_with_move_writes_and_removes(tmp_path: Path) -> None:
    """After do() + commit(), the moved file exists at the new location."""
    proj = create_project(tmp_path)
    proj.create_file("src.py", "x = 1\n")
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "src.py")
    dest = ctx.project.get_resource("pkg")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)
    ctx.commit()

    assert (tmp_path / "pkg" / "src.py").exists()
    proj.close()


def test_write_then_move_preserves_edits(tmp_path: Path) -> None:
    """ctx.write() edits a file, then ctx.do() moves it.
    The moved file should contain the edited content."""
    proj = create_project(tmp_path)
    proj.create_file(
        "mod.py",
        dedent("""\
        x = 1
    """),
    )
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "mod.py")

    # First: manual edit via write()
    ctx.write(resource, "x = 2\n")

    # Then: move the module
    # Re-fetch resource to see updated content
    resource = ctx.get_resource(tmp_path / "mod.py")
    dest = ctx.project.get_resource("pkg")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)
    ctx.commit()

    assert (tmp_path / "pkg" / "mod.py").exists()
    assert "x = 2" in (tmp_path / "pkg" / "mod.py").read_text()
    proj.close()


def test_rename_then_move(tmp_path: Path) -> None:
    """Rename a symbol, then move the module. Both changes accumulate."""
    proj = create_project(tmp_path)
    proj.create_file(
        "mod.py",
        dedent("""\
        old_name = 1
    """),
    )
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "mod.py")

    # Rename
    rename_changes = Rename(ctx.project, resource, 0).get_changes("new_name")
    ctx.do(rename_changes)
    assert len(ctx._pending) == 1
    assert len(ctx._ops) == 0

    # Move
    resource = ctx.get_resource(tmp_path / "mod.py")
    dest = ctx.project.get_resource("pkg")
    move_changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(move_changes)

    assert len(ctx._ops) >= 1
    # Both rename and move content changes are tracked
    assert len(ctx._pending) >= 1
    proj.close()


def test_sequential_do_calls_accumulate(tmp_path: Path) -> None:
    """Multiple do() calls accumulate _pending and _ops, not overwrite."""
    proj = create_project(tmp_path)
    proj.create_file("a.py", "x = 1\n")
    proj.create_file("b.py", "y = 1\n")

    ctx = proj.make_context()

    res_a = ctx.get_resource(tmp_path / "a.py")
    changes_a = Rename(ctx.project, res_a, 0).get_changes("x2")
    ctx.do(changes_a)

    res_b = ctx.get_resource(tmp_path / "b.py")
    changes_b = Rename(ctx.project, res_b, 0).get_changes("y2")
    ctx.do(changes_b)

    assert len(ctx._pending) == 2
    paths = {pw.resource.path for pw in ctx._pending}
    assert "a.py" in paths
    assert "b.py" in paths
    proj.close()


def test_move_updates_cross_file_imports(tmp_path: Path) -> None:
    """Moving a module updates import statements in dependent files,
    and the dependent file's PendingWrite has no new_path (it didn't move)."""
    proj = create_project(tmp_path)
    proj.create_file(
        "utils.py",
        dedent("""\
        def helper():
            pass
    """),
    )
    proj.create_file(
        "main.py",
        dedent("""\
        from utils import helper
        helper()
    """),
    )
    proj.create_file("lib/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "utils.py")
    dest = ctx.project.get_resource("lib")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)

    # main.py should have an updated import
    main_writes = [pw for pw in ctx._pending if pw.resource.path == "main.py"]
    assert len(main_writes) == 1
    assert "lib" in main_writes[0].new_source
    # main.py was not moved — no new_path
    assert main_writes[0].new_path is None
    proj.close()


def test_move_module_commit_removes_original(tmp_path: Path) -> None:
    """After move + commit, the original file is gone from disk."""
    proj = create_project(tmp_path)
    proj.create_file("src.py", "x = 1\n")
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "src.py")
    dest = ctx.project.get_resource("pkg")
    changes = MoveModule(ctx.project, resource).get_changes(dest)
    ctx.do(changes)
    ctx.commit()

    assert not (tmp_path / "src.py").exists()
    assert (tmp_path / "pkg" / "src.py").exists()
    assert (tmp_path / "pkg" / "src.py").read_text() == "x = 1\n"
    proj.close()


def test_move_two_modules_into_same_package(tmp_path: Path) -> None:
    """Two sequential moves into the same package both complete correctly."""
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "FOO = 1\n")
    proj.create_file("bar.py", "BAR = 2\n")
    proj.create_file("pkg/__init__.py", "")

    ctx = proj.make_context()

    foo = ctx.get_resource(tmp_path / "foo.py")
    dest = ctx.project.get_resource("pkg")
    ctx.do(MoveModule(ctx.project, foo).get_changes(dest))

    bar = ctx.get_resource(tmp_path / "bar.py")
    dest = ctx.project.get_resource("pkg")
    ctx.do(MoveModule(ctx.project, bar).get_changes(dest))

    ctx.commit()

    assert (tmp_path / "pkg" / "foo.py").read_text() == "FOO = 1\n"
    assert (tmp_path / "pkg" / "bar.py").read_text() == "BAR = 2\n"
    assert not (tmp_path / "foo.py").exists()
    assert not (tmp_path / "bar.py").exists()
    proj.close()
