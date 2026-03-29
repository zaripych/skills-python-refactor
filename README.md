# python-refactor

A Claude Code skill for AST-aware Python refactoring using [python-rope](https://github.com/python-rope/rope). Safer than regex for source code transformation — handles parameter annotations, import management, rename, move, and custom batch edits with precise offset editing.

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
- **Batch refactors** — `"refactor with rope"` or `"python refactor tool"`

The skill decides whether to use rope or direct edits based on scope (see the threshold table in SKILL.md).

## How it works

Refactor scripts are run via `uv run` using a bootstrap (`scripts/rope_bootstrap.py`) that provides:

- Rope project setup and resource management
- `--dry-run` and `--diff` modes (always runs dry first)
- Changes written via rope's history with automatic undo/redo support
- File selection with glob + text pre-filtering (ripgrep, with grep fallback)

## Included tools

| Script / Factory         | Purpose                                        |
| ------------------------ | ---------------------------------------------- |
| `add_param_annotations`  | Batch-annotate function parameters across files |
| `add_import`             | Add imports to files matching a predicate       |
| `move_globals`           | Move top-level symbols between modules          |
| `move_module`            | Move or rename a module (MoveModule)            |
| `refactor_history`       | Undo or redo a refactor run by state hash        |

For cases these don't cover, write a custom script — see `custom_scripts.md`.

## Skill docs

| File                | Contents                                           |
| ------------------- | -------------------------------------------------- |
| `SKILL.md`          | Main skill prompt — decision table, examples       |
| `custom_scripts.md` | Bootstrap API, script template, RefactorContext     |
| `annotations.md`    | AST + ChangeCollector pattern for annotations      |
| `imports.md`        | ModuleImports, NormalImport, FromImport API        |
| `rope-api.md`       | Full rope API reference (Rename, Move, Extract...) |
