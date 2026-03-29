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

Supports --dry-run and --diff via the bootstrap.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run
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

    ctx.ensure_package(dest_dir)

    dest = ctx.project.get_resource(dest_dir)
    print(f"Moving {source.path} -> {dest.path}/")

    mover = MoveModule(ctx.project, source)
    changes = mover.get_changes(dest)
    ctx.do(changes)

    if ctx.args.rename:
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
