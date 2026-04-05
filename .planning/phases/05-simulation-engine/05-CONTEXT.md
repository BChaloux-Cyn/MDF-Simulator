# Phase 5: Simulation Engine - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning (umbrella — execute via sub-phases 5.1–5.5)

<domain>
## Phase Boundary

Build the simulation engine that compiles MDF YAML models into executable opaque bundles, runs domain-scoped simulations with full Shlaer-Mellor execution semantics, and provides a GDB-style CLI debugger with breakpoints. Exposed as two MCP tools (`simulate_domain` + `simulate_class`). The elevator reference model must compile, run, and be debuggable by the end of all sub-phases.

This phase is broken into five sub-phases (5.1–5.5) due to scope. Each sub-phase has its own discuss → plan → execute cycle.

</domain>

<decisions>
## Implementation Decisions

### Architecture — Compiler, not interpreter
- **D-01:** The engine uses a **compiler approach** — YAML models are compiled into executable Python code, not interpreted at runtime. The existing design doc (`docs/2026-03-06-simulation-engine-design.md`) described an interpreter; this decision supersedes it.
- **D-02:** **Target language is Python** — generated code is Python source that calls into the runtime framework via a `ctx` object.
- **D-03:** **Hybrid architecture** — generated Python classes hold instance attributes and identity; transition tables and action functions are separate generated modules; the scheduler, queue manager, relationship store, and `ctx` runtime are stable framework code in `engine/`.

### Action language translation
- **D-04:** The pycca Lark parse tree is walked by a **Lark Transformer** subclass that emits Python source strings. The existing grammar in `pycca/grammar.py` already notes Phase 5 extends with a Transformer.
- **D-05:** Model-aware constructs (generate, cancel, create, delete, relate, unrelate, select, navigate, bridge) translate to `ctx.*` method calls. Standard constructs (assignment, if/else, for-each) translate to direct Python equivalents.
- **D-06:** Every action function receives `(self, rcvd_evt, ctx)` — self is the instance, rcvd_evt carries event parameters, ctx is the framework runtime.

### Output format
- **D-07:** Compilation target is a **self-contained opaque zip bundle** containing all generated Python files plus copied framework files. The bundle is portable — passed between mdf-simulator instances.
- **D-08:** **One generated file per class** (transition table + action functions). Plus a domain manifest (instance setup, relationship definitions, event catalog).
- **D-09:** The bundle is **opaque** — only the engine can load and execute it. Not designed for human readability.
- **D-10:** Framework code in `engine/` must be **self-contained** — no imports reaching back into `schema/`, `tools/`, or `pycca/`. The `engine/` package stands alone when copied into the bundle.

### Sub-phase breakdown
- **D-11:** Phase 5 is split into five sub-phases:
  - **5.1** — Runtime framework (scheduler, queues, registry, relationship store, ctx, micro-steps)
  - **5.2** — Model compiler (Lark Transformer, code generation, opaque zip packaging)
  - **5.3** — Simulation runner + verification (bundle loader, elevator model end-to-end, MCP tool wrappers)
  - **5.4** — GDB command language + CLI (command set, state inspection, stepping, clock control)
  - **5.5** — Breakpoint injection (action-line, property watch, event breakpoints in generated code)

### Claude's Discretion
- Internal data structures for queues, registry, and relationship store
- Exact zip bundle internal layout and naming conventions
- How framework files are copied vs referenced in the bundle
- Test strategy for each sub-phase (unit vs integration split)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Simulation engine design
- `docs/2026-03-06-simulation-engine-design.md` — Execution domain rules (queue routing, scheduler, run-to-completion, instance lifecycle, clock), micro-step types, bridge mocking, GUI layout, CLI test script schema. **Note: architecture changed from interpreter to compiler per D-01, but execution semantics and micro-step types remain authoritative.**

### Action language
- `pycca/SYNTAX.md` — Full MDF action language syntax reference
- `pycca/grammar.py` — Lark grammar with Earley parsers (GUARD_PARSER, STATEMENT_PARSER). Phase 5 extends with Transformer.
- `schema/COMPILATION.md` — How schema elements compile into pycca-accessible names, attribute access rules, visibility, mutability

### Schema and model
- `schema/` — Pydantic models for all YAML file types (ClassDef, Association, StateMachine, DomainBridge, etc.)
- `examples/elevator/` — Reference model used for end-to-end verification

### Requirements
- `.planning/REQUIREMENTS.md` §MCP-08 — Simulation engine requirements (simulate_domain, simulate_class, queue routing, run-to-completion, sync/async lifecycle, bridge mocks, structured errors)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pycca/grammar.py` — Complete Lark grammar with Earley parsers for guards and full action blocks. The Transformer will be built on top of this.
- `schema/*.py` — Pydantic models define ClassDef, Association, StateMachine, Transition, Guard, DomainBridge — the compiler reads these to generate code.
- `tools/model_io.py` — `read_model()` loads YAML into Pydantic objects; compiler uses this as input.
- `tools/validation.py` — `validate_model()` catches structural errors; should run before compilation.

### Established Patterns
- Earley parsing for both guard and statement parsers (grammar has inherent ambiguities)
- Pydantic models with `populate_by_name=True` for YAML alias flexibility
- Flat uv layout (no `src/` directory)
- Stub pattern: modules stubbed with docstring + plan reference until implemented

### Integration Points
- `engine/__init__.py` — Currently a stub, will become the runtime framework package
- `tools/simulation.py` — Currently a stub, will become MCP tool wrappers calling into `engine/`
- `examples/elevator/` — Integration test target for 5.3 verification

</code_context>

<specifics>
## Specific Ideas

- The existing design doc's execution domain rules (queue routing 1–5, scheduler 6–9, run-to-completion 10–11, instance lifecycle 12–19, clock 20–22) remain the authoritative behavioral spec even though architecture changed to compiler
- The elevator model is the exit gate — must compile, run a scenario, and produce correct micro-steps
- Bundle portability is a goal — zip can be passed between mdf-simulator instances

</specifics>

<deferred>
## Deferred Ideas

- Hot reload (recompile and reload without restarting simulation) — future enhancement
- Runtime mock editing in GUI — v2 per design doc
- Dear PyGui visual debugger — Phase 7 scope (consumes the GDB CLI commands from 5.4)
- CLI test harness with YAML test scripts — Phase 6 scope (consumes the runner from 5.3)

</deferred>

---

*Phase: 05-simulation-engine*
*Context gathered: 2026-04-05*
