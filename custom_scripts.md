# Writing Custom Refactor Scripts

All refactor scripts MUST use [scripts/rope_bootstrap.py](scripts/rope_bootstrap.py). It provides project setup, `--dry-run`, `--diff`, git safety checks, and the `RefactorContext` with file selection helpers.

## Script template

```python
import sys
from argparse import ArgumentParser
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"  # use the actual skill path
sys.path.insert(0, SKILL_SCRIPTS)
from rope_bootstrap import RefactorContext, run
from rope.refactor.rename import Rename

def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="Source file")

def refactor(ctx: RefactorContext) -> None:
    resource = ctx.get_resource(ctx.args.source)
    pymodule = ctx.project.get_pymodule(resource)
    source = resource.read()
    line_start = pymodule.lines.get_line_start(line_number)
    offset = line_start + source[line_start:].index("symbol_name")
    changes = Rename(ctx.project, resource, offset).get_changes("new_name")
    ctx.do(changes)

if __name__ == "__main__":
    run(refactor, description="My refactor script", setup_args=setup_args)
```

**IMPORTANT:** The `sys.path.insert` line MUST use the absolute path to this skill's `scripts/` directory so `rope_bootstrap` and other skill modules can be imported. Use the actual resolved path, e.g. `/Users/me/.claude/skills/python-refactor/scripts`.

## Bootstrap CLI flags

The bootstrap provides these flags automatically — no need to add them:

- `--project-root` (optional) — rope project root (defaults to git repository root)
- `--dry-run` — show what would change without modifying files
- `--diff` — show unified diff (implies `--dry-run`)

Each refactor script adds its own args via `setup_args`. Access all parsed args through `ctx.args`.

**Always run with `--dry-run` first**, then apply.

## RefactorContext API

### File selection

Use `ctx.find_files()` for file selection — see SKILL.md for usage and parameters.

### Reading and writing

```python
resource = ctx.get_resource(file_path)   # Path → rope File resource
source = resource.read()                 # current source text

# Build a ChangeSet and apply it — changes write to disk immediately via rope's history
from rope.base.change import ChangeSet, ChangeContents
cs = ChangeSet("description")
cs.add_change(ChangeContents(resource, new_source))
ctx.do(cs)                               # apply changes (writes to disk, tagged for undo)
```

Each `ctx.do()` call writes to disk immediately through `project.do()` and tags the change with a state hash for undo/redo support. Use `refactor_history.py undo` and `refactor_history.py redo` to reverse or reapply changes after a run.

### Project access

```python
ctx.project           # the rope Project instance
ctx.args              # parsed CLI args (bootstrap + script-specific)
ctx.dry_run           # True if --dry-run or --diff
```

## Rename, move, and other built-in refactorings

Use `ctx.do()` to apply rope's built-in refactorings:

```python
from rope.refactor.rename import Rename

def refactor(ctx: RefactorContext) -> None:
    resource = ctx.get_resource(some_path)
    # offset = byte position of the symbol to rename
    changes = Rename(ctx.project, resource, offset).get_changes("new_name")
    ctx.do(changes)
```

Available: Rename, Move, ExtractMethod, ExtractVariable, Inline, ChangeSignature, IntroduceParameter, Restructure, UseFunction, MethodObject, IntroduceFactory, EncapsulateField, LocalToField, ToPackage.

See [rope-api.md](rope-api.md) for full usage details.
