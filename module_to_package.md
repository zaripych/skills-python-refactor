# module_to_package

Converts a Python module into a package, then splits globals into dedicated submodules. Rewrites all imports across the project.

## Workflow

1. **Read the source file** to understand what globals it defines
2. **Propose a mapping** of symbol names to submodule names based on project naming conventions
3. **Confirm the mapping with the user** — naming mistakes cause cascading corrective work
4. **Run with `--diff`** first to preview changes
5. **Run without `--diff`** to apply

## Usage

```bash
uv run python scripts/module_to_package.py \
    --diff \
    src/pkg/models.py '{"DeviceInfo": "info", "DeviceStatus": "status"}'
```

## Arguments

- `source` — path to the `.py` file to convert
- `mapping` — **required, non-empty** JSON object: `{"SymbolName": "submodule_name", ...}`
- `--source-root` — source folder relative to project root (auto-detected if omitted)
- `--diff` — preview mode

## Building the mapping

The mapping tells the script which globals go to which submodule files. **It must not be empty.**

Read the source file, then for each class/function/constant that represents public API, choose a submodule name following the project's naming conventions. Example:

```
Source file: src/pkg/models.py
Contents: DeviceInfo (class), DeviceStatus (class), StatusCode (enum)

Mapping: {"DeviceInfo": "info", "DeviceStatus": "status", "StatusCode": "status"}
```

**Dependency auto-assignment:** Globals not listed in the mapping are automatically assigned to the submodule of the first mapped symbol that references them. For example, if `DeviceInfo` uses a helper `_parse_device`, that helper travels with `DeviceInfo` without needing to be in the mapping.

Globals referenced by no mapped symbol stay in `__init__.py`.

## After conversion

If all globals are moved out, `__init__.py` is deleted (namespace package). Otherwise it retains any unmatched globals.
