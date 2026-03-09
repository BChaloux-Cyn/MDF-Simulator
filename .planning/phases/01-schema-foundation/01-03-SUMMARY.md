---
phase: 01-schema-foundation
plan: 03
subsystem: schema
tags: [draw.io, mxcell, style-constants, bijection, id-generators, python]

# Dependency graph
requires:
  - phase: 01-01
    provides: "mdf-server package layout and uv project structure"
provides:
  - "STYLE_* constants for all 8 MDF element types (locked Draw.io mxCell style strings)"
  - "BIJECTION_TABLE dict mapping element type names to style constants"
  - "5 deterministic ID generator functions (class_id, attribute_id, association_id, state_id, transition_id)"
  - "7 passing SCHEMA-03 tests in test_drawio_schema.py"
affects: [Phase 4 render_to_drawio, Phase 4 validate_drawio, Phase 4 sync_from_drawio]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bijection table pattern: single dict mapping element type names to immutable style constants"
    - "Deterministic ID pattern: domain:type:name segments, domain always lowercased"
    - "Module-level immutable constants with __all__ for explicit public API"

key-files:
  created: []
  modified:
    - "mdf-server/mdf_server/schema/drawio_schema.py"
    - "mdf-server/tests/test_drawio_schema.py"

key-decisions:
  - "BIJECTION_TABLE uses element type name strings as keys (not enums) to keep it JSON-serializable and easy to extend"
  - "Domain is always lowercased in all ID generator functions — canonical form is lowercase regardless of input case"
  - "STYLE_ASSOC_LABEL reuses same style as multiplicity end labels — no separate STYLE_MULTIPLICITY_LABEL constant"

patterns-established:
  - "Style constants pattern: define as immutable module-level string constants, never build from f-strings at render time"
  - "ID generator pattern: domain.lower():type:name[:subname[:idx]] — fully deterministic, no UUID needed"

requirements-completed: [SCHEMA-03]

# Metrics
duration: 2min
completed: 2026-03-06
---

# Phase 1 Plan 3: Draw.io Bijection Schema Summary

**8 STYLE_* constants, BIJECTION_TABLE, and 5 deterministic ID generators locking the YAML-to-Draw.io mxCell contract for all MDF element types**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-06T16:18:41Z
- **Completed:** 2026-03-06T16:20:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Implemented `drawio_schema.py` with 8 canonical mxCell style string constants (class, attribute, association, assoc_label, state, initial_pseudo, transition, bridge)
- Defined `BIJECTION_TABLE` as the locked contract between YAML model element types and Draw.io shapes
- Implemented 5 deterministic ID generator functions with lowercase-domain canonical form
- Replaced `@pytest.mark.skip` stubs with 7 concrete SCHEMA-03 passing tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement drawio_schema.py** - `66e0f8d` (feat)
2. **Task 2: Fill in test_drawio_schema.py** - `6eb3e89` (test)

_Note: TDD tasks — tests written in RED phase then implementation brought them GREEN._

## Files Created/Modified
- `mdf-server/mdf_server/schema/drawio_schema.py` - 8 STYLE_* constants, BIJECTION_TABLE, 5 ID generator functions, __all__, module docstring
- `mdf-server/tests/test_drawio_schema.py` - 7 concrete SCHEMA-03 tests (replaced 2 skip stubs)

## Decisions Made
- `BIJECTION_TABLE` uses plain string keys (not enums) — simpler, JSON-serializable, easy to extend
- Domain lowercasing happens inside ID functions, not at call sites — enforced by design
- No separate `STYLE_MULTIPLICITY_LABEL` — multiplicity end labels share `STYLE_ASSOC_LABEL`

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- `BIJECTION_TABLE` is the locked contract; Phase 4 (render_to_drawio, validate_drawio, sync_from_drawio) can import directly
- All 7 SCHEMA-03 tests pass; full test suite shows 15 passed, 11 skipped, 0 errors
- `drawio_schema.py` is ready to import from any Phase 4 rendering module

---
*Phase: 01-schema-foundation*
*Completed: 2026-03-06*
