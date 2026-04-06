# move_module

Moves a Python module or package to a different directory, rewriting all imports across the project.

## Workflow

1. **Run with `--diff`** to preview the move and import rewrites
2. **Run without `--diff`** to apply

## Usage

```bash
# Move a single module
uv run python scripts/move_module.py \
    --diff \
    src/pkg/handlers/status.py \
    src/pkg/features/status/daemon \
    --rename handler

# Move an entire package
uv run python scripts/move_module.py \
    --diff \
    src/pkg/services/tasks \
    src/pkg/api
```

## Arguments

- `source` — path to a module file or package directory
- `dest_dir` — destination directory (relative to project root)
- `--rename` — optional new name (without `.py`)
- `--diff` — preview mode

Destination directories and intermediate `__init__.py` files are created automatically.
