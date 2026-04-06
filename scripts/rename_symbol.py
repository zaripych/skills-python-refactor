"""Rename a Python symbol (function, class, variable) across the project using rope's Rename.

Rewrites all references — imports, call sites, and type annotations — to use the new name.
Requires both symbol name and line number to anchor the rename unambiguously (avoids
matching shadowed or re-exported symbols).

Usage:
    uv run python rename_symbol.py \\
        --diff \\
        src/pkg/module.py 11 old_name new_name

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
        "source", type=Path, help="File containing the symbol to rename"
    )
    parser.add_argument("line", type=int, help="Line number of the symbol definition")
    parser.add_argument("old_name", type=str, help="Current symbol name")
    parser.add_argument("new_name", type=str, help="New symbol name")


def _find_offset(ctx: RefactorContext, resource, line: int, symbol: str) -> int:
    """Find the byte offset of a symbol at a specific line.

    Uses both line number and symbol name to anchor unambiguously — avoids
    matching shadowed or re-exported symbols with the same name.
    """
    pymodule = ctx.project.get_pymodule(resource)
    source = resource.read()
    line_start = pymodule.lines.get_line_start(line)
    line_end = pymodule.lines.get_line_end(line)
    line_text = source[line_start:line_end]
    try:
        col = line_text.index(symbol)
    except ValueError:
        raise ValueError(
            f"{symbol} not found on line {line} of {resource.path}"
        ) from None
    return line_start + col


def refactor(ctx: RefactorContext) -> None:
    resource = ctx.get_resource(ctx.args.source)
    line = ctx.args.line
    old_name = ctx.args.old_name
    new_name = ctx.args.new_name

    ctx.ensure_packages(resource)

    offset = _find_offset(ctx, resource, line, old_name)
    print(f"Renaming {old_name} -> {new_name} (line {line}, offset {offset})")
    changes = Rename(ctx.project, resource, offset).get_changes(new_name)
    ctx.do(changes)


if __name__ == "__main__":
    run(
        refactor,
        description="Rename a symbol across the project",
        setup_args=setup_args,
    )
