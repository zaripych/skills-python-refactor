# add_param_annotations

Adds type annotations to function parameters across multiple files. Handles import insertion automatically.

## Workflow

1. **Identify the parameter name** and desired annotation type
2. **Write a small script** using the factory (see example below)
3. **Run with `--diff`** to preview, then apply

## Example script

```python
import sys
from pathlib import Path

SKILL_SCRIPTS = "/absolute/path/to/skill/scripts"
sys.path.insert(0, SKILL_SCRIPTS)
from add_param_annotations import add_param_annotations
from rope_bootstrap import run
from rope.refactor.importutils.importinfo import FromImport

def setup_args(parser):
    parser.add_argument("directory", type=Path)

run(
    add_param_annotations(
        annotations={"cmd": "server_pb2.ServerCommandMsg"},
        imports={"cmd": FromImport("mylib.protobuf", 0, (("server_pb2", None),))},
        exclude=["test_protocol.py"],
    ),
    description="Annotate cmd parameters",
    setup_args=setup_args,
)
```

## Factory parameters

- `annotations` — `dict[str, str]`: param name to annotation string
- `imports` — optional `dict[str, ImportInfo]`: param name to rope import (omit for builtins)
- `include` / `exclude` — optional glob patterns
