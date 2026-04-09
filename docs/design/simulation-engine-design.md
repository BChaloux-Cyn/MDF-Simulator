# MDF Simulation Engine Design

**Date:** 2026-03-06
**Status:** In Progress — outstanding questions noted at end of each section
**Scope:** v1 — single domain simulation

---

## Overview

`mdf-sim` is a standalone Python subpackage within the `model-based-project-framework` repo. It provides a simulation engine, a CLI test harness, and a GUI for interactive debugging of xUML domain models built with MDF. The engine is the shared core consumed by both the CLI and GUI, and also exposed as a thin wrapper via the `mdf-server` MCP tool `simulate_state_machine`.

---

## Package Structure

```
mdf-sim/
  pyproject.toml          # entry points: mdf-sim-gui, mdf-sim-test
  mdf_sim/
    engine/
      interpreter.py      # pycca AST walker, instance registry, event queues
      model.py            # MicroStep types, Event, Instance, queue definitions
      grammar.lark        # pycca lark grammar (shared with mdf-server)
    cli/
      runner.py           # run engine to completion, evaluate assertions
      script.py           # YAML test script schema (start state, events, assertions)
    gui/
      app.py              # Dear PyGui entry point
      canvas.py           # Draw.io XML parser -> positioned diagram renderer
      controls.py         # step/run/filter/inject panel
      log.py              # propagation log panel
      instances.py        # instance registry panel
      queues.py           # queue inspector panel
      breakpoints.py      # domain-level event breakpoints panel
```

`mdf-server` adds `mdf-sim` as a dependency and calls `engine.interpreter` directly for the `simulate_state_machine` MCP tool.

---

## Execution Domain Rules

The following rules define the execution domain semantics the engine must implement. These are derived from xUML/Shlaer-Mellor methodology, pycca/STSA specifications, and explicit design decisions made for this simulator. Any implementation must satisfy all rules.

### Queue Routing

1. If `sending_instance_id == target_instance_id` → **priority queue**
2. If `sending_instance_id != target_instance_id` → **standard queue** (even if same class)
3. Creation events → **standard queue** always (never priority, per pycca spec)
4. Delayed events → **delay queue** first; move to standard queue when expired (never priority)
5. At most one delayed signal of a given event type per sender-instance / receiver-instance pair may be pending at any time. Posting a second cancels the first.

### Scheduler

6. Always check priority queue before standard queue
7. After each event completes (including all generated events enqueued), check priority queue again before dequeuing from standard
8. Delay queue only feeds standard queue — never dispatched directly
9. Scheduler halts when all three queues are empty

### Run-to-Completion

10. One event processes fully — all micro-steps including any `generate` calls enqueued — before the scheduler selects the next event
11. A generated event during processing is enqueued but not dispatched until the current event completes

### Instance Lifecycle

12. Only concrete subtype instances exist. The supertype is a modeling construct only and is never instantiated.
13. **Synchronous creation** — instance placed directly in specified state; entry actions of that state are not executed
14. **Asynchronous creation** — creation event posted to standard queue; entry actions execute normally when the event is processed
15. Initial state entry is treated as a creation event (asynchronous)
16. **Synchronous deletion** — instance removed immediately; final state entry actions are not executed
17. **Asynchronous deletion** — deletion event posted to standard queue; final state entry actions execute before instance is removed
18. Final state completion triggers asynchronous deletion (posts deletion event to standard queue)
19. Creation and deletion events may be delayed — they enter the delay queue and move to standard when expired

### Clock

20. Real wall-clock time drives the delay queue, scaled by a speed multiplier
21. Clock pauses at any breakpoint or when in step-through mode
22. Speed multiplier only affects delay queue expiry — not action execution speed

---

## Engine

### Execution Model

Single-threaded per domain (STSA). Three queues:

- **Priority queue** — self-directed events (sender == receiver instance)
- **Standard queue** — cross-instance events
- **Delay queue** — pending delayed events with remaining-time counters; feeds standard queue on expiry

Scheduler loop:
```
while any queue non-empty:
    if priority non-empty:
        pop -> fire transition -> run entry actions -> repeat from top
    elif standard non-empty:
        pop -> fire transition -> run entry actions -> check priority
    elif clock running and delay queue non-empty:
        advance clock -> move expired events to standard -> check priority
    else:
        halt (domain idle)
```

### Instance Identity

Instances are identified by their class's identifier attribute value(s) as defined in the YAML schema — the same identifier used by pycca to select instances. Example: `Valve["inlet"]`, not `Valve#1`.

### Micro-Step Types

Every side effect the engine produces is a discrete micro-step yielded from the generator. Both the CLI and GUI consume this stream.

