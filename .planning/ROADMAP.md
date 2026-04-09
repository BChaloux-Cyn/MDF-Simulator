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
- [x] **Phase 3: Validation Tool** - Implement validate_model with graph reachability, structural checks, and pycca pre-parser (completed 2026-03-09)
- [x] **Phase 4: Draw.io Tools** - Implement render_to_drawio, validate_drawio, and sync_from_drawio against the locked canonical schema (completed 2026-03-11)
- [ ] **Phase 5: Simulation Engine** (umbrella — compiler approach, not interpreter; see 05-CONTEXT.md)
  - [ ] **Phase 5.1: Runtime Framework** - Instance registry, relationship link store, three-queue scheduler, ctx runtime, micro-step stream, bridge mocks, simulation clock
  - [ ] **Phase 5.2: Model Compiler** - Lark Transformer (action bodies + guards → Python), type system mapping, transition table generation, opaque zip bundle packaging
  - [ ] **Phase 5.3: Simulation Runner + Verification** - Bundle loader, scenario input, elevator model end-to-end verification, MCP tool wrappers (simulate_domain + simulate_class)
  - [ ] **Phase 5.4: GDB Command Language + CLI** - Command set definition, state inspection, step/continue/reset, clock control, attach to running simulation
  - [ ] **Phase 5.5: Breakpoint Injection** - Action-line breakpoints, property watchpoints, event breakpoints, hook injection into generated code templates
- [ ] **Phase 6: CLI Test Harness** - YAML test script schema, engine runner, mid-sequence and final-state assertion evaluation, mdf-sim-test entry point
- [ ] **Phase 7: GUI Debugger** - Dear PyGui desktop app with domain/class canvas, instance registry, queue inspector, log panel (consumes GDB commands from 5.4)
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
- [x] 03-01-PLAN.md — Schema change (initial_state on StateDiagramFile), install networkx + lark, update existing fixtures
- [x] 03-02-PLAN.md — Pycca grammar module: PYCCA_GRAMMAR, GUARD_PARSER, STATEMENT_PARSER (pycca/grammar.py)
- [x] 03-03-PLAN.md — Core validator: three public tool functions, referential integrity, graph reachability
- [x] 03-04-PLAN.md — Guard completeness: enum coverage, integer interval gap analysis, string guard errors

### Phase 4: Draw.io Tools
**Goal**: Engineers can generate, validate, and sync Draw.io diagrams from YAML with a deterministic, round-trip-stable workflow
**Depends on**: Phase 3
**Requirements**: MCP-05, MCP-06, MCP-07
**Success Criteria** (what must be TRUE):
  1. `render_to_drawio(domain)` produces XML that opens correctly in Draw.io with all classes, associations, states, and transitions visually present
  2. Calling `render_to_drawio` twice on the same unchanged YAML produces byte-identical output (idempotent)
  3. `validate_drawio(domain, xml)` returns an issue list for XML containing unrecognized shape types and returns an empty list for valid canonical XML
  4. `sync_from_drawio(domain, xml)` updates the YAML file from engineer-edited Draw.io XML and automatically runs `validate_model` — the returned issue list reflects post-sync structural state
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Test scaffold: 10 skipped test stubs + minimal-domain fixture (Wave 0)
- [x] 04-02-PLAN.md — render_to_drawio / render_to_drawio_class / render_to_drawio_state with igraph Sugiyama layout and skip-if-unchanged (MCP-05)
- [x] 04-03-PLAN.md — validate_drawio + sync_from_drawio + server.py registration of all 5 tools (MCP-06, MCP-07)

### Phase 04.1: Model Development and Compiler Testing (INSERTED)

**Goal:** Fix all broken schema artifacts (associative removal aftermath), complete the elevator reference model with simulate-ready pycca action bodies for all active classes, resolve all 5 open elevator issues, and prove the pycca grammar against real action bodies via test_elevator.py and test_pycca.py
**Requirements**: SCHEMA-REPAIR-01, SCHEMA-REPAIR-02, ELV-001, ELV-003, ELV-005, ELV-006, ELV-007, GRAMMAR-EXT, ACTION-BODIES-01, ACTION-BODIES-02, TEST-ELEVATOR
**Depends on:** Phase 4
**Plans:** 6/6 plans complete (completed 2026-04-05)

Plans:
- [x] 04.1-01-PLAN.md — Remove formalizes blocks from validation.py and associative fixture from test_yaml_schema.py
- [x] 04.1-02-PLAN.md — FloorIndicator migration to active class; ELV-001 subtype inheritance; ELV-003 R14 head pointer
- [x] 04.1-03-PLAN.md — ELV-005/006/007 model YAML fixes; Dispatcher/CallButton/FloorCall syntax corrections
- [x] 04.1-04-PLAN.md — Grammar extension: 9 pycca constructs + tests/test_pycca.py
- [x] 04.1-05-PLAN.md — Action bodies: Shaft, Door, Floor, ElevatorIndicator, FloorIndicator
- [x] 04.1-06-PLAN.md — Action bodies: Elevator, Dispatcher, ElevatorCall, FloorCall, Request, CallButton; test_elevator.py

