# rename_module

Renames a module or package in place (no directory change), rewriting all imports across the project.

## Workflow

1. **Run with `--diff`** to preview
2. **Run without `--diff`** to apply

## Usage

```bash
# Rename a file module
uv run python scripts/rename_module.py --diff src/pkg/handler.py daemon

# Rename a package
uv run python scripts/rename_module.py --diff src/pkg/handlers controllers
```

## Arguments

- `source` — path to the module file or package directory
- `new_name` — new name (without `.py` for file modules)
- `--diff` — preview mode

Use this instead of `move_module.py --rename` when the module stays in the same directory.
