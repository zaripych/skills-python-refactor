---
name: python-refactor
description: Perform AST-aware Python refactors using the rope library. Handles parameter annotations, import management, rename, move, de-re-export, relative-to-absolute import conversion, and custom source transformations with precise offset edits. Triggers: "add type annotations", "refactor with rope", "python refactor skill", "python refactor tool", "add imports", "rename across files", "annotate parameters", "remove re-exports", "de-export", "absolutize imports", "relative to absolute", or needs AST-aware Python source code transformation.
---

# Python Refactor

Use python-rope for AST-aware Python refactoring. Rope provides precise offset editing, import management, and cross-file rename/move — safer than regex for source code transformation.

## Prerequisites

Rope must be a dev dependency: `uv add --dev rope`

## When to use rope vs direct edits

| Scenario                              | Use                                             |
| ------------------------------------- | ----------------------------------------------- |
| Same param name across **>3 files**   | Rope script (batch, safe)                       |
| ≤3 files, any number of occurrences   | Direct Edit tool (faster, no script overhead)   |
| Add/remove/reorganize imports in bulk | Rope (`ModuleImports` handles dedup, placement) |
| Remove `__init__.py` re-exports       | Rope (`deexport.py` — resolves + rewrites)      |
| Convert relative to absolute imports  | Rope (`absolutize.py` — batch conversion)        |
| Rename symbol across files            | Rope (resolves all references)                  |
| Simple literal string replacement     | Regex is fine                                   |
| Non-Python files                      | Regex                                           |

**Key threshold:** Count distinct _files_, not total occurrences. A param appearing 40 times across 10 files → rope script. A param appearing 3 times in 2 files → direct edits.

## Project structure and rope configuration

Rope auto-detects source folders by walking the directory tree. A folder that directly contains a package (a subfolder with `__init__.py`) is treated as a source folder. A folder with `.py` files but no packages is also treated as a source folder.

For an idiomatic Python layout:

```
myproject/
  pyproject.toml
  src/
    myapp/
      __init__.py
      models.py
      handlers/
        __init__.py
        status.py
  tests/
    test_models.py
```

Rope auto-detects `src/` as a source folder (because it contains `myapp/` which has `__init__.py`) and `tests/` as a source folder (because it contains `.py` files). This means `src/myapp/models.py` resolves as `myapp.models`.

No `source_folders` configuration is needed for this layout. However, `preferred_import_style` should be set to control how rope writes new imports:

```toml
[tool.rope.imports]
preferred_import_style = "from-global"
```

Without this, rope defaults to normal imports (`import myapp.models`) instead of from-imports (`from myapp.models import DeviceInfo`).

**Important:** source folder roots (like `src/`) must never contain an `__init__.py` file. If they do, rope treats them as packages and generates prefixed imports like `src.myapp.models`. The bootstrap's `ensure_package` automatically skips `__init__.py` creation for directories listed in `source_folders`.

## Bootstrap flags

All scripts inherit these flags from the bootstrap — no need to add them manually:

- `--project-root` — rope project root (defaults to git repository root, so usually omitted)
- `--dry-run` — show what would change without modifying files
- `--diff` — show unified diff (implies `--dry-run`)

## Built-in refactorings

Rope's built-in refactorings need a string offset. Never count offsets manually — use rope's `SourceLinesAdapter` (available as `pymodule.lines`) to convert a line number + symbol name to an offset:

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
    pymodule = ctx.project.get_pymodule(resource)
    source = resource.read()
    # Resolve line + symbol name → offset
    line_start = pymodule.lines.get_line_start(ctx.args.line)
    offset = line_start + source[line_start:].index(ctx.args.symbol)
    changes = Rename(ctx.project, resource, offset).get_changes(ctx.args.new_name)
    ctx.do(changes)

run(refactor, description="Rename symbol", setup_args=setup_args)
```

Available: Rename, Move, ExtractMethod, ExtractVariable, Inline, ChangeSignature, IntroduceParameter, Restructure, UseFunction, MethodObject, IntroduceFactory, EncapsulateField, LocalToField, ToPackage.

See [rope-api.md](rope-api.md) for full usage details.

## Adding type annotations to parameters

**Prefer reusing `add_param_annotations`** over writing new scripts. The factory handles rg pre-filtering, AST walking, import insertion, and offset-based annotation in one call.

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

## Moving modules between directories

**Prefer reusing `move_module`** over writing custom move scripts. It handles directory creation, import rewriting across the project, and optional rename in one operation:

```bash
uv run python scripts/move_module.py \
    --diff \
    src/pkg/handlers/status.py \
    src/pkg/features/status/daemon \
    --rename handler
```

Parameters:

- `source` — path to the module file to move
- `dest_dir` — destination directory (relative to project root)
- `--rename` — optional new name for the module (without `.py`)
- `--diff` — show unified diff without applying (implies `--dry-run`)
- `--dry-run` — show what would change without modifying files

The destination directory and intermediate `__init__.py` files are created automatically as scaffolding for rope's import resolution. Scaffolding is cleaned up after the operation — only the moved file and updated imports persist.

**Import rewriting:** All `from` and `import` statements across the project are updated to reflect the new location.

## Moving globals between modules

**Prefer reusing `move_globals`** over writing custom move scripts. It handles batch moves with upfront validation, automatic stale import cleanup in the destination, and caller rewriting:

```python
import sys
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
from move_globals import refactor, setup_args
from rope_bootstrap import run

