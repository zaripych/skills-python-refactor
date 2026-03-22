# Rope API Reference

Full reference for python-rope (v1.14.0). Use this to expand the python-refactor skill with new capabilities.

Source: context7 docs + installed source at `.venv/lib/python*/site-packages/rope/`.

## Table of Contents

- [Project Setup](#project-setup)
- [Resources](#resources)
- [Reading and Writing](#reading-and-writing)
- [PyModule and Scope](#pymodule-and-scope)
- [ChangeCollector](#changecollector)
- [SourceLinesAdapter](#sourcelinesadapter)
- [Import Management](#import-management)
- [Built-in Refactorings](#built-in-refactorings)
- [Change System](#change-system)
- [Multi-Project Refactoring](#multi-project-refactoring)
- [Configuration](#configuration)
- [Patched AST](#patched-ast)

---

## Project Setup

```python
from rope.base.project import Project

# Standard project
project = Project("/path/to/project")

# With custom file system commands (e.g. for VCS integration)
project = Project("/path", fscommands=MyFSCommands())

# For files outside any project
from rope.base.project import get_no_project
no_project = get_no_project()
```

### Key Project methods

```python
project.get_resource("relative/path.py")  # -> File resource
project.get_pymodule(resource)            # -> PyModule (parsed + analyzed)
project.find_module("pkg.mod")            # -> Resource or None
project.do(changes)                       # Apply a ChangeSet
project.history.undo()                    # Undo last change
project.close()                           # Cleanup
```

## Resources

```python
from rope.base import libutils

# Get resource by path
resource = project.get_resource("src/module.py")

# Or via libutils (can create for non-existent paths)
resource = libutils.path_to_resource(project, "/abs/path.py")

# Create files/folders
mod = project.root.create_file("new_module.py")
mod.write("content")

# Using generate module
from rope.contrib import generate
pkg = generate.create_package(project, "pkg")
mod = generate.create_module(project, "mod", pkg)
```

### Resource methods

```python
resource.read()           # -> str (file contents)
resource.write(content)   # Write string to file
resource.path             # Relative path from project root
resource.name             # Filename
resource.parent           # Parent folder resource
resource.exists()         # bool
```

## Reading and Writing

```python
resource = project.get_resource("file.py")
source = resource.read()      # Read file contents
resource.write(new_source)    # Write file contents
```

## PyModule and Scope

```python
pymodule = project.get_pymodule(resource)

# Source access
pymodule.source_code           # Full source string
pymodule.lines                 # SourceLinesAdapter for line indexing
pymodule.get_resource()        # The File resource

# Scope navigation
scope = pymodule.get_scope()
scope.get_kind()               # "Module", "Class", or "Function"
scope.get_defined_names()      # list[str] — names defined in this scope

# Get objects
pyobject = scope["function_name"]
# For functions:
pyobject.get_name()            # str
pyobject.get_param_names()     # list[str]
pyobject.get_ast()             # ast.FunctionDef
pyobject.get_module()          # PyModule
```

## ChangeCollector

Precise byte-offset text edits. See [annotations.md](annotations.md) for a full worked example.

```python
from rope.base.codeanalyze import ChangeCollector

collector = ChangeCollector(original_source)
collector.add_change(start_offset, end_offset, new_text)
result = collector.get_changed()  # Returns modified string, or None if no changes
```

- Changes are sorted by offset before applying — order of `add_change` calls doesn't matter
- Changes must not overlap
- `new_text` defaults to original text at `[start:end]` if `None`

## SourceLinesAdapter

Line-based indexing for source code. Located in `rope.base.codeanalyze`.

```python
from rope.base.codeanalyze import SourceLinesAdapter

lines = SourceLinesAdapter(source_code)
offset = lines.get_line_start(5)     # Byte offset of start of line 5
lineno = lines.get_line_number(100)  # Line number at byte offset 100
line_end = lines.get_line_end(5)     # Byte offset of end of line 5
```

## Import Management

See [imports.md](imports.md) for the full pattern, worked example, and gotchas.

Quick reference for the core classes:

```python
from rope.refactor.importutils.importinfo import NormalImport, FromImport
from rope.refactor.importutils.module_imports import ModuleImports
from rope.refactor.importutils import ImportOrganizer

# ModuleImports — add/inspect imports on a parsed module
# ImportOrganizer — higher-level: sort, remove unused, organize
organizer = ImportOrganizer(project)
```

## Built-in Refactorings

All refactorings follow the pattern:
1. Create refactoring object with `(project, resource, offset)`
2. Call `get_changes(...)` to compute changes
3. Call `project.do(changes)` to apply

### Rename

```python
from rope.refactor.rename import Rename

# offset = byte position of the symbol to rename
changes = Rename(project, resource, offset).get_changes("new_name")
project.do(changes)
```

### Move (MoveGlobal)

```python
from rope.refactor.move import create_move

mover = create_move(project, resource, offset)

# dest can be a Resource object or a dotted module name string
changes = mover.get_changes(dest=destination_resource)
changes = mover.get_changes(dest="pkg.subpkg.module")
project.do(changes)
```

**Prerequisites for MoveGlobal:**

1. **ModuleToPackage first** — if the source module needs to become a package (e.g. moving `fn` from `crypto.py` into `crypto/config.py`), run `ModuleToPackage` before `MoveGlobal`. You can't have both `crypto.py` and `crypto/` coexisting.

2. **`__init__.py` in intermediate directories** — rope can't resolve dotted module paths through implicit namespace packages. Without `__init__.py`, `MoveGlobal` silently falls back to a bare `import name` with no package path. Create empty `__init__.py` files before running `MoveGlobal`; they can be removed afterward if implicit namespace packages are desired at runtime.

### ModuleToPackage

Converts a single-file module into a package: `crypto.py` → `crypto/__init__.py`. Creates the directory, moves the file, and rewrites relative imports to absolute. All callers continue working unchanged.

```python
from rope.refactor.topackage import ModuleToPackage

resource = project.get_resource("src/crypto.py")
changes = ModuleToPackage(project, resource).get_changes()
project.do(changes)
```

### Extract Method/Variable

```python
from rope.refactor.extract import ExtractMethod, ExtractVariable

# Extract selection (start_offset, end_offset) into a method
extractor = ExtractMethod(project, resource, start, end)
changes = extractor.get_changes("new_method_name")
project.do(changes)
```

### Inline

```python
from rope.refactor.inline import create_inline

inliner = create_inline(project, resource, offset)
changes = inliner.get_changes()
project.do(changes)
```

### Change Signature

```python
from rope.refactor.change_signature import ChangeSignature

changer = ChangeSignature(project, resource, offset)
# Various methods to add/remove/reorder parameters
```

### Introduce Parameter

```python
from rope.refactor.introduce_parameter import IntroduceParameter

introducer = IntroduceParameter(project, resource, offset)
changes = introducer.get_changes("new_param")
project.do(changes)
```

### Restructure (pattern-based)

```python
from rope.refactor.restructure import Restructure

# Replace pattern with template
restructuring = Restructure(project, "pattern", "goal")
changes = restructuring.get_changes()
project.do(changes)
```

### Use Function

```python
from rope.refactor.usefunction import UseFunction

user = UseFunction(project, resource, offset)
changes = user.get_changes()
project.do(changes)
```

### Other refactorings

- `rope.refactor.method_object` — Convert function to class
- `rope.refactor.introduce_factory` — Create factory for class
- `rope.refactor.encapsulate_field` — Generate getters/setters
- `rope.refactor.localtofield` — Promote local to instance field

## Change System

All modifications go through the change system:

```python
from rope.base.change import ChangeSet, ChangeContents

# Atomic change group
changes = ChangeSet("Description of changes")
changes.add_change(ChangeContents(resource, new_content))
project.do(changes)

# Undo
project.history.undo()
```

### ChangeContents

```python
from rope.base.change import ChangeContents

# Replace entire file contents
change = ChangeContents(resource, new_content_string)
```

## Multi-Project Refactoring

For refactoring across multiple rope projects (monorepos):

```python
from rope.refactor.multiproject import MultiProjectRefactoring, perform
from rope.refactor.rename import Rename

# Create multi-project refactoring
# projects list should NOT include the main project
multi = MultiProjectRefactoring(Rename, [dep_project1, dep_project2])

# Create instance for main project
renamer = multi(main_project, resource, offset)

# Get changes for all projects
project_and_changes = renamer.get_all_changes("new_name")

# Apply all changes
perform(project_and_changes)
```

## Configuration

Configure via `pyproject.toml`:

```toml
[tool.rope]
split_imports = true
autoimport.aliases = [
    ["dt", "datetime"],
    ["np", "numpy"],
]

[tool.rope.imports]
# Controls how MoveGlobal rewrites imports in callers.
# "normal-import" (default) → import pkg.mod         → pkg.mod.func()
# "from-module"             → from pkg import mod     → mod.func()
# "from-global"             → from pkg.mod import func → func()
preferred_import_style = "from-global"
```

Or via `.ropeproject/config.py` (legacy).

## Patched AST

Rope's patched AST adds `.region` attributes (byte offsets) to AST nodes:

```python
from rope.refactor.patchedast import get_patched_ast

patched_tree = get_patched_ast(source, sorted_children=True)

for node in ast.walk(patched_tree):
    if isinstance(node, ast.arg):
        start, end = node.region
        print(f"Parameter source: {source[start:end]}")
```

This can be useful as an alternative to manual offset calculation from `lineno`/`col_offset`. However, for simple cases, stdlib `ast` + manual offset math is simpler and doesn't require rope's AST patching.
