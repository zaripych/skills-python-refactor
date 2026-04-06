"""Remove re-exports from __init__.py by rewriting callers to import from source modules.

Parses an __init__.py to find symbols that are imported and re-exported, resolves
each to its defining module, rewrites every caller to import directly from the
source, and removes the re-export lines from __init__.py.

Usage:
    uv run python deexport.py \\
        --project-root /path/to/project \\
        pendant/  [SYMBOL1 SYMBOL2 ...]

Supports --diff via the bootstrap.
"""

import ast
import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rope_bootstrap import RefactorContext, run
from rope.base import libutils, pynames, worder, evaluate
from rope.base.change import ChangeContents, ChangeSet
from rope.refactor import occurrences
from rope.refactor.importutils import importinfo
from rope.refactor.importutils.module_imports import ModuleImports


def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "package_path",
        type=Path,
        help="Path to __init__.py or its parent directory",
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help="Specific symbols to de-export (all re-exports if omitted)",
    )


def _resolve_init(ctx: RefactorContext, package_path: Path) -> Path:
    """Resolve package_path to the __init__.py file."""
    if package_path.is_dir():
        init = package_path / "__init__.py"
    elif package_path.name == "__init__.py":
        init = package_path
    else:
        raise ValueError(f"{package_path} is not a directory or __init__.py")
    if not init.exists():
        raise ValueError(f"{init} does not exist")
    return init


def _build_reexport_map(ctx: RefactorContext, init_resource) -> dict[str, str]:
    """Build a map of symbol_name -> source_dotted_module for re-exports.

    Iterates FromImport statements in the __init__.py scope and resolves each
    ImportedName to its actual definition module via get_definition_location().
    """
    pymodule = ctx.project.get_pymodule(init_resource)
    scope = pymodule.get_scope()
    module_imports = ModuleImports(ctx.project, pymodule)

    reexport_map: dict[str, str] = {}
    for import_stmt in module_imports.imports:
        info = import_stmt.import_info
        if not isinstance(info, importinfo.FromImport):
            continue
        for name, _alias in info.names_and_aliases:
            if name == "*":
                print(f"  Warning: skipping star import in {init_resource.path}")
                continue
            if name not in scope.get_defined_names():
                continue
            pyname = scope[name]
            if not isinstance(pyname, pynames.ImportedName):
                continue
            def_module, _lineno = pyname.get_definition_location()
            if def_module is None:
                print(f"  Warning: cannot resolve definition of {name}, skipping")
                continue
            source_resource = def_module.get_resource()
            if source_resource is None:
                print(f"  Warning: cannot resolve resource for {name}, skipping")
                continue
            source_modname = libutils.modname(source_resource)
            reexport_map[name] = source_modname

    return reexport_map


def _find_caller_files(ctx, init_resource, reexport_map) -> set[str]:
    """Use rope's occurrence finder to locate all files that import re-exported symbols."""
    pymodule = ctx.project.get_pymodule(init_resource)
    source = init_resource.read()
    caller_paths: set[str] = set()

    scope = pymodule.get_scope()
    for name in reexport_map:
        pyname = scope[name]
        finder = occurrences.create_finder(ctx.project, name, pyname, imports=True)
        for resource in ctx.project.get_python_files():
            if resource.path == init_resource.path:
                continue
            for occurrence in finder.find_occurrences(resource=resource):
                caller_paths.add(resource.path)
                break  # one hit per file is enough

    return caller_paths


def _rewrite_caller(
    ctx: RefactorContext,
    resource_path: str,
    package_modname: str,
    reexport_map: dict[str, str],
) -> None:
    """Rewrite imports in a single caller file."""
    resource = ctx.project.get_resource(resource_path)
    pymodule = ctx.project.get_pymodule(resource)
    module_imports = ModuleImports(ctx.project, pymodule)
    context = importinfo.ImportContext(ctx.project, resource.parent)
    changed = False

    for import_stmt in module_imports.imports:
        info = import_stmt.import_info
        if not isinstance(info, importinfo.FromImport):
            continue

        # Resolve the import target to check if it points to our package
        if info.level == 0:
            if info.module_name != package_modname:
                continue
        else:
            imported_resource = info.get_imported_resource(context)
            if imported_resource is None:
                continue
            resolved = libutils.modname(imported_resource)
            if resolved != package_modname:
                continue

        to_rewrite = []
        to_keep = []
        for name, alias in info.names_and_aliases:
            if name in reexport_map:
                to_rewrite.append((name, alias))
            else:
                to_keep.append((name, alias))

        if not to_rewrite:
            continue

        # Update the original import statement
        if to_keep:
            import_stmt.import_info = importinfo.FromImport(
                info.module_name, info.level, to_keep
            )
        else:
            import_stmt.empty_import()

        # Group rewritten names by source module and add new imports
        by_source: dict[str, list[tuple[str, str | None]]] = {}
        for name, alias in to_rewrite:
            source_mod = reexport_map[name]
            by_source.setdefault(source_mod, []).append((name, alias))

        for source_mod, names in sorted(by_source.items()):
            module_imports.add_import(importinfo.FromImport(source_mod, 0, names))

        changed = True

    if not changed:
        return

    new_source = module_imports.get_changed_source()
    if new_source is not None and new_source != resource.read():
        changes = ChangeSet(f"Rewrite imports in {resource.path}")
        changes.add_change(ChangeContents(resource, new_source))
        ctx.do(changes)


