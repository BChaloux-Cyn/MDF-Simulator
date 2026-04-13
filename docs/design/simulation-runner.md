# Simulation Runner: Load-to-Execution Flow

**Date:** 2026-04-13
**Status:** Current
**Scope:** `tools/simulation.py`, `engine/bundle_loader.py`, `engine/preflight.py`,
           `engine/ctx.py`, `engine/scenario_runner.py`

This document describes how a compiled `.mdfbundle` and a `.scenario.yaml` file
are loaded and executed by the simulation engine. For the scheduler mechanics that
run after execution begins, see [`engine-scheduler.md`](engine-scheduler.md). For
how the bundle is produced, see [`compiler-pipeline.md`](compiler-pipeline.md).

---

## 1. Entry Points

Two MCP tools in `tools/simulation.py` start a simulation:

- `simulate_domain(domain, scenario, mocks)` — loads `<domain>.mdfbundle` from
  `.design/bundles/` and runs the scenario against it.
- `simulate_class(class_name, scenario, mocks)` — locates which bundle contains
  `class_name` by scanning `.design/bundles/` for a bundle whose
  `generated/<class_name>.py` entry exists, then delegates to `simulate_domain`.

Both return the same result dict:

```python
{
    "total_steps": int,
    "final_instance_states": {"ClassName": {"id_str": "StateName", ...}, ...},
    "errors": [{"type": str, "message": str}, ...],
    "trace_file": "path/to/trace.json",
}
```

The six stages below all happen inside `simulate_domain`.

---

## 2. Stage 1 — Load Scenario and Mocks

```python
scenario_def = _load_scenario(scenario)   # tools/simulation.py:58
bridge_mocks = _load_mocks(scenario, mocks)
```

`_load_scenario` reads the `.scenario.yaml` file with `yaml.safe_load` and validates
it into a `ScenarioDef` Pydantic model (`schema/scenario_schema.py`). The `ScenarioDef`
holds all scenario data as structured Python objects — instances, relationships, events,
and triggers — but no live engine state yet.

`_load_mocks` looks for a companion `.mocks.yaml` alongside the scenario file (or uses
the explicit `mocks` path). The mocks dict maps bridge operation names to return values
and is passed to the engine at context construction time.

---

## 3. Stage 2 — Load Bundle

```python
manifest, tmpdir = load_bundle(bundle_path)   # engine/bundle_loader.py:31
```

`load_bundle` extracts the `.mdfbundle` zip to a temp directory and performs three
operations:

### Path traversal guard

Every zip entry path is resolved against the temp directory and rejected if the
result does not start with the temp dir's absolute path. This prevents a malicious
bundle from writing files outside the temp dir.

### Version check

`bundle.json` is read and its `engine_version` is compared against `ENGINE_VERSION`
from `engine/__init__.py`. A mismatch raises `BundleVersionError` immediately —
bundles compiled against a different engine version are refused. To fix, recompile
the model.

### Callable rebinding

`manifest.json` is deserialized into the `DomainManifest` dict structure. At this
point all `action_fn` and `guard_fn` fields in every `TransitionEntry` are `None` —
they were stripped at compile time because functions are not JSON-serializable.

The loader then imports each `generated/<Class>.py` module via
`importlib.util.spec_from_file_location` (which preserves real file paths in stack
traces) and copies the live function references from each module's `TRANSITION_TABLE`
into the corresponding entries in the in-memory manifest:

```python
# bundle_loader.py:86-98
for cls_name, cls_def in manifest.get("class_defs", {}).items():
    module = _import_module_from_file(f"mdf_generated_{cls_name}", module_file)
    live_tt = getattr(module, "TRANSITION_TABLE", {})
    manifest_tt = cls_def["transition_table"]
    for key, live_entry in live_tt.items():
        if key in manifest_tt:
            manifest_tt[key]["action_fn"] = live_entry.get("action_fn")
            manifest_tt[key]["guard_fn"] = live_entry.get("guard_fn")
```

After this step the in-memory manifest has real callables everywhere. The JSON
file is not consulted again.

Tuple keys (`(state, event)`) are also restored here — the JSON serialized them as
`"state::event"` strings (since JSON does not support tuple keys) and the loader
splits them back on `"::"`.

---

## 4. Stage 3 — Pre-flight Check

```python
preflight_issues = check_multiplicity(scenario_def, manifest)
# engine/preflight.py:27
```

Before any simulation state is created, `check_multiplicity` validates the scenario's
declared instance population against the structural constraints in the manifest's
association definitions.

For each association, it checks the required ends — any multiplicity of `"1"` or
`"1..*"`. For every instance of the relevant class, it verifies that instance appears
in at least one relationship link in the scenario's `relationships` list. If not, a
`PreflightIssue` is produced.

The check reads the `ScenarioDef` object directly — the live `InstanceRegistry`
does not exist yet at this point. If any issues are found, the simulation refuses
to start and returns them as errors immediately, with an empty trace.

This is a **structural integrity check only** — it verifies whether the declared
population satisfies the class model's multiplicity constraints. It does not validate
behavior, states, or event sequences.

---

## 5. Stage 4 — Construct SimulationContext

```python
ctx = SimulationContext(manifest, bridge_mocks=bridge_mocks)
# engine/ctx.py:39
```

`SimulationContext` is the single object that owns all runtime state. Its constructor
builds all five engine components in one shot:

