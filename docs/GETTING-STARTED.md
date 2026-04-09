<!-- GSD:doc-type=getting_started -->
# Getting Started

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | >= 3.11 | Required for `match` statements used throughout |
| [uv](https://github.com/astral-sh/uv) | latest | Virtual environment and package management |
| Git | any | Clone and version control |

## Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd mdf-simulator

# 2. Create the virtual environment
uv venv .venv

# 3. Install dependencies
uv pip install -r requirements.txt
```

## First Run

Validate the elevator reference model to confirm the installation is working:

```bash
python -m pytest tests/ -q
```

Or invoke the validation tool directly from the project root:

```bash
python -c "
from tools.validation import validate_model
from pathlib import Path
errors = validate_model(Path('examples/elevator'))
print(errors)  # Expect: []
"
```

A result of `[]` means the schema, validation, and model are all wired correctly.

## Common Setup Issues

**Wrong Python version** — `uv venv` picks up whatever `python` points to. Verify:
```bash
python --version   # must be 3.11+
```
Use `uv venv --python 3.11` to pin explicitly.

**`ModuleNotFoundError`** — Always run commands from the project root (`mdf-simulator/`), not from a subdirectory. The package is installed as an editable source tree.

**Stale requirements after a pull** — If dependencies change, re-run:
```bash
uv pip install -r requirements.txt
```

**`uv` not found** — Install it via:
```bash
pip install uv
```

## Next Steps

- **[COMMANDS.md](../COMMANDS.md)** — Full command recipes: running tools, tests, and the MCP server
- **[docs/ARCHITECTURE.md](ARCHITECTURE.md)** — System design and component map
- **[docs/CONFIGURATION.md](CONFIGURATION.md)** — YAML model file formats and runtime parameters
- **[examples/elevator/README.md](../examples/elevator/README.md)** — Reference model structure and design
