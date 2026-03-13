# Writing Custom Refactor Scripts

All refactor scripts MUST use [scripts/rope_bootstrap.py](scripts/rope_bootstrap.py). It provides project setup, `--dry-run`, `--diff`, `--backup`, git safety checks, and the `RefactorContext` with file selection helpers.

## Script template

```python
import sys
from argparse import ArgumentParser
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"  # use the actual skill path
sys.path.insert(0, SKILL_SCRIPTS)
from rope_bootstrap import RefactorContext, run

def setup_args(parser: ArgumentParser) -> None:
    parser.add_argument("directory", type=Path, help="Directory to scan")

def refactor(ctx: RefactorContext) -> None:
    for f in sorted(ctx.args.directory.rglob("*.py")):
        resource = ctx.get_resource(f)
        source = resource.read()
        # ... compute new_source ...
        ctx.write(resource, new_source)

if __name__ == "__main__":
    run(refactor, description="My refactor script", setup_args=setup_args)
```

**IMPORTANT:** The `sys.path.insert` line MUST use the absolute path to this skill's `scripts/` directory so `rope_bootstrap` and other skill modules can be imported. Use the actual resolved path, e.g. `/Users/me/.claude/skills/python-refactor/scripts`.

## Bootstrap CLI flags

The bootstrap provides these flags automatically — no need to add them:

- `--project-root` (required) — rope project root (repository root)
- `--dry-run` — show what would change without modifying files
- `--diff` — show unified diff (implies `--dry-run`)
- `--backup` — create `.bak` files before writing (for non-git repos)

Each refactor script adds its own args via `setup_args`. Access all parsed args through `ctx.args`.

**Always run with `--dry-run` first**, then apply.

## RefactorContext API

### File selection

```python
# All .py files in directory (no text filter)
files = ctx.find_files(directory)

# Only files containing "cmd" or "send", filtered by globs
files = ctx.find_files(
    directory,
    patterns={"cmd", "send"},
    include=["tests/**/*.py"],
    exclude=["conftest.py"],
)
```

When `patterns` is provided, files are pre-filtered with ripgrep (falling back to grep), then intersected with include/exclude globs. Without `patterns`, only glob filtering is applied.

### Reading and writing

```python
resource = ctx.get_resource(file_path)   # Path → rope File resource
source = resource.read()                 # current source text

ctx.write(resource, new_source)          # queue a change (never call resource.write())
ctx.do(changes)                          # apply a rope Change (Rename, Move, etc.)
```

`ctx.write()` uses an in-memory overlay — subsequent reads see prior writes without touching disk until `commit()`.

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