def _names_used_in_body(source: str, candidates: set[str]) -> set[str]:
    """Return the subset of candidates that are referenced in function/class bodies.

    Only walks into FunctionDef, AsyncFunctionDef, and ClassDef nodes -- not
    top-level import statements or __all__ assignments.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    used: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id in candidates:
                used.add(child.id)
    return used


def _cleanup_init(
    ctx: RefactorContext,
    init_path: Path,
    reexport_map: dict[str, str],
) -> None:
    """Remove re-export lines and clean up __all__ in __init__.py.

    Imports that are used locally in __init__.py (e.g. referenced in function
    bodies) are kept even though they are de-exported.
    """
    resource = ctx.get_resource(init_path)
    pymodule = ctx.project.get_pymodule(resource)
    module_imports = ModuleImports(ctx.project, pymodule)

    de_exported = set(reexport_map.keys())
    locally_used = _names_used_in_body(resource.read(), de_exported)
    if locally_used:
        print(
            f"  Keeping imports used locally in {resource.path}: {', '.join(sorted(locally_used))}"
        )
    removable = de_exported - locally_used

    for import_stmt in module_imports.imports:
        info = import_stmt.import_info
        if not isinstance(info, importinfo.FromImport):
            continue
        names = [n for n, _ in info.names_and_aliases]
        if not any(n in removable for n in names):
            continue

        remaining = [(n, a) for n, a in info.names_and_aliases if n not in removable]
        if remaining:
            import_stmt.import_info = importinfo.FromImport(
                info.module_name, info.level, remaining
            )
        else:
            import_stmt.empty_import()

    new_source = module_imports.get_changed_source()
    if new_source is None:
        new_source = resource.read()

    # Clean up __all__ if present
    new_source = _cleanup_dunder_all(new_source, de_exported)

    if new_source != resource.read():
        changes = ChangeSet(f"Remove re-exports from {resource.path}")
        changes.add_change(ChangeContents(resource, new_source))
        ctx.do(changes)


def _cleanup_dunder_all(source: str, de_exported: set[str]) -> str:
    """Remove de-exported names from __all__ list literal."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "__all__":
            continue
        if not isinstance(node.value, ast.List):
            print("  Warning: __all__ is not a simple list literal, skipping cleanup")
            return source

        remaining = [
            elt
            for elt in node.value.elts
            if not (isinstance(elt, ast.Constant) and elt.value in de_exported)
        ]

        if not remaining:
            # Remove the entire __all__ assignment
            lines = source.splitlines(keepends=True)
            start = node.lineno - 1
            end = node.end_lineno
            del lines[start:end]
            return "".join(lines)

        # Rebuild __all__ with remaining names
        names = [elt.value for elt in remaining if isinstance(elt, ast.Constant)]
        new_all = "__all__ = [" + ", ".join(f'"{n}"' for n in names) + "]\n"
        lines = source.splitlines(keepends=True)
        start = node.lineno - 1
        end = node.end_lineno
        lines[start:end] = [new_all]
        return "".join(lines)

    return source


def refactor(ctx: RefactorContext) -> None:
    init_path = _resolve_init(ctx, ctx.args.package_path)
    init_resource = ctx.get_resource(init_path)

    # Phase 1: Build the re-export map
    reexport_map = _build_reexport_map(ctx, init_resource)
    if not reexport_map:
        print("No re-exports found in", init_path)
        return

    # Filter to requested symbols
    if ctx.args.symbols:
        missing = [s for s in ctx.args.symbols if s not in reexport_map]
        if missing:
            raise ValueError(f"Symbols not found as re-exports: {', '.join(missing)}")
        reexport_map = {k: v for k, v in reexport_map.items() if k in ctx.args.symbols}

    package_modname = libutils.modname(init_resource)
    print(f"De-exporting from {package_modname}:")
    for sym, src in sorted(reexport_map.items()):
        print(f"  {sym} -> {src}")

    # Phase 2: Find callers via rope's occurrence finder and rewrite
    caller_paths = _find_caller_files(ctx, init_resource, reexport_map)
    print(f"  {len(caller_paths)} file(s) import re-exported symbols")
    for path in sorted(caller_paths):
        _rewrite_caller(ctx, path, package_modname, reexport_map)

    # Phase 3: Clean up __init__.py
    _cleanup_init(ctx, init_path, reexport_map)


if __name__ == "__main__":
    run(
        refactor,
        description="Remove re-exports from __init__.py",
        setup_args=setup_args,
    )
