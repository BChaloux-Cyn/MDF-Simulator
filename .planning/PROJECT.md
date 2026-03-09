# MDF Simulator (mdf-sim)

> **Repository:** `mdf-simulator` — a standalone Python library providing schema, tools, and simulation engine for the Model-Driven Framework (MDF). This library is consumed by `mdf-server` via git submodule.

## What This Is

A design-first development workflow for embedded and real-world systems using the Shlaer-Mellor xUML methodology. Engineers build a fully verified behavioral model before any code is written, then feed that model into a modified GSD execution pipeline. The framework is divided into four phases: Design (Phase 0), Model Verification (Phase 1), Target Configuration (Phase 2), and Implementation (Phase 3+).

**Architecture:** `mdf-simulator` owns the schema, model I/O, validation, Draw.io tools, simulation engine, and code generation targets. It exposes these as a Python library. `mdf-server` imports them and wraps them as FastMCP tools, agents, and skills.

## Current Milestone: v0.1 — Library Foundation

**Goal:** Deliver the schema definitions, model I/O tools, validation, Draw.io tools, simulation engine, and test suite as a stable, importable Python library.

**Target features:**
- Schema Foundation: YAML model schema (Pydantic), canonical Draw.io schema, behavior doc format, folder structure templates
- Model I/O: `list_domains`, `read_model`, `write_model` — foundational CRUD over `.design/model/`
- Validation: `validate_model` with graph reachability, structural checks, pycca syntax pre-check
- Draw.io Tools: `render_to_drawio`, `validate_drawio`, `sync_from_drawio` against the locked canonical schema
- Simulation: `simulate_state_machine` — lark pycca parser, event-driven interpreter, execution trace output
- Test Suite: pytest coverage for all tools with round-trip integration test

## Core Value

Engineers can verify the full structural design before typing `execute-phase` — no guessing, no mid-execution surprises.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] YAML semantic model format aligned with xUML/Shlaer-Mellor methodology — classes, associations, state machines, pycca action language, domain bridges
- [ ] Draw.io XML generation from YAML model (human-facing view only — canonical 1:1 schema)
- [ ] Structural validation with graph reachability checks — produces actionable per-issue error list (not pass/fail)
- [ ] State machine simulation — interprets pycca action language from YAML, runs event sequences, returns execution trace
- [ ] C code generation path — YAML → pycca DSL → pycca compiler → C
- [ ] Python code generation target (simulation/test path)
- [ ] Pytest suite covering all tools with round-trip integration test

### Out of Scope

- FastMCP server registration — that is `mdf-server` scope
- Agent and skill implementations — those live in `mdf-server`
- GSD integration — `mdf-server` handles the GSD layer
- Modifying GSD files — GSD is updated periodically; all customizations live in skills and the MCP package
- Micca as compilation target — pycca is the chosen path; Micca deferred
- State machine simulation is v1 — required for behavioral verification before code
- Multi-user collaboration — single engineer context for now

## Context

Built from direct experience with GSD on a previous project: GSD's questioning and planning phases ask good product questions ("what do you want to build?") but skip engineering questions ("what are your domains, what classes exist, what are the state machines, what are the subsystem interfaces?"). The result is that `execute-phase` produces structurally unexpected code — Claude makes implementation decisions that the engineer would have made differently if asked upfront.

The framework adopts **Shlaer-Mellor Executable UML** methodology, already in use at Dilon Technologies. Key references:
- *Models to Code* (Starr, Mangogna, Mellor — Apress 2017)
- Leon Starr's modelint GitHub: https://github.com/modelint
- Micca / pycca model compilers: http://repos.modelrealization.com

The YAML semantic model is Claude's native working format — one file per domain subsystem. Claude never needs to load the whole model at once, keeping context footprint small.

## Constraints

- **Package**: Standalone — this repo (`mdf-simulator`), imported by `mdf-server` as a git submodule
- **Code gen targets**: C (embedded) and Python (simulation) for v1
- **MCP tools**: Implemented as plain Python functions in this library; `mdf-server` registers them with FastMCP
- **Model files**: `.design/model/` — top-level `.design/` directory parallel to `.planning/`
- **Schema language**: Python/Pydantic — better library support for pycca parsing and graph traversal

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| YAML as source of truth (not Draw.io) | Claude generates and reasons about YAML reliably; Draw.io is a presentation view only | — Pending |
| Canonical Draw.io schema (1:1 with YAML) | Bijection means sync_from_drawio is a structured parse, not interpretation — round-trip is deterministic | — Pending |
| pycca action language in YAML | User knows C; pycca is well-documented, targets embedded C, enables simulation and code generation | — Pending |
| `.design/` as top-level directory | Separates design artifacts from planning artifacts; room to grow beyond models | — Pending |
| Simulation is v1 (not like-to-have) | pycca action language in YAML makes behavioral verification before code possible — this is the core value | — Pending |
| Artifact set: YAML + guidelines only | Draw.io is human-facing view; interface contracts are expressed in YAML as domain bridges | — Pending |
| Schema-first: YAML and Draw.io bijection locked before any tool | Prevents tool implementations from constraining schema decisions | — Pending |
| Draw.io round-trip test in Phase 1 | Validates canonical schema before the sync parser is written | — Pending |
| Skills built last against stable tool API | Agents and skills depend on stable tool contracts | — Pending |

---
*Last updated: 2026-03-09 — Migrated from model-based-project-framework monorepo; mdf-simulator split as standalone library*
