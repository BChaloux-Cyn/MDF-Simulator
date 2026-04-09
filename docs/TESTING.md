<!-- GSD:doc-type=testing -->
# Testing

## Framework and Setup

Tests use **pytest** with no plugins beyond the standard library. The test root is `tests/` as configured in `pyproject.toml`.

```bash
# Run all tests
.venv/Scripts/python -m pytest tests/ -v

# Run a specific file
.venv/Scripts/python -m pytest tests/test_pycca.py -v

# Run a specific test
.venv/Scripts/python -m pytest tests/test_pycca.py::test_arriving_action_new_syntax -v

# Grammar tests only
.venv/Scripts/python -m pytest tests/test_pycca.py tests/test_pycca_grammar.py -v
```

## Test File Organization

| File | Tests | Coverage Area |
|------|------:|---------------|
| `test_pycca.py` | 77 | Action language statement parsing |
| `test_compiler_transformer.py` | 67 | Compiler AST transformer |
| `test_compiler_manifest.py` | 42 | Compiler manifest generation |
| `test_engine.py` | 42 | Simulation engine (runtime framework) |
| `test_drawio_tools.py` | 38 | Draw.io tool implementations |
| `test_compiler_bundle.py` | 35 | Compiler bundle packaging |
| `test_validation.py` | 33 | Model validation rules |
| `test_drawio_canonical.py` | 23 | Draw.io canonical shape mapping |
| `test_compiler_elevator.py` | 19 | Compiler end-to-end (elevator model) |
| `test_pycca_grammar.py` | 18 | Lark grammar rules |
| `test_compiler_grammar.py` | 17 | Compiler grammar integration |
| `test_elevator_state_diagram.py` | 14 | Elevator state diagram generation |
| `test_yaml_schema.py` | 14 | Pydantic schema validation |
| `test_elevator_class_diagram.py` | 9 | Elevator class diagram generation |
| `test_model_io.py` | 9 | Model read/write round-trip |
| `test_drawio_schema.py` | 7 | Draw.io schema conformance |
| `test_elevator.py` | 2 | Elevator model integration |
| `test_roundtrip.py` | 2 | Full model round-trip |

**Total: ~469 tests** (count as of Phase 5.2 completion)

## Writing New Tests

- All new features must be accompanied by tests covering the new behavior
- All bug fixes must include a test that would have caught the bug
- Use the appropriate level: unit for isolated logic, integration for cross-module flows
- Place test fixtures under `tests/fixtures/` and output artifacts under `tests/output/`

The elevator model (`examples/elevator/`) is the canonical integration target — use it for any test that needs a real, well-formed model.

## Issue-Driven Tests

When fixing a tracked issue (`issues/<name>.md`), the fix is not complete until:
1. A test is written that **fails** against the pre-fix code
2. The fix is applied
3. The test **passes**

See `issues/ISSUES.md` for the full process.
