<!-- GSD:doc-type=development -->
# Development Guide

## Local Setup

```bash
uv venv .venv
uv pip install -r requirements.txt
```

After modifying `requirements.in`, recompile the pinned lockfile:

```bash
pip-compile requirements.in
```

Always add new runtime dependencies to `requirements.in` — do not install packages directly without also declaring them there.

## Package Structure

The project is a Python package (`mdf-sim`) built with Hatchling. The installable modules are:

| Module | Purpose |
|--------|---------|
| `schema/` | Pydantic models for all YAML file types |
| `pycca/` | Lark-based guard and statement parser |
| `tools/` | MCP tool implementations (model_io, validation, drawio, simulation) |
| `engine/` | Simulation engine |
| `cli/` | CLI test harness and GUI debugger |

Entry points defined in `pyproject.toml`:
- `mdf-sim-test` → `cli.test_harness:main`
- `mdf-sim-gui` → `cli.gui:main`

## Running the MCP Server

```bash
.venv/Scripts/python -m mcp run server.py
```

The server exposes all model tools (validation, model_io, drawio, simulation) over the MCP protocol for use with Claude Desktop or IDE integrations.

## Code Style

Dev dependencies: `ruff` (linting/formatting), `mypy` (type checking), `pytest` (testing).

```bash
# Lint
.venv/Scripts/python -m ruff check .

# Format
.venv/Scripts/python -m ruff format .

# Type check
.venv/Scripts/python -m mypy .
```

## Issue Tracking

When a bug, modeling error, schema gap, or missing test is identified:

1. Create a file in `issues/<name>.md` using the template in `issues/ISSUES.md`
2. Add a row to the manifest in `issues/ISSUES.md`
3. An issue is not closed until a test exists that failed before the fix and passes after
4. When solved, move to `issues/solved/<name>-SOLVED.md` and remove from the manifest

## Working with the Elevator Example

The `examples/elevator/` directory is the canonical reference model. All tool invocations that need a model root should be run from there:

```bash
cd examples/elevator

# Validate
../../.venv/Scripts/python -c "from tools.validation import validate_model; print(validate_model())"

# Regenerate Draw.io diagrams
../../.venv/Scripts/python -c "from tools.drawio import render_to_drawio; print(render_to_drawio('Elevator', force=True))"
```

See `COMMANDS.md` for the full set of command recipes.
