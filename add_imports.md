# add_imports

Adds an import to all files matching a detection predicate. Rope handles deduplication.

## Workflow

1. **Write a detection predicate** (AST check for when the import is needed)
2. **Write a small script** using the factory (see example below)
3. **Run with `--diff`** to preview, then apply

## Example script

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

## Factory parameters

- `import_info` — `NormalImport` or `FromImport` to add
- `needs_import` — predicate returning True when file needs the import
- `include` / `exclude` — optional glob patterns