| Step Type | Payload |
|---|---|
| `scheduler_selected` | queue (`priority`/`standard`), event, target_class, target_instance_id |
| `event_received` | class, instance_id, event, args, queue |
| `guard_evaluated` | expression, result, variable_values |
| `transition_fired` | from_state, to_state |
| `action_executed` | pycca line, assignments_made |
| `generate_dispatched` | event, sending_class, sending_instance_id, target_class, target_instance_id, args, queue (`priority`/`standard`) |
| `event_delayed` | event, sending_class, sending_instance_id, target_class, target_instance_id, args, delay_ms |
| `event_delay_expired` | event moved from delay queue to standard queue |
| `event_cancelled` | cancelled delayed event identifier |
| `instance_created` | class, instance_id, initial_attrs, mode (`sync`/`async`) |
| `instance_deleted` | class, instance_id, mode (`sync`/`async`) |
| `bridge_called` | operation, args, mock_return |

### Bridge Mocking (v1)

Domain boundaries are mocked. Before running, the user configures a mock registry: a mapping of `{operation: return_value}`. Bridge calls hit this registry and record the mock return in the `bridge_called` micro-step. No other domain is actually executed.

---

## GUI

**Technology:** Dear PyGui — standalone Python process, launched via `mdf-sim-gui` entry point.

### Layout

```
+------------------------------+-------------------------------+
| [Domain] [Class] [Breakpoints|  [Log] [Instances] [Queues]  |
|                              |                               |
|      (canvas content)        |      (tab content)            |
|                              |                               |
|                              |                               |
+------------------------------+-------------------------------+
|  Controls: [Step] [Continue] [Reset]   Speed: [1x v]         |
|  Step filters: [x generate] [x transition] [ ] action ...    |
|  Inject Event: Class [__] Instance [__] Event [__]  [Send]   |
+---------------------------------------------------------------+
```

### Canvas Tabs

**Domain tab:**
- Class diagram rendered from Draw.io XML using position/size hints embedded in the XML
- Each class block shows live active state (or instance count if multiple instances exist)
- Double-click a class -> navigates to Class tab for that class

**Class tab:**
- State machine diagram rendered from Draw.io XML layout for that class
- Instance selector dropdown at top — switches which instance's active state is highlighted
- Properties panel alongside state machine:
  - Class attributes section — shared across all instances, scoped watchpoints to class
  - Instance attributes section — values for selected instance, scoped watchpoints to instance
  - Property values update live as `action_executed` micro-steps fire
- Click a state -> opens Action sub-panel below showing pycca entry actions for that state
- Click a line in the Action sub-panel -> sets instance+state+line breakpoint (red dot indicator)
- Double-click a property -> opens watchpoint dialog (break on read / write / conditional write)
  - Conditional write: user enters an inequality expression (e.g. `pressure > 100`)
  - Watchpoint on instance attribute scoped to `instance + property`
  - Watchpoint on class attribute scoped to `class + property`

**Breakpoints tab:**
- Domain-level event breakpoints, configurable by scope:

| Breakpoint Type | Scope Options |
|---|---|
| Instance created | any class, or specific class |
| Instance deleted | any class, or specific class |
| Event generated | any, specific event name, or specific sender->receiver instance pair |
| Event received | any, specific class + instance |
| Delayed event expired | any, or specific event name |
| Bridge called | any, or specific operation |

### Right Panel Tabs

**Log tab:** Scrollable list of micro-steps as they execute. Each entry shows step type, class, instance, and relevant payload. Color-coded by step type.

**Instances tab:** Live instance registry showing class/subtype, current state, and identifier attribute values for all active instances.

**Queues tab:** Current contents of priority, standard, and delay queues.

### Breakpoint Levels

Four levels, all active simultaneously. Engine pauses on whichever is hit first:

1. **Global step-type filters** — controls bar checkboxes (coarse, global)
2. **Action-line breakpoints** — set from Action sub-panel, scoped to `class + instance + state + line`
3. **Property watchpoints** — set from Properties panel, scoped to `instance + property` or `class + property`
4. **Domain event breakpoints** — set from Breakpoints canvas tab, scoped per type as above

### Controls Bar

- **Step** — advance one micro-step (respecting active breakpoint filters)
- **Continue** — run until next breakpoint hit or domain idle
- **Reset** — return to initial state, clear all queues and instance registry
- **Speed multiplier** — dropdown (0.1x, 0.5x, 1x, 5x, 10x, 100x)
- **Step-type filter checkboxes** — global coarse breakpoint toggles per micro-step type
- **Event injector** — manually post an event to any class instance mid-simulation

