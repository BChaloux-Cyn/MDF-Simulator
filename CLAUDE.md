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

## Dependencies

All runtime dependencies must be declared in `requirements.in`. Do not install packages directly without also adding them to this file. The project uses a `.venv` virtual environment managed by `uv`.

## Issue Tracking

When you identify a bug, modeling error, schema gap, or missing test:
**Read [`issues/ISSUES.md`](issues/ISSUES.md) for the full process and file template.**

Summary of the process:
- Create a file in `issues/<name>.md` and add a row to the manifest.
- An issue is not closed until a test exists that failed before the fix and passes after.
- When solved, move to `issues/solved/<name>-SOLVED.md` and remove from the manifest.

## Key References

- **Upstream pycca manual:** <https://tcl-cm3.sourceforge.net/pycca.html>
  The original pycca code generator for Shlaer-Mellor models. Our MDF action language
  is inspired by (but not derived from) this tool. Useful for reference on storage
  strategies, relationship formalization, event generation patterns, and generalization.
- **`pycca/SYNTAX.md`** — MDF action language syntax reference
- **`schema/COMPILATION.md`** — How schema elements compile into pycca-accessible names

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
issues/         Bug and modeling issue tracker (see issues/ISSUES.md)
```
