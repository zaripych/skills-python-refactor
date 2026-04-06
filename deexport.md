# deexport

Removes re-exports from `__init__.py`, rewrites all callers to import directly from the source module.

## Workflow

1. **Run with `--diff`** to preview which callers get rewritten
2. **Run without `--diff`** to apply

## Usage

```bash
# De-export all re-exported symbols from a package
uv run python scripts/deexport.py --diff src/pkg/handlers/

# De-export only specific symbols
uv run python scripts/deexport.py --diff src/pkg/handlers/ StatusCommand DeviceInfo
```

## Arguments

- `package_path` — path to `__init__.py` or its parent directory
- `symbols` — optional list of specific symbols (all re-exports if omitted)
- `--diff` — preview mode
