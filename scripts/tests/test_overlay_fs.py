"""Tests for OverlayFSCommands — deferred folders, moves, and removals."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rope.base.fscommands import FileSystemCommands, FileContent
from rope.base.project import Project

from rope_bootstrap import OverlayFSCommands


def _make_fs(tmp_path: Path) -> tuple[OverlayFSCommands, Project]:
    project = Project(str(tmp_path))
    return OverlayFSCommands(project.fscommands), project


def test_create_folder_deferred_to_commit(tmp_path: Path) -> None:
    """create_folder should not touch disk until commit."""
    fs, project = _make_fs(tmp_path)

    fs.create_folder(str(tmp_path / "sub"))

    assert not (tmp_path / "sub").exists()

    fs.commit()
    assert (tmp_path / "sub").is_dir()
    project.close()


def test_create_nested_folders_sorted(tmp_path: Path) -> None:
    """Nested folders are created in sorted order so parents come first."""
    fs, project = _make_fs(tmp_path)

    # Add child before parent — sorted order should still work
    fs.create_folder(str(tmp_path / "a" / "b"))
    fs.create_folder(str(tmp_path / "a"))

    fs.commit()
    assert (tmp_path / "a").is_dir()
    assert (tmp_path / "a" / "b").is_dir()
    project.close()


def test_move_from_overlay(tmp_path: Path) -> None:
    """Moving an overlay-only file transfers it to the new key."""
    fs, project = _make_fs(tmp_path)

    fs.write("src.py", FileContent(b"content"))
    fs.move("src.py", "dst.py")

    assert fs.read("dst.py") == FileContent(b"content")
    assert "src.py" not in fs._overlay
    assert "src.py" in fs._removals
    project.close()


def test_move_from_disk(tmp_path: Path) -> None:
    """Moving a disk file reads it into overlay at the new location."""
    fs, project = _make_fs(tmp_path)

    (tmp_path / "on_disk.py").write_bytes(b"disk content")

    fs.move(str(tmp_path / "on_disk.py"), str(tmp_path / "moved.py"))

    assert fs.read(str(tmp_path / "moved.py")) == FileContent(b"disk content")
    assert str(tmp_path / "on_disk.py") in fs._removals
    project.close()


def test_remove_clears_overlay_and_tracks_removal(tmp_path: Path) -> None:
    fs, project = _make_fs(tmp_path)

    fs.write("tmp.py", FileContent(b"data"))
    fs.remove("tmp.py")

    assert "tmp.py" not in fs._overlay
    assert "tmp.py" in fs._removals
    project.close()


def test_remove_disk_file_on_commit(tmp_path: Path) -> None:
    """Commit removes files tracked in _removals from disk."""
    fs, project = _make_fs(tmp_path)

    target = tmp_path / "doomed.py"
    target.write_text("bye")

    fs.remove(str(target))
    assert target.exists()  # not yet removed

    fs.commit()
    assert not target.exists()
    project.close()


def test_commit_order_write_then_remove(tmp_path: Path) -> None:
    """Commit writes new files before removing old ones."""
    fs, project = _make_fs(tmp_path)

    old = tmp_path / "old.py"
    old.write_text("old")

    # Simulate a move: write new location, remove old
    fs.write(str(tmp_path / "new.py"), FileContent(b"new"))
    fs.remove(str(old))

    fs.commit()

    assert (tmp_path / "new.py").read_bytes() == b"new"
    assert not old.exists()
    project.close()


def test_commit_clears_all_state(tmp_path: Path) -> None:
    """After commit, overlay, folders, and removals are all cleared."""
    fs, project = _make_fs(tmp_path)

    (tmp_path / "g.py").write_text("gone")
    fs.write(str(tmp_path / "f.py"), FileContent(b"data"))
    fs.create_folder(str(tmp_path / "d"))
    fs.remove(str(tmp_path / "g.py"))

    fs.commit()

    assert len(fs._overlay) == 0
    assert len(fs._folders) == 0
    assert len(fs._removals) == 0
    project.close()


def test_remove_overlay_only_file_skips_on_commit(tmp_path: Path) -> None:
    """Removing a file that only existed in overlay (never on disk)
    should not raise — the guard skips it."""
    fs, project = _make_fs(tmp_path)

    fs.write("phantom.py", FileContent(b"data"))
    fs.remove("phantom.py")

    fs.commit()  # should not raise
    project.close()


def test_move_then_write_new_location(tmp_path: Path) -> None:
    """Simulates rope moving a file then updating its contents (import rewrites).
    The overlay should hold the updated content at the new path."""
    fs, project = _make_fs(tmp_path)

    (tmp_path / "src.py").write_bytes(b"import old\n")
    fs.move(str(tmp_path / "src.py"), str(tmp_path / "pkg" / "src.py"))
    fs.write(str(tmp_path / "pkg" / "src.py"), FileContent(b"import new\n"))

    assert fs.read(str(tmp_path / "pkg" / "src.py")) == FileContent(b"import new\n")
    project.close()


def test_create_folder_then_move_into_it(tmp_path: Path) -> None:
    """A move into a deferred folder — both should resolve on commit."""
    fs, project = _make_fs(tmp_path)

    (tmp_path / "src.py").write_bytes(b"content")
    fs.create_folder(str(tmp_path / "pkg"))
    fs.move(str(tmp_path / "src.py"), str(tmp_path / "pkg" / "src.py"))

    fs.commit()

    assert (tmp_path / "pkg").is_dir()
    assert (tmp_path / "pkg" / "src.py").read_bytes() == b"content"
    assert not (tmp_path / "src.py").exists()
    project.close()


def test_move_two_files_into_same_folder(tmp_path: Path) -> None:
    """Two modules moved into the same package — both land correctly."""
    fs, project = _make_fs(tmp_path)

    (tmp_path / "a.py").write_bytes(b"a")
    (tmp_path / "b.py").write_bytes(b"b")
    fs.create_folder(str(tmp_path / "pkg"))
    fs.move(str(tmp_path / "a.py"), str(tmp_path / "pkg" / "a.py"))
    fs.move(str(tmp_path / "b.py"), str(tmp_path / "pkg" / "b.py"))

    fs.commit()

    assert (tmp_path / "pkg" / "a.py").read_bytes() == b"a"
    assert (tmp_path / "pkg" / "b.py").read_bytes() == b"b"
    assert not (tmp_path / "a.py").exists()
    assert not (tmp_path / "b.py").exists()
    project.close()


def test_chained_move(tmp_path: Path) -> None:
    """Simulates a rename-then-move: A→B then B→C. Content ends up at C,
    both A and B are scheduled for removal."""
    fs, project = _make_fs(tmp_path)

    fs.write("a.py", FileContent(b"chain"))
    fs.move("a.py", "b.py")
    fs.move("b.py", "c.py")

    assert fs.read("c.py") == FileContent(b"chain")
    assert "a.py" not in fs._overlay
    assert "b.py" not in fs._overlay
    assert "a.py" in fs._removals
    assert "b.py" in fs._removals
    project.close()