run(refactor, description="Move symbols", setup_args=setup_args)
```

Or invoke directly:

```bash
uv run python scripts/move_globals.py \
    --diff \
    src/pkg/source.py pkg.dest.module SYMBOL1 SYMBOL2
```

The destination module and intermediate packages are created automatically if they don't exist. Intermediate `__init__.py` files are scaffolded for rope's import resolution and cleaned up after the operation.

**Symbol order matters:** Move dependencies before dependents. If symbol B references symbol A and both are being moved, list A first. Otherwise rope adds a temporary import of A from the source into the destination, which becomes stale once A moves.

**Stale import cleanup:** Before each move, the script checks if the destination already imports the symbol and removes it to prevent circular imports.

**Validation:** All symbols are validated as locally defined (not imported) in the source before any changes are made.

**Undo/redo:** Each refactor run is tagged with a state hash. Use `refactor_history.py undo` to reverse the most recent run, or `refactor_history.py redo` to reapply a previously undone run.

## Removing re-exports from `__init__.py`

**Prefer reusing `deexport`** to eliminate re-exports. It resolves each re-exported symbol to its defining module, rewrites all callers to import directly from the source, then removes the re-export lines from `__init__.py`:

```bash
# De-export all re-exported symbols from a package
uv run python scripts/deexport.py \
    --diff \
    src/pkg/handlers/

# De-export only specific symbols
uv run python scripts/deexport.py \
    --diff \
    src/pkg/handlers/ StatusCommand DeviceInfo
```

Parameters:

- `package_path` — path to `__init__.py` or its parent directory
- `symbols` — optional list of specific symbols to de-export (all re-exports if omitted)

The script:
1. Parses `__init__.py` to build a map of re-exported symbol → source module (via `ImportedName.get_definition_location()`)
2. Finds all callers via rope's `find_occurrences` (catches both absolute and relative imports)
3. Rewrites callers to import from the source module directly
4. Removes the re-export lines from `__init__.py` and cleans up `__all__`

Re-exported names that are also used locally in `__init__.py` (e.g. referenced in function bodies) are kept as imports but still de-exported from the public API. Handles aliased imports, mixed imports, nested packages, and relative imports pointing to the package.

## Converting relative imports to absolute

**Prefer reusing `absolutize`** to convert relative imports to absolute. Only touches explicit relative imports (`from .foo import bar`, `from ..models import X`) — absolute imports are never modified:

```bash
# Convert all relative imports in the project
uv run python scripts/absolutize.py --diff

# Convert only specific files or directories
uv run python scripts/absolutize.py --diff src/pkg/models.py src/pkg/handlers/
```

Parameters:

- `paths` — optional files or directories to process (all project `.py` files if omitted)

Resolves the absolute module name from the resource path relative to source folders, handling namespace packages (directories without `__init__.py`). Works across all source folders including `tests/`.

## Undo / Redo

All changes applied via `ctx.do()` are tracked through rope's history with state hash tagging. A single script manages both undo and redo:

- **`refactor_history.py undo`** — undoes the most recent refactor run by hash.
- **`refactor_history.py redo`** — redoes a previously undone run.

```bash
# Undo the last refactor
uv run python scripts/refactor_history.py undo

# Redo a previously undone refactor
uv run python scripts/refactor_history.py redo
```

## Custom refactoring scripts

If none of the existing solutions fit, a custom refactor script can be created. All scripts MUST use the bootstrap though. See [custom_scripts.md](custom_scripts.md) — MANDATORY when writing any refactor script.

## File selection

Use `ctx.find_files()` to select files. It combines glob matching with optional text pre-filtering (via ripgrep, falling back to grep):

```python
# All .py files in the project
files = ctx.find_files()

# Only files containing "cmd" or "send", filtered by globs
files = ctx.find_files(
    patterns={"cmd", "send"},
    include=["tests/**/*.py"],
    exclude=["conftest.py"],
)
```

Searches from the project root. When `patterns` is provided, only files containing a match are included. The result is always intersected with include/exclude globs. Logs which tool was used, how many files matched, and how many were excluded.

## References

| File                                   | Contents                                                                                         | Load                                           |
| -------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| [custom_scripts.md](custom_scripts.md) | Bootstrap usage, RefactorContext API (find_files, do), ChangeSet pattern, built-in refactorings   | MANDATORY when writing any refactor script     |
| [annotations.md](annotations.md)       | AST + ChangeCollector pattern for custom annotation logic                                        | MANDATORY when writing custom annotation logic |
| [imports.md](imports.md)               | ModuleImports, NormalImport, FromImport API                                                      | MANDATORY when writing custom import logic     |
| [rope-api.md](rope-api.md)             | Full rope API reference (Rename, Move, Extract, etc.)                                            | Optional — for built-in refactorings           |
| `move_module.py`                       | Move a module to a new directory, rewriting all imports. Supports `--rename`.                     | Run directly from CLI                          |
| `move_globals.py`                      | Move global symbols between modules with stale import cleanup                                    | Run directly from CLI                          |
| `deexport.py`                          | Remove re-exports from `__init__.py`, rewrite callers to import from source modules              | Run directly from CLI                          |
| `absolutize.py`                        | Convert relative imports to absolute across files                                                | Run directly from CLI                          |
| `refactor_history.py`                  | Undo/redo refactor runs by state hash (`undo` or `redo` subcommand)                              | Run after a refactor to reverse or reapply     |

## Keywords

rope, refactor, python, AST, annotations, type annotations, imports, rename, move, source transformation, code modification, re-export, deexport, absolutize, relative imports, __init__.py
