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

The skill decides whether to use rope or direct edits based on scope (see [SKILL.md](SKILL.md) for details).
