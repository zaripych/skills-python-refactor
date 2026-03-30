"""Convert relative imports to absolute imports.

Only touches explicit relative imports (``from .foo import bar``,
``from ..models import X``).  Absolute imports and ``import foo`` statements
are left untouched.

Usage:
    uv run python absolutize.py \\
        --project-root /path/to/project \\
        [FILES_OR_DIRS...]

If no files or directories are given, processes all .py files in the project.
Supports --dry-run and --diff via the bootstrap.
"""

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
            continue

        new_source = module_imports.get_changed_source()
        if new_source is not None and new_source != source:
            changes = ChangeSet(f"Absolutize imports in {resource.path}")
            changes.add_change(ChangeContents(resource, new_source))
            ctx.do(changes)


if __name__ == "__main__":
    run(
        refactor,
        description="Convert relative imports to absolute",
        setup_args=setup_args,
    )
