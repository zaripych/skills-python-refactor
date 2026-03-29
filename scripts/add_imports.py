"""Add a missing import to files that reference a module without importing it.

The factory `add_import` returns a refactor function — pass any ImportInfo
and a detection predicate.

Usage:
    python ensure_imports.py --project-root /path/to/repo /path/to/tests
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Protocol

from rope.base.change import ChangeContents, ChangeSet
from rope.refactor.importutils.importinfo import FromImport, NormalImport
from rope.refactor.importutils.module_imports import ModuleImports

sys.path.insert(0, str(Path(__file__).parent))
from rope_bootstrap import RefactorContext, RefactorFn, run


class NeedsImportFn(Protocol):
    """Predicate that returns True when a parsed module needs the import."""

    def __call__(self, tree: ast.Module) -> bool: ...


def add_import(
    import_info: NormalImport | FromImport,
    needs_import: NeedsImportFn,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> RefactorFn:
    """Return a refactor function that adds `import_info` where `needs_import` is True.

    Rope handles deduplication, so the import won't be added if it already exists.
    """
    _include = include or []
    _exclude = exclude or []

    def refactor(ctx: RefactorContext) -> None:
        files = ctx.find_files(include=_include, exclude=_exclude)
        for file_path in files:
            resource = ctx.get_resource(file_path)
            source = resource.read()

            tree = ast.parse(source)
            if not needs_import(tree):
                continue

            pymodule = ctx.project.get_pymodule(resource)
            module_imports = ModuleImports(ctx.project, pymodule)
            module_imports.add_import(import_info)
            new_source = module_imports.get_changed_source()

            if new_source != source:
                cs = ChangeSet(f"Change <{resource.path}>")
                cs.add_change(ChangeContents(resource, new_source))
                ctx.do(cs)

    return refactor


def _uses_pytest(tree: ast.Module) -> bool:
    """Return True if any node references `pytest.something`."""
    return any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "pytest"
        for node in ast.walk(tree)
    )


if __name__ == "__main__":
    run(
        add_import(NormalImport((("pytest", None),)), _uses_pytest),
        description="Add import pytest where needed",
    )
