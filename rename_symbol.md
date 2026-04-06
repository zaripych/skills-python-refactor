# rename_symbol

Renames a symbol (function, class, constant) in place, rewriting all imports and references across the project.

**Important:** Requires the **line number** of the symbol definition — you must read the source file first to find it. The line number anchors the rename unambiguously so it won't match shadowed or re-exported symbols with the same name.

## Workflow

1. **Read the source file** to find the symbol definition and note its **line number**
2. **Run with `--diff`** to preview — pass the line number as the second positional argument
3. **Run without `--diff`** to apply

## Usage

```bash
# Line 11 of module.py contains: def old_name(...) or class old_name(...) etc.
uv run python scripts/rename_symbol.py \
    --diff \
    src/pkg/module.py 11 old_name new_name
```

## Arguments

- `source` — path to the `.py` file containing the symbol
- `line` — **(required)** line number of the symbol definition (anchors the rename)
- `old_name` — current name of the symbol
- `new_name` — desired new name
- `--diff` — preview mode
