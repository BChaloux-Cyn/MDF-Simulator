# Terminate Pseudostate — Design Spec

**Date:** 2026-06-26
**Status:** Approved

## Summary

Add a `__terminal__` reserved transition destination keyword to the MDF state diagram YAML. Any transition with `to: __terminal__` routes to a UML terminate pseudostate (circle with X) rendered in Draw.io. The terminate pseudostate is a virtual node — no `StateDef` is required. Reaching `__terminal__` deletes the object instance; it performs no other action.

---

## Background

The MDF simulator currently supports:
- An initial pseudostate (`__initial__`) as a virtual source node — generated automatically in Draw.io, not defined in the YAML states list
- `StateDef.terminal: bool = False` — an unused flag intended to mark lifecycle-ending states

The `StateDef.terminal` approach is wrong for two reasons:
1. The UML terminate pseudostate is not a state with behavior — it is a pseudostate that causes immediate object deletion
2. Entry actions are inappropriate on a terminate pseudostate; cleanup must happen in a preceding state

The new approach mirrors how `__initial__` works: `__terminal__` is a reserved keyword used as a `to:` destination in transitions. The Draw.io renderer emits a terminate pseudostate cell whenever any transition targets it.

---

## Semantics

### `__terminal__` pseudostate

- **Purpose:** Signals the end of the object instance lifecycle.
- **Effect:** On entry, the runtime deletes the object. No action body executes.
- **Entry action:** Not supported. If cleanup is required (attribute zeroing, relationship unlinks, cross-domain notifications), it must be performed in a normal state that transitions to `__terminal__`.
- **Outgoing transitions:** None. `__terminal__` is a sink.
- **Incoming transitions:** Any number of transitions from any state may target `__terminal__`.
- **YAML syntax:**

```yaml
transitions:
  - from: Closing
    to: __terminal__
    event: Closed
```

- **Draw.io rendering:** A 20×20 circle with an X (UML terminate pseudostate symbol), using `shape=mxgraph.uml.terminate`.

---

## Changes Required

### 1. `schema/yaml_schema.py`

Remove `terminal: bool = False` and its docstring from `StateDef`. The field is unused in practice (no existing fixtures use it) and is replaced by the `__terminal__` keyword.

**No other changes to this file.**

---

### 2. `schema/drawio_schema.py`

Add the terminate pseudostate style constant:

```python
STYLE_TERMINATE_PSEUDO = (
    "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    "fillColor=#ffffff;strokeColor=#000000;"
    "shape=mxgraph.uml.terminate;"
)
```

- Add `"STYLE_TERMINATE_PSEUDO"` to `__all__`.
- Add `"terminate_pseudo": STYLE_TERMINATE_PSEUDO` to `BIJECTION_TABLE`.
- No new ID generator function. Terminal pseudostate cells use the existing `state_id` pattern: `{domain.lower()}:state:{class_name}:__terminal__`.

---

### 3. `tools/validation.py`

**Referential integrity** (`_check_referential_integrity`):

Allow `t.to == "__terminal__"` as a valid transition target. Specifically, in the block:
```python
if t.to not in state_names:
    issues.append(...)
```
add `and t.to != "__terminal__"` to the condition so it becomes:
```python
if t.to not in state_names and t.to != "__terminal__":
    issues.append(...)
```

**Reachability and terminal logic** (`_check_reachability`):

Replace the existing `StateDef.terminal`-based logic entirely:

```python
# Old — remove:
terminal_states = {s.name for s in sd.states if s.terminal}
for state in terminal_states:
    if G.out_degree(state) > 0:
        issues.append(...)  # terminal states must not have outgoing transitions

# Old trap-state check — update fix message:
for state in state_names:
    if G.out_degree(state) == 0 and state not in terminal_states:
        # fix= currently says "mark the state as terminal: true"
```

New logic:
- Add `"__terminal__"` as a node in the DiGraph.
- Add edges `from_state → "__terminal__"` for all transitions where `t.to == "__terminal__"`.
- Remove the "terminal states must not have outgoing transitions" block.
- Update the trap-state fix message from `"mark the state as terminal: true if it ends the object lifecycle"` to `"add a transition 'to: __terminal__' if the state ends the object lifecycle, or add outgoing transitions"`.

**Effect:** States that route exclusively to `__terminal__` have `G.out_degree > 0` and are not flagged as traps. `__terminal__` itself is not in `state_names` so it is never tested for reachability.

---

### 4. `tools/drawio.py` — Rendering

**Import:** Add `STYLE_TERMINATE_PSEUDO` to the import from `schema.drawio_schema`.

**`_build_state_diagram_xml`:**

At the top of the function, detect whether a terminal pseudostate node is needed:

```python
has_terminal = any(t.to == "__terminal__" for t in sd.transitions)
```

Vertex indexing:
- Vertices `0`: `__initial__`
- Vertices `1..N`: states (unchanged)
- Vertex `N+1` (if `has_terminal`): `__terminal__`

Update `state_name_to_idx`, `node_widths`, `node_heights`, and `n_vertices` to include `__terminal__` when `has_terminal`:

```python
if has_terminal:
    terminal_vertex_idx = n_vertices
    n_vertices += 1
    state_name_to_idx["__terminal__"] = terminal_vertex_idx
    node_widths.append(INIT_SIZE)
    node_heights.append(INIT_SIZE)
```

After emitting all regular state nodes, emit the terminal pseudostate cell:

```python
if has_terminal:
    term_cid = f"{domain.lower()}:state:{class_name}:__terminal__"
    x = int(positions[terminal_vertex_idx][0])
    y = int(positions[terminal_vertex_idx][1])
    term_cell = etree.SubElement(
        root_el, "mxCell",
        id=term_cid, value="",
        style=STYLE_TERMINATE_PSEUDO, vertex="1", parent="1",
    )
    etree.SubElement(
        term_cell, "mxGeometry",
        x=str(x), y=str(y), width=str(INIT_SIZE), height=str(INIT_SIZE),
        attrib={"as": "geometry"},
    )
```

Transitions to `__terminal__` are handled by the existing transition loop unchanged — `state_name_to_idx["__terminal__"]` resolves to the vertex index, and `state_id(domain, class_name, "__terminal__")` resolves to the cell ID.

**`_drawio_to_canonical_state`:**

In the state-collection loop, skip `__terminal__` alongside `__initial__`:

```python
if state_name in ("__initial__", "__terminal__"):
    continue
```

Transitions targeting `__terminal__` are parsed normally by the existing transition loop — `to_state_name` will be `"__terminal__"` and flows correctly into `CanonicalTransition.to`.

---

### 5. Canonical representation — No changes

`CanonicalState`, `CanonicalStateDiagram`, `canonical_builder.py` require no changes. Transitions with `to: __terminal__` appear in the canonical as ordinary transitions. The terminal pseudostate cell is skipped during state parsing. Round-trip detection works correctly: if a `to: __terminal__` transition is added or removed from YAML, the canonical JSON changes and re-render is triggered.

---

### 6. `docs/design/SYNTAX.md` — New section

Add a new section (between sections 11 and 12) titled **"State Machine Pseudostates"**. Content:

- `__initial__`: virtual source node; the `initial_state:` field in YAML points to the first real state; not defined in the `states:` list.
- `__terminal__`: reserved transition destination; reaching it deletes the object instance; performs no other action; if cleanup is needed, use a preceding state with an entry action; no `StateDef` is required.
- YAML usage example for `__terminal__`.
- Note that `__terminal__` is the only action — it cannot be extended.

---

### 7. Tests

**`tests/test_drawio_schema.py`:**
- Add `"terminate_pseudo"` to `REQUIRED_ELEMENT_TYPES`.
- Add `test_style_terminate_pseudo_nonempty`.

**New fixture:** `tests/fixtures/terminal-state-diagram.yaml`

A minimal state machine (domain `Terminal`, class `Widget`) with:
- States: `Active`, `Closing`
- Events: `Shutdown`, `Done`
- Transitions: `Active --Shutdown--> Closing`, `Closing --Done--> __terminal__`

**New test file:** `tests/test_terminate_pseudostate.py`

| Test | Assertion |
|------|-----------|
| `test_terminate_pseudostate_cell_present` | Cell with ID `terminal:state:Widget:__terminal__` exists |
| `test_terminate_pseudostate_uses_correct_style` | Cell style is `STYLE_TERMINATE_PSEUDO` |
| `test_terminate_pseudostate_is_20x20` | Geometry width/height == `INIT_SIZE` |
| `test_terminate_pseudostate_has_empty_value` | `value == ""` |
| `test_regular_state_still_uses_state_style` | `Active` and `Closing` cells use `STYLE_STATE` |
| `test_transition_to_terminal_targets_pseudostate_cell` | Edge targeting `Closing --Done--> __terminal__` has `target == "terminal:state:Widget:__terminal__"` |
| `test_no_terminal_transitions_no_terminal_cell` | A diagram with no `__terminal__` targets produces no `__terminal__` cell |

**`tests/test_elevator_state_diagram.py`:**
- No changes needed (elevator fixture has no `__terminal__` transitions).

---

## Files Changed

| File | Change |
|------|--------|
| `schema/yaml_schema.py` | Remove `StateDef.terminal` field |
| `schema/drawio_schema.py` | Add `STYLE_TERMINATE_PSEUDO`, update `__all__` and `BIJECTION_TABLE` |
| `tools/validation.py` | Allow `__terminal__` as transition target; remove `StateDef.terminal`-based logic |
| `tools/drawio.py` | Add terminal pseudostate rendering; skip `__terminal__` in canonical parser |
| `docs/design/SYNTAX.md` | Add "State Machine Pseudostates" section |
| `tests/test_drawio_schema.py` | Add `terminate_pseudo` to `REQUIRED_ELEMENT_TYPES`; add style test |
| `tests/fixtures/terminal-state-diagram.yaml` | New minimal fixture with `__terminal__` target |
| `tests/test_terminate_pseudostate.py` | New test file (7 tests) |

---

## Out of Scope

- `schema/drawio_canonical.py` — no change needed
- `schema/canonical_builder.py` — no change needed
- Compiler (`compiler/`) — `__terminal__` transitions are plain transitions; if the compiler handles lifecycle deletion separately, that is a separate concern
