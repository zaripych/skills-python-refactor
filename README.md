# python-refactor

A Claude Code skill for AST-aware Python refactoring using [python-rope](https://github.com/python-rope/rope). Safer than regex for source code transformation — rope resolves references and rewrites all callers automatically.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (used to manage dependencies and run scripts)
- **Optional:** [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) for faster file pre-filtering. Falls back to `grep` if not installed.

## Installation

Clone this repository into your Claude Code skills directory:

```sh
git clone https://github.com/user/python-refactor.git ~/.claude/skills/python-refactor
```

The skill is loaded automatically when Claude Code starts. Rope itself is added as a dev dependency in your target project (`uv add --dev rope`) — the skill prompts for this when needed.

## Usage

Trigger the skill by asking Claude Code to:

- **Add type annotations** — `"annotate all cmd parameters with ServerCommandMsg"`
- **Add/reorganize imports** — `"add import pytest to all test files that use it"`
- **Rename symbols** — `"rename process_data to handle_event across the project"`
- **Move modules** — `"move utils.py into the helpers/ package"`
- **Rename modules** — `"rename parser.py to ast_parser.py"`
- **Convert module to package** — `"split models.py into a package with submodules"`
- **Remove re-exports** — `"de-export Device from __init__.py"`
- **Absolutize imports** — `"convert relative imports to absolute in the api package"`

The skill decides whether to use rope or direct edits based on scope (see [SKILL.md] for details).

## Included scripts

Scripts are run via `uv run` using a bootstrap (`scripts/rope_bootstrap.py`) that provides rope project setup, `--diff` mode, history-based undo/redo, and file selection with glob + ripgrep pre-filtering.

Each script has a companion `.md` doc with the exact workflow to follow.

| Script                  | Purpose                                              | Doc                          |
| ----------------------- | ---------------------------------------------------- | ---------------------------- |
| `move_module.py`        | Move a module/package to a new directory              | [move_module.md]             |
| `rename_module.py`      | Rename a module/package in place                      | [rename_module.md]           |
| `rename_symbol.py`      | Rename a symbol (requires line number — read first)   | [rename_symbol.md]           |
| `move_globals.py`       | Move top-level symbols between modules                | [move_globals.md]            |
| `module_to_package.py`  | Convert module to package, split into submodules      | [module_to_package.md]       |
| `deexport.py`           | Remove re-exports from `__init__.py`                  | [deexport.md]                |
| `absolutize.py`         | Convert relative imports to absolute                  | [absolutize.md]              |
| `add_param_annotations` | Batch-annotate function parameters across files       | [add_param_annotations.md]   |
| `add_imports`           | Add imports to files matching a predicate             | [add_imports.md]             |
| `refactor_history.py`   | List refactor history, undo/redo                      | —                            |

For cases these don't cover, write a custom script — see [custom_scripts.md].

## References

| File                 | Contents                                           |
| -------------------- | -------------------------------------------------- |
| [SKILL.md]           | Main skill prompt — decision table, workflows      |
| [custom_scripts.md]  | Bootstrap API, script template, RefactorContext     |
| [annotations.md]     | AST + ChangeCollector pattern for annotations      |
| [imports.md]         | ModuleImports, NormalImport, FromImport API        |
| [rope-api.md]        | Full rope API reference (Rename, Move, Extract...) |