### Phase 04.2: Body of Knowledge and Modeling Process (INSERTED)

**Goal:** Produce BoK documentation that enables a fresh Claude context to create valid, well-formed domain models — modeling patterns observed in Phase 4.1, schema/language reference synthesis, domain/class/state machine authoring guide, and a draft subagent strategy for model development
**Requirements**: TBD
**Depends on:** Phase 04.1
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 04.2 to break down)

### Phase 5: Simulation Engine (Umbrella)
**Goal**: Compile MDF YAML models into executable opaque bundles, run domain-scoped simulations with full Shlaer-Mellor execution semantics, and provide a GDB-style CLI debugger with breakpoints. Elevator model must compile, run, and be debuggable by the end of all sub-phases.
**Architecture**: Compiler approach (not interpreter) — YAML → Python source → opaque zip bundle. Hybrid: generated classes + action functions, stable framework in `engine/`. See `05-CONTEXT.md`.
**Depends on**: Phase 4.1 (pycca grammar + elevator model)
**Requirements**: MCP-08
**Success Criteria** (what must be TRUE — across all sub-phases):
  1. `simulate_domain(domain, scenario)` manages multiple active class instances across a domain, dispatches events between instances via the three-queue scheduler, and returns the full micro-step stream without raising exceptions
  2. `simulate_class(class, events)` runs an isolated single-class event sequence and returns the same micro-step format
  3. All queue routing rules apply: self-directed events → priority queue; cross-instance → standard queue; creation/deletion/delayed → standard queue
  4. Run-to-completion semantics hold: a generated event during action execution is enqueued but not dispatched until the current event finishes
  5. Sync and async instance creation and deletion each produce the correct micro-steps and lifecycle behavior per the execution domain rules
  6. Bridge calls hit the YAML mock registry and record `bridge_called` micro-steps; undefined operations return null without error
  7. An undefined class, unknown event target, or unparseable pycca block returns a structured error — not a Python exception
  8. GDB-style CLI can attach to a running simulation, inspect state, step through, and set all breakpoint types
  9. All breakpoint types (action-line, property watchpoint, event breakpoint) halt execution correctly on the elevator model

### Phase 5.1: Runtime Framework
**Goal**: Self-contained runtime framework — instance registry, relationship link store, three-queue event scheduler, `ctx` runtime object, micro-step stream generator, bridge mock registry, simulation clock. Framework runs a hand-written test harness without the compiler.
**Depends on**: Phase 5 architecture decisions (05-CONTEXT.md)
**Requirements**: MCP-08 (partial — runtime semantics)
**Success Criteria** (what must be TRUE):
  1. Instance registry supports create (sync/async), delete (sync/async), and lookup by class + identifier (including composite identifiers)
  2. Relationship link store enforces multiplicity (1:1, 1:M, M:M) and supports relate, unrelate, and chained navigation
  3. Three-queue scheduler dispatches correctly: priority before standard, FIFO within each, delay queue feeds standard on expiry
  4. Run-to-completion holds: generated events enqueue but don't dispatch until current event completes
  5. Polymorphic event dispatch routes supertype events to subtype state machines
  6. "Can't happen" produces error micro-step; "event ignored" silently consumes
  7. Final state detection triggers automatic async deletion
  8. All 12 micro-step types yield correctly from the generator
  9. Bridge mock registry loads YAML and records bridge_called micro-steps
  10. Two identical runs produce identical micro-step streams (determinism)
  11. `engine/` has zero imports from `schema/`, `tools/`, or `pycca/`
**Plans**: 5 plans

Plans:
- [ ] 05.1-01-PLAN.md — Data types (micro-steps, Event, manifest spec) + Wave 0 test scaffold
- [ ] 05.1-02-PLAN.md — Instance registry + relationship link store (SC-01, SC-02)
- [ ] 05.1-03-PLAN.md — Simulation clock + bridge mock registry (SC-09)
- [ ] 05.1-04-PLAN.md — Three-queue scheduler with dispatch, run-to-completion, polymorphic routing (SC-03..SC-07)
- [ ] 05.1-05-PLAN.md — SimulationContext (ctx) + run_simulation generator + integration tests (SC-08, SC-10, SC-11)

