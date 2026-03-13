---
name: rope-refactor
description: Perform AST-aware Python refactors using the rope library. Handles parameter annotations, import management, rename, move, and custom source transformations with precise byte-offset edits. Triggers: "add type annotations", "refactor with rope", "rope refactor skill", "rope refactor tool", "add imports", "rename across files", "annotate parameters", or needs AST-aware Python source code transformation.
---

# Rope Refactor

Use python-rope for AST-aware Python refactoring. Rope provides precise byte-offset editing, import management, and cross-file rename/move — safer than regex for source code transformation.

## Prerequisites

Rope must be a dev dependency: `uv add --dev rope`

## When to use rope vs direct edits

| Scenario                              | Use                                             |
| ------------------------------------- | ----------------------------------------------- |
| Same param name across **>3 files**   | Rope script (batch, safe)                       |
| ≤3 files, any number of occurrences   | Direct Edit tool (faster, no script overhead)   |
| Add/remove/reorganize imports in bulk | Rope (`ModuleImports` handles dedup, placement) |
| Rename symbol across files            | Rope (resolves all references)                  |
| Simple literal string replacement     | Regex is fine                                   |
| Non-Python files                      | Regex                                           |

**Key threshold:** Count distinct _files_, not total occurrences. A param appearing 40 times across 10 files → rope script. A param appearing 3 times in 2 files → direct edits.

## Built-in refactorings

Rope's built-in refactorings need a byte offset. Never count bytes manually — use a line number (from the Read tool) + symbol name, then resolve to an offset in the script:

```python
import sys
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
from rope_bootstrap import run, RefactorContext
from rope.refactor.rename import Rename

def setup_args(parser):
    parser.add_argument("file", type=Path)
    parser.add_argument("line", type=int, help="Line number (1-based, from Read tool)")
    parser.add_argument("symbol", help="Symbol name to find on that line")
    parser.add_argument("new_name")

def refactor(ctx: RefactorContext) -> None:
    resource = ctx.get_resource(ctx.args.file)
    source = resource.read()
    # Resolve line + symbol name → byte offset
    lines = source.split("\n")
    line_start = sum(len(lines[i]) + 1 for i in range(ctx.args.line - 1))
    col = lines[ctx.args.line - 1].index(ctx.args.symbol)
    offset = line_start + col
    changes = Rename(ctx.project, resource, offset).get_changes(ctx.args.new_name)
    ctx.do(changes)

run(refactor, description="Rename symbol", setup_args=setup_args)
```

Available: Rename, Move, ExtractMethod, ExtractVariable, Inline, ChangeSignature, IntroduceParameter, Restructure, UseFunction, MethodObject, IntroduceFactory, EncapsulateField, LocalToField, ToPackage.

See [rope-api.md](rope-api.md) for full usage details.

## Adding type annotations to parameters

**Prefer reusing `add_param_annotations`** over writing new scripts. The factory handles rg pre-filtering, AST walking, import insertion, and byte-offset annotation in one call.

All scripts MUST use the bootstrap. See [custom_scripts.md](custom_scripts.md) — MANDATORY when writing any refactor script.

```python
import sys
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
from add_param_annotations import add_param_annotations
from rope_bootstrap import run
from rope.refactor.importutils.importinfo import FromImport

def setup_args(parser):
    parser.add_argument("directory", type=Path)

run(
    add_param_annotations(
        annotations={"cmd": "server_pb2.ServerCommandMsg"},
        imports={"cmd": FromImport("mylib.protobuf", 0, (("server_pb2", None),))},
        exclude=["test_protocol.py"],
    ),
    description="Annotate cmd parameters",
    setup_args=setup_args,
)
```

Parameters:

- `annotations` — `dict[str, str]`: param name → annotation string
- `imports` — optional `dict[str, ImportInfo]`: param name → rope import (omit for builtins like `str`, `int`)
- `include` — optional `list[str]`: glob patterns to include (default: all `**/*.py`)
- `exclude` — optional `list[str]`: glob patterns to exclude (applied after include)

See [annotations.md](annotations.md) — MANDATORY when writing custom annotation logic (not needed when reusing the factory).

## Adding imports

**Prefer reusing `add_import`** over writing new scripts. The factory adds an import to all files matching a detection predicate:

```python
import ast
import sys
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
from add_imports import add_import
from rope_bootstrap import run
from rope.refactor.importutils.importinfo import NormalImport

def _uses_pytest(tree: ast.Module) -> bool:
    return any(
        isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id == "pytest"
        for n in ast.walk(tree)
    )

def setup_args(parser):
    parser.add_argument("directory", type=Path)

run(
    add_import(NormalImport((("pytest", None),)), _uses_pytest),
    description="Add import pytest where needed",
    setup_args=setup_args,
)
```

Parameters:

- `import_info` — `NormalImport` or `FromImport` to add
- `needs_import` — `NeedsImportFn` protocol: predicate that returns True when the file needs the import
- `include` — optional `list[str]`: glob patterns to include (default: all `**/*.py`)
- `exclude` — optional `list[str]`: glob patterns to exclude (applied after include)

Rope handles deduplication — the import won't be added if already present.

See [imports.md](imports.md) — MANDATORY when writing custom import logic.

## File selection

Use `ctx.find_files()` to select files. It combines glob matching with optional text pre-filtering (via ripgrep, falling back to grep):

```python
# All .py files in directory
files = ctx.find_files(directory)

# Only files containing "cmd" or "send", filtered by globs
files = ctx.find_files(
    directory,
    patterns={"cmd", "send"},
    include=["tests/**/*.py"],
    exclude=["conftest.py"],
)
```

When `patterns` is provided, only files containing a match are included. The result is always intersected with include/exclude globs. Logs which tool was used, how many files matched, and how many were excluded.

## References

| File                                   | Contents                                                                                         | Load                                           |
| -------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| [custom_scripts.md](custom_scripts.md) | Bootstrap usage, RefactorContext API (match_globs, grep_files, write, do), built-in refactorings | MANDATORY when writing any refactor script     |
| [annotations.md](annotations.md)       | AST + ChangeCollector pattern for custom annotation logic                                        | MANDATORY when writing custom annotation logic |
| [imports.md](imports.md)               | ModuleImports, NormalImport, FromImport API                                                      | MANDATORY when writing custom import logic     |
| [rope-api.md](rope-api.md)             | Full rope API reference (Rename, Move, Extract, etc.)                                            | Optional — for built-in refactorings           |

## Keywords

rope, refactor, python, AST, annotations, type annotations, imports, rename, move, source transformation, code modification
