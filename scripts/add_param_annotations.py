"""Add type annotations to function parameters by name.

The factory `add_param_annotations` returns a refactor function —
pass any mapping of parameter names to annotation strings and their
required imports.

Usage:
    uv run python /path/to/add_param_annotations.py \
        --project-root /path/to/repo /path/to/directory

Reuse from a project script:

    sys.path.insert(0, "/path/to/skill/scripts")
    from add_param_annotations import add_param_annotations

    run(
        add_param_annotations(
            annotations={"cmd": "server_pb2.ServerCommandMsg"},
            imports={"cmd": FromImport("mylib.protobuf", 0, (("server_pb2", None),))},
            exclude=["test_protocol.py"],
        ),
        ...
    )
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from rope.base.change import ChangeContents, ChangeSet
from rope.base.codeanalyze import ChangeCollector
from rope.refactor.importutils.importinfo import FromImport, NormalImport
from rope.refactor.importutils.module_imports import ModuleImports

sys.path.insert(0, str(Path(__file__).parent))
from rope_bootstrap import RefactorContext, RefactorFn, run


def add_param_annotations(
    annotations: dict[str, str],
    imports: dict[str, NormalImport | FromImport] | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> RefactorFn:
    """Return a refactor function that annotates parameters matching `annotations`.

    Args:
        annotations: Mapping of parameter names to annotation strings.
        imports: Optional mapping of parameter names to rope import objects.
            Only params that need a new import should be listed.
        include: Glob patterns to include (default: all .py files recursively).
        exclude: Glob patterns to exclude (applied after include).
    """
    _imports = imports or {}
    _include = include or []
    _exclude = exclude or []

    def refactor(ctx: RefactorContext) -> None:
        param_names = set(annotations)

        files = ctx.find_files(patterns=param_names, include=_include, exclude=_exclude)

        for file_path in files:
            resource = ctx.get_resource(file_path)
            source = resource.read()

            # Step 1: Find which params need annotations
            tree = ast.parse(source)
            used_params: set[str] = set()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for arg in node.args.args:
                    if arg.arg in annotations and arg.annotation is None:
                        used_params.add(arg.arg)

            if not used_params:
                continue

            # Step 2: Add imports via rope (operates on original source)
            pymodule = ctx.project.get_pymodule(resource)
            module_imports = ModuleImports(ctx.project, pymodule)
            for param in sorted(used_params):
                if param in _imports:
                    module_imports.add_import(_imports[param])
            after_imports = module_imports.get_changed_source()

            # Step 3: Add annotations to import-modified source
            # Re-parse since line offsets shifted from added imports
            tree = ast.parse(after_imports)
            collector = ChangeCollector(after_imports)
            lines = after_imports.split("\n")

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for arg in node.args.args:
                    if arg.arg in annotations and arg.annotation is None:
                        line_start = sum(
                            len(lines[i]) + 1 for i in range(arg.lineno - 1)
                        )
                        start = line_start + arg.col_offset
                        end = start + len(arg.arg)
                        collector.add_change(
                            start, end, f"{arg.arg}: {annotations[arg.arg]}"
                        )

            final_source = collector.get_changed()
            if final_source:
                cs = ChangeSet(f"Change <{resource.path}>")
                cs.add_change(ChangeContents(resource, final_source))
                ctx.do(cs)

    return refactor


if __name__ == "__main__":
    run(
        add_param_annotations(
            annotations={
                "capsys": "pytest.CaptureFixture[str]",
                "tmp_path": "Path",
            },
            imports={
                "capsys": NormalImport((("pytest", None),)),
                "tmp_path": FromImport("pathlib", 0, (("Path", None),)),
            },
        ),
        description="Annotate capsys and tmp_path parameters",
        setup_args=setup_args,
    )
