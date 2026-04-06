"""Rename a Python module or package in place using rope's Rename.

Works on both file modules (.py files) and packages (directories).
Rewrites all imports across the project to use the new name.

Usage:
    uv run python rename_module.py \\
        --project-root /path/to/project \\
        src/pkg/old_name.py new_name

    uv run python rename_module.py \\
        --project-root /path/to/project \\
        src/pkg/old_package new_name

Supports --diff via the bootstrap.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run
from rope.refactor.rename import Rename


def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "source", type=Path, help="Module file or package directory to rename"
    )
    parser.add_argument("new_name", type=str, help="New module name (without .py)")


def refactor(ctx: RefactorContext) -> None:
    source = ctx.get_resource(ctx.args.source)
    new_name = ctx.args.new_name

    ctx.ensure_packages(source)

    print(f"Renaming {source.path} -> {new_name}")
    renamer = Rename(ctx.project, source)
    changes = renamer.get_changes(new_name)
    ctx.do(changes)


if __name__ == "__main__":
    run(
        refactor,
        description="Rename a module or package in place",
        setup_args=setup_args,
    )