---

## CLI Test Harness

**Entry point:** `mdf-sim-test <script.yaml>`

Runs the engine to completion against a YAML test script. Reports pass/fail per assertion. Exits with non-zero status on any failure.

### Test Script Schema (YAML)

```yaml
domain: HydraulicSystem           # domain name (maps to .design/model/<domain>/)
mocks: path/to/mocks.yaml         # optional YAML mock registry for bridge calls

setup:
  instances:
    - class: Valve
      identifier: {name: "inlet"}
      initial_state: Closed
    - class: Pump
      identifier: {serial: "P-001"}
      initial_state: Idle

sequence:
  - step: 1
    class: Valve
    instance: {name: "inlet"}
    event: Open
    args: {}
    clock_tick_ms: 0              # optional delay before this event is dispatched
    assert:                       # optional mid-sequence assertions after this step completes
      - class: Valve
        instance: {name: "inlet"}
        state: Opening
      - class: Valve
        instance: {name: "inlet"}
        attribute: position
        value: 0

  - step: 2
    class: Pump
    instance: {serial: "P-001"}
    event: Start
    args: {}

final_assert:                     # assertions evaluated after all events complete
  - class: Valve
    instance: {name: "inlet"}
    state: Open
  - class: Pump
    instance: {serial: "P-001"}
    state: Running
    attribute: rpm
    value: 1800
```

**Assertion granularity:** Both mid-sequence (per step, runs immediately after that step's event is fully processed) and final-state (after all events complete) assertions are supported. A failing assertion reports step number, class, instance identifier, expected value, and actual value.

---

## Resolved Questions (2026-03-09)

### CLI
1. **Test script format** — YAML, schema defined above. Covers: domain, mock registry path, instance setup (class, identifier, initial state), event sequence (class, instance, event, args, optional clock tick), per-step assertions and final assertions.
2. **Assertion granularity** — Both mid-sequence and final-state assertions are supported.

### GUI
3. **Launch mechanism** — `mdf-sim-gui <domain> [--scenario file.yaml]` — domain name as positional CLI argument. No in-app domain picker for v1.
4. **Draw.io source** — GUI reads the existing `.drawio` file directly from disk. No MCP server dependency at runtime. If the file is stale, the engineer resolves that before launching.
5. **Initial simulation state** — Optional `--scenario` file pre-populates instances and queues. Without it, the domain starts empty and the engineer creates instances via the Create Instance control.
6. **Instance creation in the GUI** — Dedicated Create Instance control with sync/async toggle. Both creation modes are accessible directly (not just via event injector).

### Bridge Mocking
7. **Mock registry configuration** — YAML file only for v1. Loaded at startup by both CLI (`mocks:` field in test script) and GUI (`--mocks file.yaml` flag). GUI displays loaded mocks read-only. Runtime editing deferred to v2.

### MCP Tool Names (updated from original design)
The original design referenced a single `simulate_state_machine` MCP tool. This has been replaced by two tools:
- `simulate_domain(domain, scenario)` — domain-scoped engine, manages full object instance pool
- `simulate_class(class, events)` — isolated single-class simulation for unit-level behavioral testing

Both are thin wrappers over `mdf_sim.engine.interpreter`. The engine generator is the shared core consumed by all three surfaces (MCP tools, CLI, GUI).

---

## Engine Testing Requirements

**Very detailed engine testing is required.** The engine is the correctness guarantee for the entire simulation stack — CLI and GUI both depend on it being right. Test coverage in `tests/test_engine.py` must include:

- Each micro-step type yielded with correct payload
- All queue routing rules (self → priority, cross-instance → standard, creation/delayed → standard)
- Run-to-completion: event generated mid-action must not dispatch until current event completes
- Sync vs async instance creation: distinct lifecycle behavior for each
- Sync vs async instance deletion: distinct lifecycle behavior for each
- Guard evaluation: true path, false path, variable resolution from instance attributes
- All pycca interpreter constructs: assignment, generate, bridge call, create, delete, select/where, cardinality, conditional
- select/where with multiple instances, empty result set, cardinality operator
- Bridge call mock registry hit, miss (null return), and `bridge_called` micro-step
- Clock and delay queue: expiry moves event to standard queue, speed multiplier only affects expiry
- Clock pauses at breakpoints and in step-through mode
- Edge cases: event to non-existent instance, deletion of already-deleted instance, empty domain, unparseable pycca action

---

*Design session: 2026-03-06 — engine execution model, GUI layout, and breakpoint system defined.*
*Updated: 2026-03-09 — all outstanding questions resolved; test script schema added; MCP tool names updated; engine testing requirements added.*
