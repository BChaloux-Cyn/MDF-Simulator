# Roadmap: MDF Simulator (mdf-sim) v0.1

## Overview

Build the `mdf-simulator` library in strict dependency order: schema and templates first (the contract everything else depends on), then model I/O tools, then validation, Draw.io tools, simulation engine, CLI test harness, GUI debugger, and finally the test suite. Each layer is independently verifiable before the next begins.

This roadmap covers the library scope only (Phases 1–8). Agent prompts, skills, and workflow integration are tracked in `mdf-server`.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Schema Foundation** - Define YAML model schema (Pydantic), canonical Draw.io bijection, and all artifact templates (completed 2026-03-06)
- [x] **Phase 2: MCP Server + model_io** - Scaffold the library package and implement the three foundational CRUD tools (completed 2026-03-06)
- [ ] **Phase 3: Validation Tool** - Implement validate_model with graph reachability, structural checks, and pycca pre-parser
- [ ] **Phase 4: Draw.io Tools** - Implement render_to_drawio, validate_drawio, and sync_from_drawio against the locked canonical schema
- [ ] **Phase 5: Simulation Engine** - Build pycca interpreter, object instance registry, three-queue event scheduler, micro-step generator, and MCP tool wrappers (simulate_domain + simulate_class)
- [ ] **Phase 6: CLI Test Harness** - YAML test script schema, engine runner, mid-sequence and final-state assertion evaluation, mdf-sim-test entry point
- [ ] **Phase 7: GUI Debugger** - Dear PyGui desktop app with domain/class canvas, instance registry, queue inspector, log panel, action-line breakpoints, property watchpoints, and event injector
- [ ] **Phase 8: Test Suite** - Build pytest suite covering all tools, engine unit tests, and round-trip integration test

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

### Phase 5: Simulation Engine
**Goal**: A domain-scoped simulation engine that manages object instances, relationship links, event queues, and a step-aware pycca interpreter — exposed as two MCP tools
**Depends on**: Phase 3 (pycca grammar)
**Requirements**: MCP-08
**Success Criteria** (what must be TRUE):
  1. `simulate_domain(domain, scenario)` manages multiple active class instances across a domain, dispatches events between instances via the three-queue scheduler, and returns the full micro-step stream without raising exceptions
  2. `simulate_class(class, events)` runs an isolated single-class event sequence and returns the same micro-step format
  3. All queue routing rules apply: self-directed events → priority queue; cross-instance → standard queue; creation/deletion/delayed → standard queue
  4. Run-to-completion semantics hold: a generated event during action execution is enqueued but not dispatched until the current event finishes
  5. Sync and async instance creation and deletion each produce the correct micro-steps and lifecycle behavior per the execution domain rules
  6. Bridge calls hit the YAML mock registry and record `bridge_called` micro-steps; undefined operations return null without error
  7. An undefined class, unknown event target, or unparseable pycca block returns a structured error — not a Python exception
**Plans**: TBD

### Phase 6: CLI Test Harness
**Goal**: Engineers can run automated behavioral verification against a domain model using a repeatable YAML test script
**Depends on**: Phase 5
**Requirements**: MCP-10
**Success Criteria** (what must be TRUE):
  1. `mdf-sim-test <script.yaml>` runs the engine against the scenario and evaluates all assertions, exiting non-zero on any failure
  2. The YAML test script schema covers: domain to load, mock registry path, initial instance creation (class, identifier, starting state), event sequence (class, instance, event, args, optional clock tick), and per-step assertions
  3. Mid-sequence assertions (after a specific event step) and final-state assertions are both supported
  4. Assertion failures report the specific step, class, instance, expected value, and actual value
**Plans**: TBD

### Phase 7: GUI Debugger
**Goal**: Engineers can interactively step through domain simulation with visual state machine diagrams, live instance inspection, and multi-level breakpoints
**Depends on**: Phase 5
**Requirements**: MCP-11
**Success Criteria** (what must be TRUE):
  1. `mdf-sim-gui <domain> [--scenario file.yaml]` launches the Dear PyGui app; without `--scenario` the domain starts empty
  2. Domain tab renders the class diagram from the existing `.drawio` file; Class tab renders the state machine for the selected class with active state highlighted per instance
  3. Step / Continue / Reset controls work correctly; Step advances one micro-step respecting active breakpoint filters
  4. Action-line breakpoints (class + instance + state + line), property watchpoints (break on write / conditional write), and domain event breakpoints (instance created/deleted, event generated/received, bridge called) all halt execution correctly
  5. Instance creation control supports both sync and async creation modes
  6. Log, Instances, and Queues panels update live as micro-steps fire
**Plans**: TBD

### Phase 8: Test Suite
**Goal**: All tools and the simulation engine have automated coverage confirming correctness, regression safety, and round-trip fidelity
**Depends on**: Phase 6
**Requirements**: MCP-09
**Success Criteria** (what must be TRUE):
  1. `pytest tests/` passes with zero failures on a clean checkout
  2. `test_engine.py` provides very detailed unit coverage of the engine: each micro-step type, all queue routing rules, run-to-completion semantics, sync/async lifecycle, every pycca interpreter construct, guard evaluation, select/where, bridge mock lookup, clock and delay queue expiry, and edge cases (unknown event target, double-deletion, empty domain)
  3. `test_model_io.py` covers list/read/write for valid input, missing domain, and schema-invalid input
  4. `test_drawio_roundtrip.py` confirms that YAML → XML → sync → YAML preserves semantic equivalence
  5. `test_validation.py` confirms unreachable states, trap states, and broken referential integrity are each detected
  6. `test_simulation.py` confirms a known event sequence on a known domain model produces the expected micro-step trace via the CLI harness
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Schema Foundation | 5/5 | Complete | 2026-03-06 |
| 2. MCP Server + model_io | 2/2 | Complete | 2026-03-06 |
| 3. Validation Tool | 3/4 | In Progress|  |
| 4. Draw.io Tools | 0/TBD | Not started | - |
| 5. Simulation Engine | 0/TBD | Not started | - |
| 6. CLI Test Harness | 0/TBD | Not started | - |
| 7. GUI Debugger | 0/TBD | Not started | - |
| 8. Test Suite | 0/TBD | Not started | - |

---
*Roadmap created: 2026-03-05 for milestone v1.0 Foundation*
*Last updated: 2026-03-09 — Phase 5 expanded into Phases 5–8: engine, CLI harness, GUI debugger, test suite*
