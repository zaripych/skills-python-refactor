# Adding Imports with Rope

## Pattern

Use `ModuleImports` for AST-aware import insertion. Rope handles:
- Deduplication (won't add `import pytest` if already present)
- Multi-line import detection (won't split `from foo import (\n  a,\n  b\n)`)
- Proper placement (after existing imports, respecting grouping)
- Indented imports (ignores `from x import y` inside function bodies)

## Core API

```python
from rope.refactor.importutils.module_imports import ModuleImports
from rope.refactor.importutils.importinfo import NormalImport, FromImport
```

### NormalImport

For `import x` statements:

```python
# import pytest
NormalImport((("pytest", None),))

# import numpy as np
NormalImport((("numpy", "np"),))

# import os, sys
NormalImport((("os", None), ("sys", None)))
```

Constructor: `NormalImport(names_and_aliases)` where `names_and_aliases` is a tuple of `(module_name, alias_or_None)` tuples.

### FromImport

For `from x import y` statements:

```python
# from pathlib import Path
FromImport("pathlib", 0, (("Path", None),))

# from pathlib import Path, PurePath
FromImport("pathlib", 0, (("Path", None), ("PurePath", None)))

# from . import utils  (relative import, level=1)
FromImport("", 1, (("utils", None),))

# from ..models import User  (relative import, level=2)
FromImport("models", 2, (("User", None),))
```

Constructor: `FromImport(module_name, level, names_and_aliases)` where:
- `module_name`: the module path (empty string for bare relative imports)
- `level`: 0 for absolute, 1 for `.`, 2 for `..`, etc.
- `names_and_aliases`: tuple of `(name, alias_or_None)` tuples

### ModuleImports

Operates on a parsed module to add/inspect imports:

```python
pymodule = ctx.project.get_pymodule(resource)
module_imports = ModuleImports(ctx.project, pymodule)
module_imports.add_import(NormalImport((("pytest", None),)))
module_imports.add_import(FromImport("pathlib", 0, (("Path", None),)))

new_source = module_imports.get_changed_source()
```

`add_import` is smart:
- If `from pathlib import PurePath` exists and you add `FromImport("pathlib", 0, (("Path", None),))`, rope merges them into `from pathlib import PurePath, Path`
- If `import pytest` already exists, it's a no-op

## Worked example

For most import tasks, use the `add_import` factory directly — see SKILL.md for usage.

Full implementation: [scripts/add_imports.py](scripts/add_imports.py)
Tests: [scripts/tests/test_add_imports.py](scripts/tests/test_add_imports.py)

## Combining with other edits

When adding imports AND making other source changes (e.g. annotations), always:

1. **Add imports first** — this shifts line numbers
2. **Re-parse the import-modified source** — AST offsets must match
3. **Apply remaining edits** to the post-import source
4. **Queue write once** at the end via `ctx.write()`

```python
# Step 1: imports
after_imports = module_imports.get_changed_source()

# Step 2: re-parse
tree = ast.parse(after_imports)
collector = ChangeCollector(after_imports)
# ... add annotation changes ...

# Step 3: queue write
final = collector.get_changed()
if final:
    ctx.write(resource, final)
```

## Gotchas

- `get_changed_source()` returns the original source unchanged if no imports were added (safe to compare with `!=`).
- `ModuleImports` requires a `pymodule` from `project.get_pymodule(resource)`, not just the raw source string.
- Rope may adjust whitespace around the import block (e.g. blank lines). Run your formatter after if needed.
