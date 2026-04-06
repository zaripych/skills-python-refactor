"""Convert relative imports to absolute imports.

Only touches explicit relative imports (``from .foo import bar``,
``from ..models import X``).  Absolute imports and ``import foo`` statements
are left untouched.  Handles both top-level and lazy (function-body) imports.

Usage:
    uv run python absolutize.py \\
        --project-root /path/to/project \\
        [FILES_OR_DIRS...]

If no files or directories are given, processes all .py files in the project.
Supports --diff via the bootstrap.
"""

import ast
import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor.importutils import importinfo
from rope.refactor.importutils.module_imports import ModuleImports


def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories to process (all .py files if omitted)",
    )


def _collect_resources(ctx: RefactorContext, paths: list[Path]) -> list:
    """Collect rope resources from given paths, or all project Python files."""
    if not paths:
        return sorted(ctx.project.get_python_files(), key=lambda r: r.path)

    result = []
    project_root = Path(ctx.project.root.real_path)
    for p in paths:
        p = p.resolve()
        if p.is_file() and p.suffix == ".py":
            result.append(ctx.get_resource(p))
        elif p.is_dir():
            for pyfile in sorted(p.rglob("*.py")):
                rel = pyfile.relative_to(project_root)
                if ".venv" not in rel.parts:
                    result.append(ctx.get_resource(pyfile))
        else:
            print(f"  Warning: skipping {p} (not a .py file or directory)")
    return result


def _modname_from_path(resource, source_folders) -> str | None:
    """Derive a dotted module name from the resource path relative to a source folder.

    Unlike ``libutils.modname``, this walks up from the resource through *all*
    parent directories until it hits a source folder -- it does not stop at
    the first directory missing ``__init__.py``, so namespace packages are
    handled correctly.
    """
    res_path = resource.pathlib
    for sf in source_folders:
        sf_path = sf.pathlib
        if not res_path.is_relative_to(sf_path):
            continue
        rel = res_path.relative_to(sf_path)
        parts = list(rel.parts)
        # Strip .py / __init__.py from the leaf
        if parts[-1] == "__init__.py":
            parts.pop()
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts) if parts else None
    return None


def _absolutize_lazy_imports(
    source: str,
    context: importinfo.ImportContext,
    source_folders: list,
) -> str:
    """Rewrite relative imports inside function/class bodies.

    These are invisible to rope's ModuleImports (which only handles top-level),
    so we find them via ast.walk and do direct text replacement.
    """
    tree = ast.parse(source)
    top_level = {id(node) for node in tree.body}

    # Collect (start_offset, end_offset, replacement_text) for each lazy
    # relative import, in reverse source order so replacements don't shift
    # earlier offsets.
    replacements: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if id(node) in top_level:
            continue
        if not node.level:
            continue

        info = importinfo.FromImport(
            node.module or "",
            node.level,
            [(alias.name, alias.asname) for alias in node.names],
        )
        imported_resource = info.get_imported_resource(context)
        if imported_resource is None:
            continue
        absolute_name = _modname_from_path(imported_resource, source_folders)
        if absolute_name is None:
            continue

        names = ", ".join(
            f"{name} as {alias}" if alias else name
            for name, alias in info.names_and_aliases
        )
        new_text = f"from {absolute_name} import {names}"

        # Use the AST node's line/col offsets to locate the original text.
        start = _offset_of(source, node.lineno, node.col_offset)
        end = _offset_of(source, node.end_lineno, node.end_col_offset)
        replacements.append((start, end, new_text))

    for start, end, new_text in sorted(replacements, reverse=True):
        source = source[:start] + new_text + source[end:]

    return source


def _offset_of(source: str, lineno: int, col_offset: int) -> int:
    """Convert a 1-based line number and 0-based column to a string offset."""
    offset = 0
    for i, line in enumerate(source.splitlines(keepends=True), 1):
        if i == lineno:
            return offset + col_offset
        offset += len(line)
    return offset + col_offset


def refactor(ctx: RefactorContext) -> None:
    resources = _collect_resources(ctx, ctx.args.paths)
    source_folders = ctx.project.get_source_folders()

    for resource in resources:
        source = resource.read()
        pymodule = ctx.project.get_pymodule(resource)
        module_imports = ModuleImports(ctx.project, pymodule)
        context = importinfo.ImportContext(ctx.project, resource.parent)
        changed = False

        for import_stmt in module_imports.imports:
            info = import_stmt.import_info
            if not isinstance(info, importinfo.FromImport):
                continue
            if info.level == 0:
                continue

            imported_resource = info.get_imported_resource(context)
            if imported_resource is None:
                continue
            absolute_name = _modname_from_path(imported_resource, source_folders)
            if absolute_name is None:
                continue
            import_stmt.import_info = importinfo.FromImport(
                absolute_name, 0, info.names_and_aliases
            )
            changed = True

        if not changed:
            new_source = source
        else:
            new_source = module_imports.get_changed_source()
            if new_source is None:
                new_source = source

        # Handle lazy imports inside function/class bodies.
        new_source = _absolutize_lazy_imports(new_source, context, source_folders)

        if new_source != source:
            changes = ChangeSet(f"Absolutize imports in {resource.path}")
            changes.add_change(ChangeContents(resource, new_source))
            ctx.do(changes)


if __name__ == "__main__":
    run(
        refactor,
        description="Convert relative imports to absolute",
        setup_args=setup_args,
    )
