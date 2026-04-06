# absolutize

Converts relative imports (`from .foo import bar`) to absolute imports across files. Absolute imports are never modified.

## Workflow

1. **Run with `--diff`** to preview
2. **Run without `--diff`** to apply

## Usage

```bash
# Convert all relative imports in the project
uv run python scripts/absolutize.py --diff

# Convert only specific files or directories
uv run python scripts/absolutize.py --diff src/pkg/models.py src/pkg/handlers/
```

## Arguments

- `paths` — optional files or directories to process (all project `.py` files if omitted)
- `--diff` — preview mode