| Component | Type | Purpose |
|---|---|---|
| `ctx.clock` | `SimulationClock` | Simulation time in ms, starts at 0 |
| `ctx.registry` | `InstanceRegistry` | Instance dict store, keyed by `(class, frozenset_id)` |
| `ctx.relationships` | `RelationshipStore` | Link store keyed by `rel_id` |
| `ctx.bridge_registry` | `BridgeMockRegistry` | Maps bridge operation names to mock return values |
| `ctx.scheduler` | `ThreeQueueScheduler` | Three-queue event dispatcher |

The scheduler receives a back-reference to `ctx` (`ctx=self`) so generated action
functions can call `ctx.generate()`, `ctx.relate()`, `ctx.traverse()`, etc. at
runtime.

At this point all components are empty — no instances, no links, no events queued.

---

## 6. Stage 5 — Run Scenario Setup

```python
for step in run_scenario(ctx, scenario_def, manifest):
    steps.append(step)
# engine/scenario_runner.py:23
```

`run_scenario` is a generator. It sets up the initial world state and then drives
the execution loop, yielding `MicroStep` records throughout.

### Instance creation

For each `inst_def` in `scenario_def.instances`, `ctx.create()` is called with the
merged identifier and attribute dict. `ctx.create()` (`ctx.py:227`) looks up the
class's `initial_state` from the manifest, calls `registry.create_sync()`, and
returns the live instance dict.

The instance dict is a plain Python `dict` keyed by attribute name. Two special keys
are injected by the registry:

- `instance["__class_name__"]` — the model class name as a string
- `instance["__instance_key__"]` — a `frozenset` of the identifier attributes,
  used as a hashable registry key and as the `target` value in `ctx.generate()` calls

If the scenario specifies an explicit `state` for an instance, `curr_state` is
overridden immediately after creation.

An `aliases` dict is built mapping scenario instance names (e.g. `"elev1"`) to their
live instance dicts. This is used throughout the rest of `run_scenario` to resolve
event targets and trigger conditions by name.

### Relationship linking

For each `rel` in `scenario_def.relationships`, `ctx.relate()` is called with the
two instance dicts and the relationship ID. `ctx.relate()` delegates to
`RelationshipStore.relate()`, which enforces multiplicity and stores a link record.

### Event enqueuing

For each `ev` in `scenario_def.events`, `ctx.generate()` is called. Timing
(`at_ms` / `after_ms`) is translated to `delay_ms`: events with `fire_time > 0`
enter the delay queue; events at `fire_time=0` enter the priority or standard queue
immediately.

---

## 7. Stage 6 — Execution Loop

```python
evaluator = TriggerEvaluator(scenario.triggers, aliases)
for step in ctx.execute():
    yield step
    for trig_def in evaluator.evaluate(ctx):
        _fire_trigger_action(ctx, trig_def.then, aliases, manifest)
# engine/scenario_runner.py:82-86
```

`ctx.execute()` delegates to `scheduler.execute()` — the main event loop. For the
scheduler's detailed behavior, see [`engine-scheduler.md`](engine-scheduler.md).

After each `MicroStep` yielded from the execution loop, `TriggerEvaluator.evaluate()`
checks all scenario triggers. A trigger fires when its `when` condition is satisfied
(instance in a specific state and/or attribute equals a specific value). Triggers
that fire inject new events or method calls into the running `ctx` — this is how
scenarios drive the simulation in response to state machine behavior rather than
pre-scripting every event upfront.

Triggers with `repeat=False` disarm after the first fire. A total fire cap of 10,000
prevents infinite loops from `repeat=True` triggers that always match.

The execution loop runs until all three scheduler queues are empty (domain idle).

---

## 8. After Execution

Back in `simulate_domain`, after `run_scenario` returns:

```python
final_states = _collect_final_states(ctx)   # tools/simulation.py:114
trace_file = _write_trace(...)
```

`_collect_final_states` iterates `ctx.registry._store` to build the
`final_instance_states` dict. Each instance's `curr_state` value is read directly
from the instance dict.

All micro-steps are serialized to a timestamped JSON trace file under
`.design/traces/`. Each frozen dataclass step is converted to a plain dict via
`dataclasses.asdict`. The trace file path is returned in the result dict so callers
can inspect the full execution record.

Finally, the temp directory created by `load_bundle` is cleaned up with
`shutil.rmtree`, and any `mdf_generated_*` modules are removed from `sys.modules`
to prevent stale state from leaking between simulation calls.

---

## 9. Instance Representation

There are no Python class definitions generated for model classes — no `class Elevator:`.
Instances are plain `dict` objects throughout. The "type" of an instance exists only
in the manifest as a `ClassManifest` TypedDict.

The generated `.py` file for each model class is a **module**, not a class — it
carries the callable behavior (action and guard functions) and the `TRANSITION_TABLE`
wiring dict. The engine is the interpreter that connects instance dicts to their
behavior via the transition table.

```
Instance dict (plain Python dict)
  curr_state: "Idle"
  elevator_id: 1
  current_floor: 1
  __class_name__: "Elevator"
  __instance_key__: frozenset({("elevator_id", 1)})

ClassManifest (from manifest.json, with callables rebound)
  transition_table: {
    ("Idle", "Floor_assigned"): [{"next_state": "Departing", "action_fn": <fn>, ...}]
    ...
  }

Generated module (Elevator.py)
  def action_Departing_entry(ctx, self_dict, params): ...
  TRANSITION_TABLE: dict = { ... }
```

The scheduler looks up `(curr_state, event_type)` in the class's transition table,
calls the `action_fn` with `(ctx, instance_dict, event_args)`, then updates
`curr_state` in the instance dict. No object-oriented dispatch — the engine is the
interpreter.
