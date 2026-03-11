# mdf-simulator

A Python library implementing an MDF (Model-Driven Framework) simulator with MCP server tools for working with Shlaer-Mellor / Executable UML domain models.

## Project Planning

This project uses the **GSD (Get Shit Done)** workflow for structured development.
Planning artifacts live in `.planning/` — roadmap, phase plans, summaries, and state.

To check current progress and route to the next action:
```
/gsd:progress
```

The active milestone is `v0.1`. Phases 1–3 are complete (schema, MCP server, validation).
The next phase is **Phase 5: Simulation Engine**.

## Examples

### `examples/elevator/`

A multi-domain elevator control system model used to verify the mdf-simulator tools.

This is a **clean, well-formed reference model** — no validation errors by design.
It can be used to:
- Verify `validate_model` does not false-positive on correct models
- Test `model_io` round-trip (read/write)
- Serve as a baseline for introducing intentional errors to test validation catches

See [`examples/elevator/README.md`](examples/elevator/README.md) for the full domain structure,
class model, and state machine designs.

## Key Directories

```
schema/         Pydantic models for all YAML file types
tools/          MCP tool implementations (model_io, validation, drawio, simulation)
pycca/          Lark-based guard and statement parser
tests/          pytest suite
engine/         Simulation engine (Phase 5)
cli/            CLI test harness and GUI debugger (Phases 6–7)
.design/model/  Runtime model root — domain YAML files live here
.planning/      GSD planning artifacts
```
