"""Move global symbols between modules using rope's MoveGlobal.

Handles batch moves with upfront validation and automatic cleanup of stale
imports in the destination file before each move.

Usage:
    uv run python move_globals.py \\
        --project-root /path/to/project \\
        source_file.py dest.dotted.module SYMBOL1 SYMBOL2 ...

Symbol order matters: move dependencies before dependents. If symbol B
references symbol A and both are being moved, list A first. Otherwise rope
adds a temporary import of A from the source into the destination, which
becomes stale once A moves and must be cleaned up.

Supports --dry-run and --diff via the bootstrap.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor.importutils.module_imports import ModuleImports
from rope.refactor.importutils import importinfo
from rope.refactor.move import create_move


def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="Source file containing the symbols")
    parser.add_argument("dest", type=str, help="Destination dotted module name")
    parser.add_argument("symbols", nargs="+", help="Symbols to move")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Source folder relative to project root (e.g. src). Auto-detected if omitted.",
    )


def _find_offset(project, resource, symbol: str) -> tuple[int, int] | None:
    """Find the string offset of a symbol definition using rope's scope API.

    Returns (offset, lineno) or None if the symbol is not locally defined
    in the module's top-level scope.
    """
    pymodule = project.get_pymodule(resource)
    scope = pymodule.get_scope()
    if symbol not in scope.get_defined_names():
        return None
    pyname = scope[symbol]
    if pyname.get_definition_location()[0].get_resource() != resource:
        return None
    lineno = pyname.get_definition_location()[1]
    source = resource.read()
    line_start = pymodule.lines.get_line_start(lineno)
    col = source[line_start:].index(symbol)
    return line_start + col, lineno


def _remove_symbol_import(ctx: RefactorContext, dest_path: Path, symbol: str) -> None:
    """Remove an import of `symbol` from the destination file using rope's import API.

    When moving a symbol that the destination already imports, the stale import
    must be removed first. Otherwise rope adds the definition alongside the
    import, creating a circular dependency.
    """
    resource = ctx.get_resource(dest_path)
    pymodule = ctx.project.get_pymodule(resource)
    module_imports = ModuleImports(ctx.project, pymodule)

    for import_stmt in module_imports.imports:
        info = import_stmt.import_info
        if not isinstance(info, importinfo.FromImport):
            continue
        names = [n for n, _ in info.names_and_aliases]
        if symbol not in names:
            continue

        if len(names) == 1:
            import_stmt.empty_import()
        else:
            new_names = [(n, a) for n, a in info.names_and_aliases if n != symbol]
            import_stmt.import_info = importinfo.FromImport(
                info.module_name, info.level, new_names
            )
        break
    else:
        return

    new_source = module_imports.get_changed_source()
    if new_source != resource.read():
        changes = ChangeSet(f"Remove import of {symbol} from {dest_path.name}")
        changes.add_change(ChangeContents(resource, new_source))
        ctx.do(changes)
        print(f"  Removed import of {symbol} from {dest_path.name}")


def refactor(ctx: RefactorContext) -> None:
    # Validate all symbols are locally defined in the source before making any changes
    resource = ctx.get_resource(ctx.args.source)
    pymodule = ctx.project.get_pymodule(resource)
    scope = pymodule.get_scope()
    defined = scope.get_defined_names()
    missing = []
    for s in ctx.args.symbols:
        if s not in defined:
            missing.append(f"{s} (not found)")
        elif scope[s].get_definition_location()[0].get_resource() != resource:
            missing.append(f"{s} (imported, not locally defined)")
    if missing:
        raise ValueError(f"Cannot move from {ctx.args.source}: {', '.join(missing)}")

    # Resolve destination module, creating it and parent packages if needed
    dest_file = ctx.ensure_module(ctx.args.dest, source_root=ctx.args.source_root)

    for symbol in ctx.args.symbols:
        # Remove stale import of this symbol from destination before moving
        _remove_symbol_import(ctx, dest_file, symbol)

        resource = ctx.get_resource(ctx.args.source)
        found = _find_offset(ctx.project, resource, symbol)
        if found is None:
            raise ValueError(
                f"Symbol {symbol} disappeared from {ctx.args.source} during move"
            )
        offset, lineno = found
        print(f"Moving {symbol} (line {lineno}, offset {offset})")

        mover = create_move(ctx.project, resource, offset)
        changes = mover.get_changes(dest=ctx.args.dest)
        ctx.do(changes)


if __name__ == "__main__":
    run(
        refactor,
        description="Move global symbols to a destination module",
        setup_args=setup_args,
    )
