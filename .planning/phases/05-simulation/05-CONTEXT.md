# Phase 5: Simulation Engine - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the simulation engine core: pycca interpreter (extending Phase 3's syntax-only grammar with an execution layer), object instance registry with full lifecycle management, three-queue event scheduler (priority / standard / delay), and a micro-step generator that both the CLI harness (Phase 6) and GUI debugger (Phase 7) consume. Expose the engine as two MCP tools: `simulate_domain` and `simulate_class`. Bridge call handling via a pre-configured YAML mock registry.

Draw.io tools (Phase 4), CLI harness (Phase 6), GUI debugger (Phase 7), and test suite (Phase 8) are all out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### MCP tool interface

Two tools replace the original `simulate_state_machine`:

- `simulate_domain(domain, scenario)` — domain-scoped simulation. Manages all active class instances in the domain, inter-class event dispatch, and the full three-queue scheduler. Takes a domain name and an optional path to a YAML scenario file. Returns the full micro-step stream as a list.
- `simulate_class(class, events)` — isolated single-class simulation for unit-level behavioral testing. No object pool, no cross-class dispatch. Returns the same micro-step format as `simulate_domain` for compatibility.

Both tools follow the established pattern: never raise exceptions, always return structured data.

### Engine execution model

Fully defined in `docs/2026-03-06-simulation-engine-design.md`. Key rules locked:

- Single-threaded per domain (STSA)
- Three queues: priority (self-directed), standard (cross-instance), delay (timed events feeding standard)
- Run-to-completion: one event fully processes before the next is dequeued
- Queue routing: self → priority, cross-instance → standard, creation/deletion/delayed → standard
- Scheduler halts when all three queues are empty

### Micro-step types

Defined in the design doc. Every side effect the engine produces is a discrete typed micro-step. The engine is a generator that yields micro-steps — consumers (CLI, GUI) iterate over this stream. Types:

`scheduler_selected`, `event_received`, `guard_evaluated`, `transition_fired`, `action_executed`, `generate_dispatched`, `event_delayed`, `event_delay_expired`, `event_cancelled`, `instance_created`, `instance_deleted`, `bridge_called`

### Instance identity

Instances are identified by their class's identifier attribute value(s) as defined in the YAML schema — consistent with how pycca selects instances. Example: `Valve["inlet"]`, not an internal numeric ID. This means identifier attributes are required at creation time.

### Instance lifecycle

Fully defined in the design doc (rules 12–19). Key points:
- Only concrete subtype instances exist (supertype is a modeling construct only)
- Synchronous creation: instance placed directly in specified state, entry actions NOT executed
- Asynchronous creation: creation event posted to standard queue; entry actions execute normally
- Synchronous deletion: instance removed immediately, final state entry actions NOT executed
- Asynchronous deletion: deletion event posted to standard queue; final state actions execute before removal

### Bridge call handling (v1)

Domain boundaries are mocked via a YAML mock registry file. Format: `{operation_name: return_value}`. The file is passed as an optional argument at simulation startup; if absent, bridge calls return `null` and are logged as `bridge_called` micro-steps. The registry is read-only during simulation — no runtime mutation.

### Pycca interpreter scope

Phase 3 delivers the lark grammar (syntax-only). Phase 5 adds the AST walker / interpreter that actually executes pycca constructs:
- Assignment: `self.x = expr`
- Generate: `generate Event to SELF` / `generate Event to ClassName where <expr>`
- Bridge call: `Domain::operation[args]`
- Object lifecycle: `create object of ClassName` / `delete object of ClassName where ...`
- Select/where: `select any/many <var> from instances of <Class> where <expr>`
- Cardinality: `cardinality <assoc_ref>`
- Conditionals: `if <expr>; ... end if;`

### Clock

Real wall-clock time drives the delay queue, scaled by a speed multiplier. Clock pauses at any breakpoint or in step-through mode. Speed multiplier only affects delay queue expiry — not action execution.

### Package structure

New subpackage `mdf_sim/` added alongside existing `mdf_server/` in the repo. Entry points registered in `pyproject.toml`: `mdf-sim-gui` (Phase 7) and `mdf-sim-test` (Phase 6). `mdf_server` imports from `mdf_sim.engine` for the MCP tool wrappers.

