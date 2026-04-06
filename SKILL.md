---
name: python-refactor
description: "Perform AST-aware Python refactors using the rope library. Handles parameter annotations, import management, rename, move, module-to-package conversion, de-re-export, relative-to-absolute import conversion, and custom source transformations with precise offset edits. Triggers: 'add type annotations', 'refactor with rope', 'python refactor skill', 'add imports', 'rename across files', 'rename package', 'annotate parameters', 'remove re-exports', 'de-export', 'absolutize imports', 'relative to absolute', 'module to package', 'split module', or needs AST-aware Python source code transformation."
---

# Python Refactor

Use python-rope for AST-aware Python refactoring. Rope provides precise offset editing, import management, and cross-file rename/move — safer than regex for source code transformation.

## Script location

All scripts live in this skill's `scripts/` directory — **not** in the target project. Commands in the docs use relative paths like `scripts/move_module.py` for brevity. When running them, resolve relative to this skill's base directory:

```
SKILL_DIR=<this skill's base directory>
uv run python "$SKILL_DIR/scripts/move_module.py" ...
```

## Prerequisites

Rope must be a dev dependency: `uv add --dev rope`

## When to use rope vs direct edits

Use rope scripts when the refactor touches imports or symbols across multiple files — rope resolves references and rewrites all callers automatically. Use direct Edit tool or regex when changes are localized (≤3 files, confirm with grep!) or non-Python.

## Project structure and rope configuration

Rope auto-detects source folders. A folder containing a package (subfolder with `__init__.py`) or `.py` files is a source folder. For `src/` layouts, `src/` is auto-detected — no config needed.

Set `preferred_import_style` in `pyproject.toml`:

```toml
[tool.rope.imports]
preferred_import_style = "from-global"
```

**Important:** source folder roots (like `src/`) must never contain an `__init__.py`.

## Available scripts

Each script has a companion `.md` file with the exact workflow to follow. **Read the companion doc before running a script.**

| Script                  | What it does                                             | Doc                                                  |
| ----------------------- | -------------------------------------------------------- | ---------------------------------------------------- |
| `move_module.py`        | Move a module/package to a new directory                 | [move_module.md](move_module.md)                     |
| `rename_module.py`      | Rename a module/package in place                         | [rename_module.md](rename_module.md)                 |
| `rename_symbol.py`      | Rename a symbol (requires line number — read file first) | [rename_symbol.md](rename_symbol.md)                 |
| `move_globals.py`       | Move globals between modules                             | [move_globals.md](move_globals.md)                   |
| `module_to_package.py`  | Convert module to package, split globals into submodules | [module_to_package.md](module_to_package.md)         |
| `deexport.py`           | Remove re-exports from `__init__.py`                     | [deexport.md](deexport.md)                           |
| `absolutize.py`         | Convert relative imports to absolute                     | [absolutize.md](absolutize.md)                       |
| `add_param_annotations` | Add type annotations to parameters in bulk               | [add_param_annotations.md](add_param_annotations.md) |
| `add_imports`           | Add imports to files matching a predicate                | [add_imports.md](add_imports.md)                     |
| `refactor_history.py`   | List refactor history, undo/redo                         | See below                                            |

## Refactor history

```bash
uv run python scripts/refactor_history.py list   # show history and undo/redo usage
```

## Custom refactoring scripts

If none of the existing scripts fit, write a custom one. See [custom_scripts.md](custom_scripts.md) — MANDATORY when writing any refactor script.

## References

| File                                   | Load                                           |
| -------------------------------------- | ---------------------------------------------- |
| [custom_scripts.md](custom_scripts.md) | MANDATORY when writing any refactor script     |
| [annotations.md](annotations.md)       | MANDATORY when writing custom annotation logic |
| [imports.md](imports.md)               | MANDATORY when writing custom import logic     |
| [rope-api.md](rope-api.md)             | Optional — for built-in rope refactorings      |

## Keywords

rope, refactor, python, AST, annotations, type annotations, imports, rename, rename module, rename package, move, module to package, split module, source transformation, code modification, re-export, deexport, absolutize, relative imports, lazy imports, **init**.py
