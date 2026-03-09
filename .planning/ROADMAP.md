# Roadmap: MDF Simulator (mdf-sim) v0.1

## Overview

Build the `mdf-simulator` library in strict dependency order: schema and templates first (the contract everything else depends on), then model I/O tools, then validation, Draw.io tools, simulation engine, and finally the test suite. Each layer is independently verifiable before the next begins.

This roadmap covers the library scope only (Phases 1–6). Agent prompts, skills, and workflow integration are tracked in `mdf-server`.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Schema Foundation** - Define YAML model schema (Pydantic), canonical Draw.io bijection, and all artifact templates (completed 2026-03-06)
- [x] **Phase 2: MCP Server + model_io** - Scaffold the library package and implement the three foundational CRUD tools (completed 2026-03-06)
- [ ] **Phase 3: Validation Tool** - Implement validate_model with graph reachability, structural checks, and pycca pre-parser
- [ ] **Phase 4: Draw.io Tools** - Implement render_to_drawio, validate_drawio, and sync_from_drawio against the locked canonical schema
- [ ] **Phase 5: Simulation** - Implement simulate_state_machine with lark pycca parser and event-driven interpreter
- [ ] **Phase 6: Test Suite** - Build pytest suite covering all tools with round-trip integration test

## Phase Details

### Phase 1: Schema Foundation
**Goal**: Engineers and tools have a locked, versioned contract for every model element — YAML schema, Draw.io shape mappings, and scaffold templates
**Depends on**: Nothing (first phase)
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, TMPL-01, TMPL-02, TMPL-03, TMPL-04
**Success Criteria** (what must be TRUE):
  1. A valid domain YAML file (classes, associations, state machines, domain bridges) can be written by hand and accepted by the Pydantic schema without errors
  2. Every model element (class, association, state, transition, domain bridge) maps to exactly one Draw.io shape type — the bijection table is written and agreed upon
  3. The Draw.io round-trip test passes: a generated XML file opened and saved in real Draw.io produces a diff that the sync parser can handle without loss
  4. All artifact templates (DOMAINS.md, CLASS_DIAGRAM.yaml, STATE_DIAGRAM.yaml, behavior docs) exist and are populated with correct structure
  5. Any model YAML file that omits schema_version is rejected at schema validation time
**Plans**: 5 plans

Plans:
- [x] 01-01-PLAN.md — Bootstrap library package, test scaffolds, stub modules
- [x] 01-02-PLAN.md — Pydantic YAML schema (all model types, SCHEMA-01 + SCHEMA-02)
- [x] 01-03-PLAN.md — Draw.io bijection constants and ID functions (SCHEMA-03)
- [x] 01-04-PLAN.md — Draw.io round-trip test: automated + real Draw.io checkpoint (SCHEMA-04)
- [x] 01-05-PLAN.md — All six template files (SCHEMA-05, TMPL-01..04)

### Phase 2: MCP Server + model_io
**Goal**: The mdf-simulator Python package is installable and the three foundational model I/O tools are functional
**Depends on**: Phase 1
**Requirements**: MCP-00, MCP-01, MCP-02, MCP-03
**Success Criteria** (what must be TRUE):
  1. Running `pip install -e .` succeeds and the tools are importable as a library
  2. `list_domains()` returns domain names from `.design/model/` and returns an empty list when the directory does not exist
  3. `read_model(domain)` returns the YAML string for a known domain and an error listing available domains for an unknown one
  4. `write_model(domain, yaml)` saves a valid YAML file and returns a structured issue list for malformed input without throwing an exception
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Package scaffold: pyproject.toml, stub modules, test contracts (MCP-00)
- [x] 02-02-PLAN.md — model_io implementation: list_domains, read_model, write_model; all 9 tests green (MCP-01, MCP-02, MCP-03)