### Phase 5.2: Model Compiler
**Goal**: Lark Transformer compiles pycca action bodies and guards into Python source. Compiler generates one file per class (transition tables + action functions), a domain manifest, and packages everything into an opaque self-contained zip bundle.
**Depends on**: Phase 5.1
**Requirements**: MCP-08 (partial — compilation)
**Success Criteria** (what must be TRUE):
  1. Lark Transformer translates all pycca constructs (assignment, generate, cancel, create, delete, relate, unrelate, select, navigate, bridge, if/else, for-each, lambda, method calls) into valid Python source
  2. Guard expressions compile to Python boolean expressions via separate grammar entry point
  3. MDF types (enums, typedefs, container types) map to Python equivalents in generated code
  4. Supertype/subtype hierarchies are flattened correctly in generated class files
  5. Transition tables include can't-happen and event-ignored cells per state/event pair
  6. Opaque zip bundle contains generated code + copied framework — self-contained and portable
  7. Elevator model compiles to a bundle without errors
  8. Same model input produces identical bundle output (deterministic)
**Plans**: TBD

### Phase 5.3: Simulation Runner + Verification
**Goal**: Load compiled bundles, execute simulations, verify the elevator model produces correct micro-step output. Expose as `simulate_domain()` and `simulate_class()` MCP tool wrappers.
**Depends on**: Phase 5.2
**Requirements**: MCP-08 (partial — MCP tools + verification)
**Success Criteria** (what must be TRUE):
  1. Bundle loader unpacks opaque zip and wires generated code into the runtime framework
  2. Elevator model compiles, loads, runs a multi-instance scenario, and produces correct micro-step stream
  3. `simulate_domain(domain, scenario)` manages full object instance pool across a domain
  4. `simulate_class(class, events)` runs isolated single-class simulation with stripped-down context
  5. Two identical scenario runs produce identical micro-step output (determinism verified end-to-end)
**Plans**: 4 plans

Plans:
- [ ] 05.3-01-PLAN.md — Wave 0 test scaffold + fixtures + runtime directories
- [ ] 05.3-02-PLAN.md — ctx API extension: __instance_key__, generated-code-facing methods (create/delete/relate/select_*)
- [ ] 05.3-03-PLAN.md — Bundle loader + ENGINE_VERSION + scenario Pydantic schema + preflight multiplicity check
- [ ] 05.3-04-PLAN.md — simulate_domain/simulate_class MCP tools + trigger evaluator + scenario_runner + elevator E2E verification

### Phase 5.4: GDB Command Language + CLI
**Goal**: Define and implement a GDB-style command set for interacting with running simulations — inspect instances, show queues, step through events, control the clock.
**Depends on**: Phase 5.3
**Requirements**: MCP-08 (partial — interactive control)
**Success Criteria** (what must be TRUE):
  1. Command set covers: inspect instances, show queues, show current state, list relationships, list breakpoints, step, continue, reset, clock control (pause/resume/speed)
  2. CLI attaches to a running simulation and processes commands interactively
  3. State inspection shows instance attributes, current state, queue contents, and relationship links
  4. Step advances one micro-step; continue runs until breakpoint or domain idle
**Plans**: TBD

### Phase 5.5: Breakpoint Injection
**Goal**: Inject debugger hooks into generated code templates so all breakpoint types halt execution. Verify all types on the elevator model.
**Depends on**: Phase 5.4
**Requirements**: MCP-08 (partial — breakpoints)
**Success Criteria** (what must be TRUE):
  1. Action-line breakpoints (class + instance + state + line) halt execution at the specified line
  2. Property watchpoints (break on write, conditional write) halt on attribute modification
  3. Event breakpoints (instance created/deleted, event generated/received, bridge called) halt on the matching micro-step
  4. Breakpoint manager in runtime supports register, remove, enable/disable, and hit notification
  5. All breakpoint types verified working on elevator model via the GDB CLI
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
| 3. Validation Tool | 4/4 | Complete | 2026-03-09 |
| 4. Draw.io Tools | 3/3 | Complete | 2026-03-11 |
| 04.1. Model Development and Compiler Testing | 6/6 | Complete | 2026-04-05 |
| 04.2. Body of Knowledge and Modeling Process | 0/TBD | In planning | - |
| 5. Simulation Engine (umbrella) | — | Context gathered | - |
| 5.1. Runtime Framework | 0/5 | Planned | - |
| 5.2. Model Compiler | 0/TBD | Not started | - |
| 5.3. Simulation Runner + Verification | 0/TBD | Not started | - |
| 5.4. GDB Command Language + CLI | 0/TBD | Not started | - |
| 5.5. Breakpoint Injection | 0/TBD | Not started | - |
| 6. CLI Test Harness | 0/TBD | Not started | - |
| 7. GUI Debugger | 0/TBD | Not started | - |
| 8. Test Suite | 0/TBD | Not started | - |

---
*Roadmap created: 2026-03-05 for milestone v1.0 Foundation*
*Last updated: 2026-04-05 — Phase 5.1 planned: 5 plans in 3 waves*
