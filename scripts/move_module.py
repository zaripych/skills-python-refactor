"""Move a Python module to a new directory using rope's MoveModule.

Rewrites all imports across the project. Optionally renames the module
after moving.

Usage:
    uv run python move_module.py \\
        --project-root /path/to/project \\
        src/pkg/module.py src/pkg/new_location/ \\
        --rename new_name

The destination directory is created automatically if it doesn't exist,
along with __init__.py files for rope's import resolution.

Use --rename to change the module name (e.g. move status.py and rename
to handler.py).

Supports --diff via the bootstrap.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run
from rope.base.exceptions import ResourceNotFoundError
from rope.refactor.move import MoveModule
from rope.refactor.rename import Rename


def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="Source module file to move")
    parser.add_argument(
        "dest_dir", type=str, help="Destination directory (relative to project root)"
    )
    parser.add_argument(
        "--rename", type=str, default=None, help="Rename the module after moving"
    )


def refactor(ctx: RefactorContext) -> None:
    source = ctx.get_resource(ctx.args.source)
    dest_dir = ctx.args.dest_dir

    # Pre-validation: source must not already be in dest
    source_parent = Path(source.path).parent
    if source_parent == Path(dest_dir):
        raise ValueError(f"Source {source.path} is already in destination {dest_dir}")

    # Ensure __init__.py exists for the source's own package and all packages
    # it imports from, so rope's modname() can resolve full dotted paths.
    ctx.ensure_packages(source)

    # Check if dest_dir/source.name already exists.
    # Without --rename: this would silently overwrite — abort.
    # With --rename: rename at source first, then move to avoid collision.
    rename_before_move = False
    dest_file = f"{dest_dir}/{source.name}"
    dest_exists = False
    try:
        ctx.project.get_resource(dest_file)
        dest_exists = True
    except ResourceNotFoundError:
        pass

    if dest_exists and not ctx.args.rename:
        raise ValueError(
            f"Destination already exists: {dest_file}. "
            f"Use --rename to move with a different name, or remove the existing file."
        )
    if dest_exists and ctx.args.rename:
        rename_before_move = True

    # Check the final destination (dest_dir/{rename}.py) doesn't already exist
    if ctx.args.rename:
        renamed_dest = f"{dest_dir}/{ctx.args.rename}.py"
        try:
            ctx.project.get_resource(renamed_dest)
            raise ValueError(
                f"Destination already exists: {renamed_dest}. "
                f"Remove or rename the existing file first."
            )
        except ResourceNotFoundError:
            pass

    ctx.ensure_package(dest_dir)

    if rename_before_move:
        # Check that the renamed name doesn't already exist in the source directory
        source_renamed = f"{Path(source.path).parent}/{ctx.args.rename}.py"
        try:
            ctx.project.get_resource(source_renamed)
            raise ValueError(
                f"Cannot rename before move: {source_renamed} already exists "
                f"in the source directory."
            )
        except ResourceNotFoundError:
            pass

        # Rename in-place first to avoid destination collision
        print(
            f"Renaming {source.name} -> {ctx.args.rename} (before move, destination collision)"
        )
        renamer = Rename(ctx.project, source)
        changes = renamer.get_changes(ctx.args.rename)
        ctx.do(changes)
        # Re-resolve source after rename
        renamed_path = f"{Path(source.path).parent}/{ctx.args.rename}.py"
        source = ctx.project.get_resource(renamed_path)

    dest = ctx.project.get_resource(dest_dir)
    print(f"Moving {source.path} -> {dest.path}/")

    mover = MoveModule(ctx.project, source)
    changes = mover.get_changes(dest)
    ctx.do(changes)

    if ctx.args.rename and not rename_before_move:
        moved_path = f"{dest_dir}/{source.name}"
        moved = ctx.project.get_resource(moved_path)
        print(f"Renaming {moved.name} -> {ctx.args.rename}")
        renamer = Rename(ctx.project, moved)
        changes = renamer.get_changes(ctx.args.rename)
        ctx.do(changes)


if __name__ == "__main__":
    run(
        refactor,
        description="Move a module to a new directory",
        setup_args=setup_args,
    )