### Phase 3: Validation Tool
**Goal**: Structural model errors are caught automatically with actionable, location-specific issue lists — not pass/fail booleans
**Depends on**: Phase 2
**Requirements**: MCP-04
**Success Criteria** (what must be TRUE):
  1. `validate_model(domain)` returns a list of `{issue, location, value, fix}` objects — never raises an exception, never returns a boolean
  2. Unreachable states (states with no incoming transition from reachable states) are detected and reported with state name and domain location
  3. Trap states (states with no outgoing transitions) are detected and reported
  4. Referential integrity errors (association referencing a class that does not exist, transition targeting a state that does not exist) are reported with specific names
**Plans**: 4 plans

Plans:
- [ ] 03-01-PLAN.md — Schema change (initial_state on StateDiagramFile), install networkx + lark, update existing fixtures
- [ ] 03-02-PLAN.md — Pycca grammar module: PYCCA_GRAMMAR, GUARD_PARSER, STATEMENT_PARSER (pycca/grammar.py)
- [ ] 03-03-PLAN.md — Core validator: three public tool functions, referential integrity, graph reachability
- [ ] 03-04-PLAN.md — Guard completeness: enum coverage, integer interval gap analysis, string guard errors

### Phase 4: Draw.io Tools
**Goal**: Engineers can generate, validate, and sync Draw.io diagrams from YAML with a deterministic, round-trip-stable workflow
**Depends on**: Phase 3
**Requirements**: MCP-05, MCP-06, MCP-07
**Success Criteria** (what must be TRUE):
  1. `render_to_drawio(domain)` produces XML that opens correctly in Draw.io with all classes, associations, states, and transitions visually present
  2. Calling `render_to_drawio` twice on the same unchanged YAML produces byte-identical output (idempotent)
  3. `validate_drawio(domain, xml)` returns an issue list for XML containing unrecognized shape types and returns an empty list for valid canonical XML
  4. `sync_from_drawio(domain, xml)` updates the YAML file from engineer-edited Draw.io XML and automatically runs `validate_model` — the returned issue list reflects post-sync structural state
**Plans**: TBD

### Phase 5: Simulation
**Goal**: Engineers can run event sequences against state machines and receive execution traces that verify behavioral correctness
**Depends on**: Phase 3
**Requirements**: MCP-08
**Success Criteria** (what must be TRUE):
  1. `simulate_state_machine(class, events)` processes an event sequence and returns a trace listing each `{event, from_state, to_state, guards_evaluated, actions_executed, final_state}` entry
  2. The lark grammar parses valid pycca action blocks (assignments, generate statements, bridge calls, conditionals) without error
  3. A guard condition that evaluates to false causes the transition to be skipped and that guard evaluation is visible in the trace
  4. An undefined class name or unparseable pycca block returns a structured error — not a Python exception propagating to the caller
**Plans**: TBD

### Phase 6: Test Suite
**Goal**: All tools have automated coverage confirming correctness, regression safety, and round-trip fidelity
**Depends on**: Phase 5
**Requirements**: MCP-09
**Success Criteria** (what must be TRUE):
  1. `pytest tests/` passes with zero failures on a clean checkout
  2. `test_model_io.py` covers list/read/write for valid input, missing domain, and schema-invalid input
  3. `test_drawio_roundtrip.py` confirms that YAML → XML → sync → YAML preserves semantic equivalence (same classes, associations, and state topology)
  4. `test_validation.py` confirms that unreachable states, trap states, and broken referential integrity are each detected
  5. `test_simulation.py` confirms that a known event sequence on a known state machine produces the expected trace
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema Foundation | 5/5 | Complete   | 2026-03-06 |
| 2. MCP Server + model_io | 2/2 | Complete   | 2026-03-06 |
| 3. Validation Tool | 0/4 | Not started | - |
| 4. Draw.io Tools | 0/TBD | Not started | - |
| 5. Simulation | 0/TBD | Not started | - |
| 6. Test Suite | 0/TBD | Not started | - |

---
*Roadmap created: 2026-03-05 for milestone v1.0 Foundation*
*Last updated: 2026-03-09 — Split from monorepo; Phases 7–10 (agents, skills) moved to mdf-server*
