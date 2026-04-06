# rename_symbol

Renames a symbol (function, class, constant) in place, rewriting all imports and references across the project. Requires both symbol name and line number to anchor unambiguously — avoids matching shadowed or re-exported symbols.

## Workflow

1. **Read the source file** to find the symbol and its line number
2. **Run with `--diff`** to preview
3. **Run without `--diff`** to apply

## Usage

```bash
uv run python scripts/rename_symbol.py \
    --diff \
    src/pkg/module.py 11 old_name new_name
```

## Arguments

- `source` — path to the `.py` file containing the symbol
- `line` — line number of the symbol definition (anchors the rename)
- `old_name` — current name of the symbol
- `new_name` — desired new name
- `--diff` — preview mode