```
mdf_sim/
  engine/
    interpreter.py    # pycca AST walker, instance registry, event queues
    model.py          # MicroStep types, Event, Instance, queue definitions
  cli/                # Phase 6
  gui/                # Phase 7
```

### Testing requirements

**Very detailed engine testing is required.** The engine is the core correctness guarantee of the entire simulation stack — the CLI harness and GUI both depend on it being correct. Unit tests must cover:
- Each micro-step type individually
- All queue routing rules (self vs cross-instance, creation, delayed)
- Run-to-completion semantics (event generated mid-action must not dispatch until current event completes)
- Sync vs async instance creation and deletion (distinct behavior for each)
- Guard evaluation (true/false paths, variable resolution)
- pycca interpreter: each construct type with correct and incorrect inputs
- select/where with multiple instances, empty result, cardinality
- Bridge call mock registry lookup and null fallback
- Clock and delay queue expiry
- Edge cases: event to non-existent instance, deletion of already-deleted instance, empty domain

Engine tests live in `tests/test_engine.py` and are separate from `tests/test_simulation.py` (the integration-level simulation tests in Phase 8).

### Claude's Discretion

- Internal data structure for the instance registry (dict keyed by `(class, identifier_tuple)` or similar)
- AST node types and visitor pattern details
- Exact queue implementation (deque, heapq for delay)
- Error message wording for malformed pycca or unknown event targets
- How to handle pycca `where` clause evaluation against the instance registry

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `mdf_server/pycca/__init__.py` — stub module scaffolded in Phase 1; `grammar.lark` and `grammar.py` added in Phase 3; Phase 5 adds `interpreter.py` here or under `mdf_sim/engine/`
- `mdf_server/schema/yaml_schema.py` — all Pydantic models: `ClassDef`, `StateDef`, `Transition`, `StateDiagramFile`, `ClassDiagramFile` — engine reads YAML through these
- `mdf_server/tools/model_io.py::_resolve_domain_path()` — reusable case-insensitive domain path resolution
- `mdf_server/tools/model_io.py::read_model()` — engine calls this to load domain YAML

### Established Patterns

- Tools never raise exceptions — structured return data only
- `MODEL_ROOT = Path(".design/model")` anchored to CWD
- Issue/trace format: `{field, value, location}` — micro-step format extends this
- `importlib.reload` pattern for test isolation (monkeypatch.chdir)

### Integration Points

- `mdf_server/server.py` — two new `@mcp.tool` registrations for `simulate_domain` and `simulate_class`
- `mdf_server/tools/simulation.py` — currently a docstring stub; thin wrapper calling `mdf_sim.engine.interpreter`
- `mdf_sim/engine/` — new module; must be importable independently of `mdf_server`
- Phase 3 grammar in `mdf_server/pycca/grammar.py` (or `.lark`) — Phase 5 imports it; no duplication

</code_context>

<specifics>
## Specific Ideas

- The engine is a Python generator yielding micro-steps. Consumers call `next()` or iterate with `for step in engine.run(scenario)`. This makes step-through mode in the GUI trivial — call `next()` once per Step button press.
- Instance identity via identifier attribute values (not opaque handles) means pycca `select where` queries and `generate Event to ClassName where id == "X"` resolve through the same registry lookup path.
- The design doc (`docs/2026-03-06-simulation-engine-design.md`) is the authoritative reference for execution domain rules and micro-step payloads. Do not restate those rules in plans — reference the doc.

</specifics>

<deferred>
## Deferred Ideas

- Multi-domain simulation (bridged domain execution, not just mocking) — v2+
- Scrall action language interpreter — deferred until pycca path is proven
- Polymorphic event dispatch across subtype hierarchies — Phase 5 dispatches to concrete subtypes only; supertype dispatch deferred
- GUI bridge mock editing at runtime — v2; v1 is YAML file only
- Test script format and CLI runner — Phase 6
- GUI debugger — Phase 7

</deferred>

---

*Phase: 05-simulation*
*Context gathered: 2026-03-09*
