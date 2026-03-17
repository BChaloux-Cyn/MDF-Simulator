# Draw.io Class Diagram Debug — Continuation Prompt

We have been iterating on the class diagram generation in `tools/drawio.py`.
The goal is to produce clean, readable Draw.io class diagrams from the Elevator
domain YAML model. Continue from where we left off.

---

## How to run the iteration loop

```
.venv/Scripts/python -m pytest tests/test_elevator_class_diagram.py tests/test_drawio_tools.py -v
```

Five output files are generated to `tests/output/` on every test run:

| File | What it shows |
|---|---|
| `elevator-step1-boxes-grid.drawio` | Boxes only, simple 4-column grid (no layout, no edges) |
| `elevator-step2-boxes-sugiyama.drawio` | Boxes only, igraph Sugiyama layout |
| `elevator-step3-full-sugiyama.drawio` | Sugiyama + all edges |
| `elevator-step4-boxes-kamada-kawai.drawio` | Boxes only, igraph Kamada-Kawai layout |
| `elevator-step5-full-kamada-kawai.drawio` | Kamada-Kawai + all edges ← **primary output to review** |

Open these in Draw.io to inspect visually. The test fixture YAML is at
`tests/fixtures/elevator-class-diagram.yaml`.

---

## What was fixed this session

### 1. Canvas overflow (`tools/drawio.py`)
- `fit_into` was mapping node *positions* (top-left corners) to the full canvas,
  so boxes drawn at those positions extended past the canvas boundary.
- **Fix:** Removed `fit_into` entirely. Replaced with `_scale_for_min_spacing`,
  which scales raw igraph coordinates so the closest pair of node centres is at
  least `CLASS_W + 40 = 260px` apart. Canvas size is derived from the resulting
  positions after scaling.

### 2. x-nudge pass removed
- The old greedy x-nudge pass sorted all nodes globally by x and pushed them
  apart in a single chain, ignoring rows (destroyed grid layouts, created
  uneven spacing in Sugiyama).
- **Fix:** Deleted. `_scale_for_min_spacing` supersedes it.

### 3. Kamada-Kawai layout added
- `_layout_for_canvas` now accepts a `method` parameter (`"sugiyama"` or
  `"kamada_kawai"`).
- `_build_class_diagram_xml` accepts `layout="sugiyama"` or `layout="kamada_kawai"`.
- KK produces significantly cleaner results than Sugiyama for class diagrams
  (which aren't inherently hierarchical).

### 4. Unnecessary edge crossings at box boundaries (R10/R11, R4/R14)
- `_assign_edge_ports` was assigning anchor slots in YAML order, not in
  the spatial order of the target nodes. This caused edges from the same side
  of a box to cross each other at the boundary.
- **Fix:** In `_assign_edge_ports`, each group of edges sharing a side is now
  sorted by the other-endpoint's position in the side's spread dimension
  (x for top/bottom sides, y for left/right sides) before anchor slots are
  assigned.

---

## Current test suite

27 tests, all passing:
- `tests/test_drawio_tools.py` — 21 tests (MCP-05/06/07 + rendering quality)
- `tests/test_elevator_class_diagram.py` — 6 tests:
  - `test_all_classes_present`
  - `test_all_associations_present`
  - `test_no_overlapping_classes`
  - `test_no_box_overlaps` — AABB check, GAP=20px on at least one axis
  - `test_anchor_order_matches_target_positions` — verifies exit anchors are
    ordered to match target positions, preventing unnecessary crossings
  - `test_classes_within_canvas`

---

## Known remaining issues / things to investigate

These have not been addressed yet. Open `elevator-step5-full-kamada-kawai.drawio`
in Draw.io and look for:

1. **Multiplicity/verb-phrase label placement** — the `assoc_mult` edge labels
   are positioned at fixed `x=±0.9, y=-10` relative offsets. On longer or
   curved edges this can place them on top of other elements. The label
   positioning logic is in `_build_class_diagram_xml` around the
   `association_label_id` cells.

2. **R5 / R6 generalization relationships** — these are subtype/supertype
   relationships (Call→ElevatorCall/FloorCall, CallButton→DestFloorButton/
   FloorCallButton) but are rendered as plain association lines. UML convention
   is a hollow triangle arrowhead pointing to the supertype. The schema has
   `partitions` and `specializes` fields that could drive a different style.

3. **Active vs entity class colours** — all classes use the same blue
   (`fillColor=#dae8fc`). Active classes (stereotype `active`) and entity classes
   (stereotype `entity`) could use distinct colours for faster visual parsing.

4. **Referential attribute noise** — attributes like `r14_request_id`,
   `r1_elevator_id` are raw foreign-key fields. They clutter the class boxes.
   Consider whether these should be hidden, dimmed, or rendered differently
   (e.g. in italic or a lighter colour) since they are compiler artefacts, not
   domain attributes.

5. **Label overlap on dense edge areas** — where many edges converge (around
   the Elevator class), multiplicity labels may overlap each other or the edge
   lines. No automated check for this yet.

---

## Key files

| File | Purpose |
|---|---|
| `tools/drawio.py` | All diagram generation logic |
| `schema/drawio_schema.py` | Style constants and ID generators |
| `tests/test_elevator_class_diagram.py` | Visual quality tests + output generation |
| `tests/test_drawio_tools.py` | Existing MCP + rendering unit tests |
| `tests/fixtures/elevator-class-diagram.yaml` | Stable test fixture (copy of elevator model) |
| `tests/output/` | Generated diagrams (git-ignored) |
