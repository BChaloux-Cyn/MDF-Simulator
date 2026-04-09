# Commands Reference

## Setup

```bash
# Create virtual environment and install dependencies
uv venv .venv
uv pip install -r requirements.txt

# Compile requirements (after modifying requirements.in)
pip-compile requirements.in
```

## Tests

```bash
# Run all tests
.venv/Scripts/python -m pytest tests/ -v

# Run grammar tests only
.venv/Scripts/python -m pytest tests/test_pycca.py tests/test_pycca_grammar.py -v

# Run a specific test
.venv/Scripts/python -m pytest tests/test_pycca.py::test_arriving_action_new_syntax -v
```

## Model Tools (Python API)

All model tools operate relative to the current working directory, expecting
a `.design/model/` directory structure. For the elevator example, run from
`examples/elevator/`.

### Validation

```python
from tools.validation import validate_model, validate_domain, validate_class

# Validate entire model (all domains, all classes, all state machines)
issues = validate_model()

# Validate one domain
issues = validate_domain("Elevator")

# Validate one class
issues = validate_class("Elevator", "DestFloorButton")
```

### Model I/O

```python
from tools.model_io import list_domains, read_model, write_model

# List all domains
domains = list_domains()

# Read a domain's class-diagram.yaml as raw YAML string
yaml_str = read_model("Elevator")

# Write (validates before saving)
issues = write_model("Elevator", yaml_str)
```

### Draw.io Diagram Generation

```python
from tools.drawio import render_to_drawio, render_to_drawio_class, render_to_drawio_state

# Generate all diagrams for a domain (class + state diagrams)
results = render_to_drawio("Elevator", force=True)

# Generate class diagram only
results = render_to_drawio_class("Elevator", force=True)

# Generate one state diagram
results = render_to_drawio_state("Elevator", "Elevator", force=True)
```

Without `force=True`, diagrams are skipped if the YAML structure hasn't
changed (preserving manual layout adjustments in Draw.io).

### Draw.io Sync (Draw.io -> YAML)

```python
from tools.drawio import sync_from_drawio, validate_drawio

# Validate Draw.io XML against the MDF schema
issues = validate_drawio("Elevator", xml_string)

# Sync structural changes from Draw.io back to state YAML
issues = sync_from_drawio("Elevator", "Elevator", xml_string)
```

## Quick Recipes

```bash
# Validate the elevator model (run from examples/elevator/)
cd examples/elevator
../../.venv/Scripts/python -c "from tools.validation import validate_model; print(validate_model())"

# Regenerate all elevator diagrams (run from examples/elevator/)
cd examples/elevator
../../.venv/Scripts/python -c "from tools.drawio import render_to_drawio; print(render_to_drawio('Elevator', force=True))"

# Run grammar tests after editing pycca/grammar.py
.venv/Scripts/python -m pytest tests/test_pycca.py tests/test_pycca_grammar.py -v
```
