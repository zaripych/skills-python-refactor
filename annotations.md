# Adding Type Annotations with Rope

## Preferred approach: reuse the factory

For most annotation tasks, use `add_param_annotations` directly — see SKILL.md for usage. Only write custom annotation logic when the factory doesn't cover your case (e.g. conditional annotations based on function context).

Full implementation: [scripts/add_param_annotations.py](scripts/add_param_annotations.py)

## Pattern (custom logic)

Use `ast.walk` for parameter detection + `ChangeCollector` for byte-offset replacement. This avoids the regex pitfalls of matching parameter names in function bodies.

## Why AST over regex

Regex approaches fail when:
- The same name appears in the function body (e.g. `str(tmp_path)` gets annotated)
- Parameters span multiple lines in signatures
- Nested functions have indented `def` lines that confuse signature detection

AST parsing eliminates all of these — `ast.arg` nodes only exist in function signatures.

## Core API

```python
import ast
from rope.base.codeanalyze import ChangeCollector
```

### ChangeCollector

Accumulates precise byte-offset edits and applies them in one pass:

```python
collector = ChangeCollector(source)
collector.add_change(start_offset, end_offset, replacement_text)
new_source = collector.get_changed()  # returns None if no changes
```

Changes are sorted by offset and applied without overlap — safe for multiple edits.

### Converting AST positions to byte offsets

`ast.arg` provides `lineno` (1-based) and `col_offset` (0-based). Convert to byte offset:

```python
lines = source.split("\n")
line_start = sum(len(lines[i]) + 1 for i in range(arg.lineno - 1))
start = line_start + arg.col_offset
end = start + len(arg.arg)
```

## Worked example

See [scripts/add_param_annotations.py](scripts/add_param_annotations.py) for the factory implementation. It supports:

- `annotations` — param name → annotation string
- `imports` — param name → rope ImportInfo (optional, omit for builtins)
- `include` / `exclude` — glob patterns for file selection (optional)
- Text pre-filter — skips files not containing any target param name

Tests: [scripts/tests/test_add_param_annotations.py](scripts/tests/test_add_param_annotations.py)

## Key lessons learned

1. **Add imports first, then annotate.** Import insertion shifts line offsets. Re-parse after imports so AST positions are correct for annotation edits.
2. **Write once at the end.** Compute all changes in memory, apply together. Avoids multiple disk writes and re-indexing.
3. **`ChangeCollector.get_changed()` returns `None` when empty.** Always check before using the result.
4. **`ast.walk` visits all nesting levels.** It catches parameters in nested functions, lambdas, and class methods — no manual nesting tracking needed.
5. **Pre-filter with text search.** Before AST parsing, check if the file text contains the param name. This avoids expensive parsing for files that can't possibly match.
