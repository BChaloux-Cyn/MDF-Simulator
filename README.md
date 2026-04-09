<!-- generated-by: gsd-doc-writer -->
# mdf-simulator

A Python library implementing an MDF (Model-Driven Framework) simulator for Shlaer-Mellor / Executable UML domain models.

## Installation

Requires Python >= 3.11 and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone <repo-url>
cd mdf-simulator
uv venv .venv
uv pip install -r requirements.txt
```

## Quick Start

1. Place your domain YAML files under `.design/model/` in the working directory.
2. Validate your model:

```python
from tools.validation import validate_model

issues = validate_model()
print(issues)  # [] means no issues
```

See `examples/elevator/` for a complete, well-formed reference model.

## Usage Examples

### Model I/O

```python
from tools.model_io import list_domains, read_model, write_model

# List all domains in .design/model/
domains = list_domains()

# Read a domain's class-diagram.yaml as a YAML string
yaml_str = read_model("Elevator")

# Validate and write back
issues = write_model("Elevator", yaml_str)
```

### Validation

```python
from tools.validation import validate_model, validate_domain, validate_class

# Validate the entire model
issues = validate_model()

# Validate one domain
issues = validate_domain("Elevator")

# Validate one class and its state machine
issues = validate_class("Elevator", "DestFloorButton")
```

### Draw.io Diagram Generation

```python
from tools.drawio import render_to_drawio, sync_from_drawio

# Generate all diagrams for a domain (class + state diagrams)
results = render_to_drawio("Elevator", force=True)

# Sync structural changes from a Draw.io XML back to state YAML
issues = sync_from_drawio("Elevator", "Elevator", xml_string)
```

Without `force=True`, diagrams are skipped when the YAML structure is unchanged, preserving manual layout adjustments.

## Project Structure

```
schema/         Pydantic models for all YAML file types
tools/          Tool implementations (model_io, validation, drawio, simulation)
pycca/          Lark-based guard and statement parser
engine/         Simulation engine
compiler/       Model compiler
cli/            CLI test harness and GUI debugger
tests/          pytest suite
examples/       Reference models (elevator case study)
.design/model/  Runtime model root — domain YAML files live here
```

## Key References

- [`COMMANDS.md`](COMMANDS.md) — Setup, test, and tool invocation recipes
- [`docs/design/SYNTAX.md`](docs/design/SYNTAX.md) — MDF action language syntax reference
- [`docs/design/COMPILATION.md`](docs/design/COMPILATION.md) — How schema elements compile into pycca-accessible names
- [Upstream pycca manual](https://tcl-cm3.sourceforge.net/pycca.html) — Reference for the original Shlaer-Mellor code generator

## Running Tests

```bash
.venv/Scripts/python -m pytest tests/ -v
```

## License

No license file detected in this repository. <!-- VERIFY: license terms -->
