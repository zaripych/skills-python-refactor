from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

from rope.refactor.rename import Rename

from conftest import create_project, get_diffs


def test_write_queues_change(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")
    ctx.write(resource, "x = 2\n")

    diffs = get_diffs(ctx)
    assert len(diffs) == 1
    assert "-x = 1" in diffs[0]
    assert "+x = 2" in diffs[0]
    proj.close()


def test_write_skips_unchanged(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")
    ctx.write(resource, "x = 1\n")

    assert len(ctx._pending) == 0
    proj.close()


def test_sequential_writes_see_previous_changes(tmp_path: Path) -> None:
    """After ctx.write(), subsequent resource.read() returns the new content."""
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")
    ctx.write(resource, "x = 2\n")

    source = resource.read()
    assert source == "x = 2\n"
    proj.close()


def test_multiple_files(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("a.py", "a = 1\n")
    proj.create_file("b.py", "b = 1\n")

    ctx = proj.make_context()
    res_a = ctx.get_resource(tmp_path / "a.py")
    res_b = ctx.get_resource(tmp_path / "b.py")
    ctx.write(res_a, "a = 2\n")
    ctx.write(res_b, "b = 2\n")

    diffs = get_diffs(ctx)
    assert len(diffs) == 2
    proj.close()


def test_get_resource_resolves_path(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file("sub/foo.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "sub" / "foo.py")
    assert resource.path == "sub/foo.py"
    proj.close()


def test_multiple_writes_to_same_file(tmp_path: Path) -> None:
    """Successive writes to the same file compose correctly."""
    proj = create_project(tmp_path)
    proj.create_file("foo.py", "x = 1\ny = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")

    ctx.write(resource, "x = 2\ny = 1\n")
    source = resource.read()
    assert source == "x = 2\ny = 1\n"
    ctx.write(resource, "x = 2\ny = 2\n")

    assert len(ctx._pending) == 2
    assert resource.read() == "x = 2\ny = 2\n"
    proj.close()


def test_write_does_not_touch_disk(tmp_path: Path) -> None:
    """ctx.write() must not modify the file on disk."""
    proj = create_project(tmp_path)
    file_path = proj.create_file("foo.py", "x = 1\n")
    mtime_before = os.stat(file_path).st_mtime_ns

    ctx = proj.make_context()
    resource = ctx.get_resource(file_path)
    ctx.write(resource, "x = 2\n")

    mtime_after = os.stat(file_path).st_mtime_ns
    assert mtime_before == mtime_after
    assert file_path.read_text() == "x = 1\n"
    proj.close()


def test_commit_writes_to_disk(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    file_path = proj.create_file("foo.py", "x = 1\n")

    ctx = proj.make_context()
    resource = ctx.get_resource(file_path)
    ctx.write(resource, "x = 2\n")
    ctx.commit()

    assert file_path.read_text() == "x = 2\n"
    proj.close()


def test_dry_run_never_writes_to_disk(tmp_path: Path) -> None:
    """Full dry-run scenario: write + no commit = disk untouched."""
    proj = create_project(tmp_path)
    file_a = proj.create_file("a.py", "a = 1\n")
    file_b = proj.create_file("b.py", "b = 1\n")
    mtime_a = os.stat(file_a).st_mtime_ns
    mtime_b = os.stat(file_b).st_mtime_ns

    ctx = proj.make_context()
    ctx.dry_run = True
    ctx.write(ctx.get_resource(file_a), "a = 2\n")
    ctx.write(ctx.get_resource(file_b), "b = 2\n")

    # Pending changes exist for reporting
    assert len(ctx._pending) == 2
    # But disk is untouched
    assert os.stat(file_a).st_mtime_ns == mtime_a
    assert os.stat(file_b).st_mtime_ns == mtime_b
    assert file_a.read_text() == "a = 1\n"
    assert file_b.read_text() == "b = 1\n"
    proj.close()


def test_do_tracks_rename(tmp_path: Path) -> None:
    """ctx.do() with a Rename changeset tracks changes in _pending."""
    proj = create_project(tmp_path)
    proj.create_file(
        "foo.py",
        dedent("""\
        my_var = 1
        print(my_var)
    """),
    )

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")
    changes = Rename(ctx.project, resource, 0).get_changes("new_var")
    ctx.do(changes)

    assert len(ctx._pending) == 1
    assert ctx._pending[0].new_source == dedent("""\
        new_var = 1
        print(new_var)
    """)

    diffs = get_diffs(ctx)
    assert "-my_var = 1" in diffs[0]
    assert "+new_var = 1" in diffs[0]
    assert "-print(my_var)" in diffs[0]
    assert "+print(new_var)" in diffs[0]
    proj.close()


def test_do_does_not_touch_disk(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    file_path = proj.create_file(
        "foo.py",
        dedent("""\
        my_var = 1
    """),
    )
    mtime_before = os.stat(file_path).st_mtime_ns

    ctx = proj.make_context()
    resource = ctx.get_resource(file_path)
    changes = Rename(ctx.project, resource, 0).get_changes("new_var")
    ctx.do(changes)

    assert os.stat(file_path).st_mtime_ns == mtime_before
    assert file_path.read_text() == dedent("""\
        my_var = 1
    """)
    proj.close()


def test_do_visible_to_subsequent_reads(tmp_path: Path) -> None:
    proj = create_project(tmp_path)
    proj.create_file(
        "foo.py",
        dedent("""\
        my_var = 1
    """),
    )

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "foo.py")
    changes = Rename(ctx.project, resource, 0).get_changes("new_var")
    ctx.do(changes)

    assert resource.read() == dedent("""\
        new_var = 1
    """)
    proj.close()


def test_do_across_files(tmp_path: Path) -> None:
    """Rename used across multiple files tracks all changed files."""
    proj = create_project(tmp_path)
    proj.create_file(
        "mod.py",
        dedent("""\
        def greet():
            pass
    """),
    )
    proj.create_file(
        "main.py",
        dedent("""\
        import mod
        mod.greet()
    """),
    )

    ctx = proj.make_context()
    resource = ctx.get_resource(tmp_path / "mod.py")
    changes = Rename(ctx.project, resource, 4).get_changes("hello")
    ctx.do(changes)

    assert len(ctx._pending) == 2
    diffs = get_diffs(ctx)
    all_diffs = "\n".join(diffs)
    assert "-def greet():" in all_diffs
    assert "+def hello():" in all_diffs
    assert "-mod.greet()" in all_diffs
    assert "+mod.hello()" in all_diffs
    proj.close()
