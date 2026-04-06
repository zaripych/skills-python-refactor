# move_globals

Moves global symbols (classes, functions, constants) from one module to another, rewriting all imports across the project.

## Workflow

1. **Identify the symbols** to move and the destination module
2. **Order dependencies first** — if B references A and both move, list A before B
3. **Run with `--diff`** to preview
4. **Run without `--diff`** to apply

## Usage

```bash
uv run python scripts/move_globals.py \
    --diff \
    src/pkg/source.py pkg.dest.module SYMBOL1 SYMBOL2
```

## Arguments

- `source` — path to the source `.py` file
- `dest` — dotted module path for the destination (e.g. `pkg.dest.module`)
- `symbols` — one or more symbol names to move
- `--diff` — preview mode

The destination module and intermediate packages are created automatically if they don't exist.

## Symbol ordering

**Move dependencies before dependents.** If symbol B references symbol A and both are being moved, list A first. Otherwise rope adds a temporary import that becomes stale.
