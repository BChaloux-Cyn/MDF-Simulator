# Draw.io State Diagram — Continuation Prompt

We have been iterating on the state diagram generation in `tools/drawio.py`.
The goal is to produce clean, readable Draw.io state diagrams from the Elevator
domain YAML model. Continue from where we left off.

---

## How to run the iteration loop

```
.venv/Scripts/python -m pytest tests/test_elevator_state_diagram.py tests/test_drawio_tools.py -v
```

One output file is generated to `tests/output/` on every test run:

| File | What it shows |
|---|---|
| `elevator-Elevator-state-diagram.drawio` | Production state diagram ← **primary output to review** |

Open in Draw.io to inspect visually. The test fixture YAML is at
`tests/fixtures/elevator-state-diagram.yaml`.

---

## What was fixed this session

### 1. Canvas overflow + wrong layout call (`tools/drawio.py`)
- `_build_state_diagram_xml` was passing `canvas_w` and `canvas_h` as the
  `min_dist` and `margin` positional args of `_layout_for_canvas`, a signature
  mismatch introduced when `_layout_for_canvas` was refactored for the class
  diagram. This caused nodes to scale to `min_dist=1200px` apart, placing them
  far outside the intended canvas.
- **Fix:** Mirrored the class diagram pattern — compute `min_dist` from node
  dimensions (`math.hypot(STATE_W + 40, max_state_h + 40)`), call
  `_layout_for_canvas(n_vertices, edges, min_dist)`, then derive canvas size
  from the resulting positions.

### 2. New test suite for state diagrams
- `tests/test_elevator_state_diagram.py` — 12 tests:
  - `test_all_states_present`
  - `test_initial_pseudostate_present`
  - `test_all_transitions_have_edge_cells`
  - `test_initial_transition_has_no_label`
  - `test_no_overlapping_states`
  - `test_states_within_canvas`
  - `test_no_duplicate_exit_anchors`
  - `test_no_duplicate_entry_anchors`
  - `test_transition_labels_contain_event`
  - `test_self_loop_transitions_have_waypoints`
  - `test_states_with_entry_action_are_taller`
  - `test_initial_state_is_target_of_init_transition`

---

## Next task: switch to Kamada-Kawai layout

The state diagram currently uses Sugiyama (hierarchical/layered) layout, which
is appropriate for DAGs but produces awkward results for state machines with
cycles. The class diagram already supports both layouts via a `method` parameter
to `_layout_for_canvas`.

**Goal:** Switch `_build_state_diagram_xml` to use `layout_kamada_kawai` by
default — the same approach used for the class diagram's production output.

**How to do it:**

`_layout_for_canvas` already accepts a `method` parameter:
```python
def _layout_for_canvas(n_vertices, edges, min_dist, margin=MARGIN, method="sugiyama"):
```

Change the call in `_build_state_diagram_xml` (around line 832) from:
```python
positions = _layout_for_canvas(n_vertices, edges, min_dist)
```
to:
```python
positions = _layout_for_canvas(n_vertices, edges, min_dist, method="kamada_kawai")
```

After making this change, run the tests and open `tests/output/elevator-Elevator-state-diagram.drawio`
in Draw.io. The layout quality should be noticeably better — fewer crossing
edges, more balanced spacing.

---

## Things to investigate / debug after layout switch

Once Kamada-Kawai is in place, open the output in Draw.io and look for:

1. **Transition label placement** — labels currently sit at `x=-0.3, y=-15`
   relative to the edge midpoint (inherited from the class diagram pattern).
   On a state diagram with many transitions between the same pair of states,
   labels may overlap. Consider whether per-edge label offsets need spreading.

2. **Self-loop corner selection** — `_self_loop_corner` picks corners based on
   which sides have the fewest outgoing edges. Verify that all self-loops in
   the Elevator diagram (Moving_Up→Moving_Up, Moving_Down→Moving_Down) render
   cleanly outside their state box with 3-point exterior waypoints.

3. **Initial pseudostate placement** — the initial dot should appear near the
   `Idle` state (the initial state), not isolated in a corner. Verify that
   Kamada-Kawai pulls it adjacent to Idle.

4. **Guard/action text in transition labels** — transitions with guards render
   as `{trans_id}<br>{event}({params})<br>[{guard}]`. Verify these are
   readable and not clipped by the edge cell's auto-sized bounds.

5. **Anchor collision between parallel transitions** — the Elevator has two
   transitions from `Idle` (both on `Request_assigned` with different guards)
   and two from `Moving_Up` (both on `Floor_reached`). Verify
   `_assign_edge_ports` gives them distinct exit/entry anchors.

---

## Current test suite

42 tests, all passing:
- `tests/test_drawio_tools.py` — 21 tests
- `tests/test_elevator_class_diagram.py` — 9 tests
- `tests/test_elevator_state_diagram.py` — 12 tests

---

## Key files

| File | Purpose |
|---|---|
| `tools/drawio.py` | All diagram generation logic |
| `schema/drawio_schema.py` | Style constants and ID generators |
| `schema/yaml_schema.py` | `StateDiagramFile` Pydantic model |
| `tests/test_elevator_state_diagram.py` | State diagram quality tests + output generation |
| `tests/test_drawio_tools.py` | MCP + rendering unit tests |
| `tests/fixtures/elevator-state-diagram.yaml` | Stable test fixture (Elevator class state machine) |
| `tests/output/` | Generated diagrams (git-ignored) |
