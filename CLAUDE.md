# Test fixtures

Use "todo app" domain concepts (Task, TodoList, Priority, etc.) in new test fixtures — not DeviceInfo/DeviceStatus/DeviceType.

# Running tests

Tests live in `scripts/tests/`. Run from the `scripts/` directory:

```bash
cd scripts
uv run pytest
```

To run a single test file:

```bash
cd scripts
uv run pytest tests/test_move_globals.py
```
