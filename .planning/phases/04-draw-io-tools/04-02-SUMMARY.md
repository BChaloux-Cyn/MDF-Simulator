---
phase: 04-draw-io-tools
plan: "02"
subsystem: drawio
tags: [igraph, lxml, drawio, render, sugiyama, mcp]

requires:
  - phase: 04-draw-io-tools
    plan: "01"
    provides: test scaffold (test_drawio_tools.py) with 4 skipped MCP-05 render tests and tmp_domain fixture
  - phase: 01-schema-foundation
    provides: drawio_schema.py (BIJECTION_TABLE, STYLE_* constants, ID generators, render_sample_xml pattern)
  - phase: 01-schema-foundation
    provides: yaml_schema.py (ClassDiagramFile, StateDiagramFile, ClassDef, StateDef, Transition Pydantic models)

provides:
  - tools/drawio.py with render_to_drawio, render_to_drawio_class, render_to_drawio_state
  - Idempotent class diagram rendering: skip-if-unchanged via structural ID frozenset comparison
  - Idempotent state diagram rendering: skip-if-unchanged via same approach
  - Greedy x-axis nudge pass ensuring no two class boxes overlap horizontally
  - igraph Sugiyama layout with dummy-vertex guard (slice coords[:n_vertices] before fit_into)

affects:
  - 04-03 (validate_drawio and sync_from_drawio consume the same drawio.py module)

tech-stack:
  added:
    - igraph (already installed; used for Sugiyama layout)
  patterns:
    - "igraph dummy-vertex guard: create new ig.Layout(coords[:n]) then call fit_into — do not attempt to set layout.coords directly (property has no setter)"
    - "Skip-if-unchanged via frozenset of cell IDs containing ':' — structural comparison avoids rewriting files when content is identical"
    - "All public functions return list[dict] with 'file'+'status' keys or issue dicts — no exceptions raised"
    - "Greedy x-axis nudge: sort by x, for each adjacent pair ensure gap >= CLASS_W"

key-files:
  created:
    - .planning/phases/04-draw-io-tools/04-02-SUMMARY.md
  modified:
    - tools/drawio.py
    - tests/test_drawio_tools.py

key-decisions:
  - "ig.Layout property has no setter — fix is ig.Layout(coords[:n]) to create new Layout from sliced list before fit_into"
  - "State diagram vertices: index 0 = initial pseudostate, indices 1..N = states (matches RESEARCH.md pattern)"
  - "render_to_drawio skips state rendering if class diagram render returned error — avoids stale state on error"

patterns-established:
  - "TDD RED: unskip tests, confirm TypeError (functions undefined), commit; GREEN: implement, fix, pass, commit"

requirements-completed:
  - MCP-05

duration: 20min
completed: 2026-03-11
---

# Phase 4 Plan 02: Draw.io Render Tools Summary

**Deterministic, idempotent Draw.io class and state diagram rendering via igraph Sugiyama layout and lxml, with structural skip-if-unchanged check**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-11T00:00:00Z
- **Completed:** 2026-03-11T00:20:00Z
- **Tasks:** 1 (TDD: 2 commits — test RED + implementation GREEN)
- **Files modified:** 2

## Accomplishments

- Implemented `render_to_drawio_class`, `render_to_drawio_state`, `render_to_drawio` in `tools/drawio.py`
- Layout uses igraph Sugiyama with dummy-vertex guard; coordinates sliced to `n_vertices` then fit to canvas
- Greedy x-axis nudge pass prevents any two class boxes from overlapping horizontally
- Structural skip-if-unchanged: `_extract_drawio_ids` compares frozenset of `":"` IDs against expected set — second render returns `status="skipped"` and does not touch the file
- All 4 MCP-05 render tests green; full suite 70 passed / 6 skipped

## Task Commits

1. **Task 1 RED: add failing render tests** - `a3d2fda` (test)
2. **Task 1 GREEN: implement render functions** - `b3e25d3` (feat)

## Files Created/Modified

- `tools/drawio.py` — Full implementation of render helpers and public render functions
- `tests/test_drawio_tools.py` — Unskipped 4 MCP-05 render tests

## Decisions Made

- `ig.Layout.coords` property has no setter in igraph 1.0.0 — fixed by constructing a new `ig.Layout(layout.coords[:n])` before calling `fit_into()` (deviation Rule 3 — blocking issue auto-fixed)
- State diagram vertex ordering: index 0 = initial pseudostate, indices 1..N = states; initial transition always `(0, initial_state_vertex_idx)`
- `render_to_drawio` short-circuits state rendering when class diagram render returns an error issue to prevent stale state

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] igraph Layout.coords has no setter**
- **Found during:** Task 1 GREEN (first test run)
- **Issue:** Plan snippet `layout.coords = coords` assumes the property is settable; igraph 1.0.0 exposes `coords` as a read-only property backed by `_coords`
- **Fix:** Replaced `layout.coords = coords; layout.fit_into(...)` with `sliced = ig.Layout(layout.coords[:n_vertices]); sliced.fit_into(...)`
- **Files modified:** `tools/drawio.py`
- **Verification:** 4 render tests pass, full suite clean
- **Committed in:** `b3e25d3` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking API difference)
**Impact on plan:** One-line fix required to adapt plan snippet to actual igraph API. No scope change.

## Issues Encountered

- igraph `Layout.coords` read-only property — discovered on first run, fixed immediately per Rule 3.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `tools/drawio.py` is fully importable with `render_to_drawio`, `render_to_drawio_class`, `render_to_drawio_state`
- Stubs for `validate_drawio` and `sync_from_drawio` raise `NotImplementedError` — plan 04-03 replaces them
- `tmp_domain` fixture reusable as-is for plan 04-03 validate/sync tests

---
*Phase: 04-draw-io-tools*
*Completed: 2026-03-11*

## Self-Check: PASSED

- tools/drawio.py: FOUND
- tests/test_drawio_tools.py: FOUND
- 04-02-SUMMARY.md: FOUND
- Commit a3d2fda (test RED): FOUND
- Commit b3e25d3 (feat GREEN): FOUND
