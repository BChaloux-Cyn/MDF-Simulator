# Phase 5: Simulation Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 05-simulation-engine
**Areas discussed:** Architecture approach, Target language, Code representation, Action language translation, Output format, Sub-phase breakdown, Runtime semantics allocation

---

## Architecture Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Interpreter | Walk pycca AST at runtime, no code generation (original design doc approach) | |
| Compiler | Translate YAML model → executable Python → opaque bundle | :heavy_check_mark: |

**User's choice:** Compiler approach
**Notes:** User reframed the entire phase. Instead of the interpreter described in `docs/2026-03-06-simulation-engine-design.md`, the engine compiles models into executable code with debugger hooks injected. The design doc's execution semantics (queue routing, scheduler, micro-steps) remain authoritative; only the architecture changed.

---

## Target Language

| Option | Description | Selected |
|--------|-------------|----------|
| Python | Easy breakpoint injection (sys.settrace, explicit callbacks), introspection trivial, pycca maps naturally | :heavy_check_mark: |
| C | Matches upstream pycca target, but debugger hook injection much harder | |

**User's choice:** Python
**Notes:** User confirmed quickly — Python's debugging and introspection capabilities align with the GDB-style debugger goal.

---

## Code Representation (Hybrid Architecture)

| Option | Description | Selected |
|--------|-------------|----------|
| Option 1: Full OOP | One Python class per model class with everything (scheduler, state machine, dispatch) baked in | |
| Option 2: Data-driven | Classes as dicts, generic executor walks transition tables | |
| Option 3: Hybrid | Generated Python classes for attributes/identity + separate action functions/transition tables + stable framework code | :heavy_check_mark: |

**User's choice:** Option 3 (Hybrid)
**Notes:** User asked for pros/cons of all three before confirming. Key selling points: debuggability (real classes + isolated action functions with known line numbers), clear boundary between framework and generated code, minimal regeneration surface.

---

## Action Language Translation

**Presented:** Mapping table of pycca constructs → Python equivalents. Standard constructs (assignment, if/else, for-each) map directly. Model-aware constructs (generate, cancel, create, delete, relate, unrelate, select, navigate, bridge) map to `ctx.*` method calls. Lark Transformer subclass emits Python source strings.

**User's choice:** Confirmed the approach
**Notes:** No alternatives considered — the Transformer pattern was a natural fit given the existing Lark grammar.

---

## Output Format

| Option | Description | Selected |
|--------|-------------|----------|
| Human-readable project | Unzippable, browsable Python project | |
| Opaque bundle | Self-contained zip, only engine can load/execute | :heavy_check_mark: |

**User's choice:** Opaque bundle
**Notes:** User specified the zip should be opaque — not designed for human inspection. One file per class, framework files copied in. Bundle is portable between mdf-simulator instances.

---

## Sub-Phase Breakdown

Initially proposed 4 sub-phases (user's original framing). Claude identified a gap: the runtime framework needs to exist before the translator has a target, and a simulation runner is needed to verify before layering debugging.

**Final structure (5 sub-phases):**

| Phase | Scope |
|-------|-------|
| 5.1 | Runtime framework — scheduler, queues, registry, relationship store, ctx, micro-steps |
| 5.2 | Model compiler — Lark Transformer, code generation, opaque zip packaging |
| 5.3 | Simulation runner + verification — bundle loader, elevator end-to-end, MCP tools |
| 5.4 | GDB command language + CLI — command set, state inspection, stepping, clock control |
| 5.5 | Breakpoint injection — all breakpoint types wired into generated code templates |

**User's choice:** Confirmed 5 sub-phases

---

## Additional Concerns Surfaced

Claude surfaced the following implementation concerns and allocated them to sub-phases:

**Allocated to 5.1 (Runtime):**
- Polymorphic event dispatch (supertype → subtype state machine)
- "Can't happen" vs "event ignored" per state/event cell
- Final state → async deletion chain
- Multiplicity enforcement on relationship store
- FIFO queue ordering for determinism
- Cancel semantics (match event type + sender + target)
- Sync/async creation and deletion lifecycle
- Event parameter passing
- Bridge mocking
- Simulation clock (not wall clock), now() support
- Error micro-steps (structured, never exceptions)
- Determinism guarantee

**Allocated to 5.2 (Compiler):**
- Guard expression compilation (separate grammar entry point)
- Method body compilation (not just state actions)
- Type system mapping (enums, typedefs → Python)
- Container types (List, Set, Optional → Python)
- Supertype/subtype flattening
- Lambda expressions → Python lambdas
- Can't-happen/ignored table per state
- Deterministic output

**Allocated to 5.3 (Runner):**
- Bundle loader
- Minimal scenario input format (before CLI exists)
- simulate_class isolation semantics
- MCP tool wrappers
- Determinism verification end-to-end

**User's choice:** Confirmed all allocations

---

## Claude's Discretion

- Internal data structures for queues, registry, relationship store
- Module split within `engine/`
- Micro-step representation format (dataclasses, NamedTuple, TypedDict)
- Zip bundle internal layout and naming conventions
- Test strategy per sub-phase

## Deferred Ideas

- Hot reload (recompile without restarting simulation) — future enhancement
- Runtime mock editing in GUI — v2
- Dear PyGui visual debugger — Phase 7 (consumes GDB commands)
- CLI test harness with YAML scripts — Phase 6 (consumes runner)
