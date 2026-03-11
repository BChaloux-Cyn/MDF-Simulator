---
phase: 04-draw-io-tools
plan: "01"
subsystem: testing
tags: [pytest, drawio, mcp, yaml, fixtures]

requires:
  - phase: 03-validation-tool
    provides: validate_model tool and issue dict format used by MCP-07 sync tests
  - phase: 01-schema-foundation
    provides: drawio_schema.py (BIJECTION_TABLE, style constants, render_sample_xml, ID generators)

provides:
  - tests/test_drawio_tools.py with 10 skipped stubs covering MCP-05/06/07
  - tmp_domain fixture creating a minimal hydraulics domain (class-diagram + Pump state machine)
  - Test contracts locked before implementation begins

affects:
  - 04-02 (render_to_drawio implementation — unskips MCP-05 tests)
  - 04-03 (validate_drawio + sync_from_drawio — unskips MCP-06 and MCP-07 tests)

tech-stack:
  added: []
  patterns:
    - "Try/except import guard — stub modules that define no exports don't block test collection"
    - "tmp_domain fixture uses monkeypatch.chdir(tmp_path) for MODEL_ROOT resolution"

key-files:
  created:
    - tests/test_drawio_tools.py
  modified: []

key-decisions:
  - "Import guard via try/except (not pytest.importorskip) — allows None sentinels; tests remain skippable without conditional imports inside each function"
  - "Fixture writes YAML with yaml.dump (not raw strings) — ensures canonical key names for Association aliases (1_mult_2 etc.)"

patterns-established:
  - "Test-first scaffold: all 10 test contracts defined before any production code exists"

requirements-completed:
  - MCP-05
  - MCP-06
  - MCP-07

duration: 5min
completed: 2026-03-11
---

# Phase 4 Plan 01: Draw.io Tools Test Scaffold Summary

**10 skipped pytest stubs covering render/validate/sync Draw.io tools with a reusable hydraulics domain fixture**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-11T00:00:00Z
- **Completed:** 2026-03-11T00:05:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/test_drawio_tools.py` with 10 named test functions, all marked `@pytest.mark.skip`
- `tmp_domain` fixture builds a minimal hydraulics domain (Valve entity, Pump active class, R1 association, Pump state machine) under `tmp_path/.design/model/hydraulics/`
- Import guard prevents `ImportError` from `tools/drawio.py` stub (which exports no functions yet)
- pytest collects all 10 tests, reports 10 skipped, 0 errors

## Task Commits

1. **Task 1: Write test scaffold for drawio tools** - `0b9e391` (test)

**Plan metadata:** (pending final docs commit)

## Files Created/Modified

- `tests/test_drawio_tools.py` - 10 skipped test stubs + tmp_domain fixture for MCP-05/06/07

## Decisions Made

- Used `try/except ImportError` rather than `pytest.importorskip` so individual test functions receive `None` sentinels rather than being globally skipped at collection time — keeps skip reasons accurate per test.
- Fixture uses `yaml.dump` to write YAML (not inline raw strings) to guarantee the Association's aliased keys (`1_mult_2`, `2_mult_1`, `1_phrase_2`, `2_phrase_1`) are present exactly as the schema expects.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Test scaffold is complete; plan 04-02 can immediately unskip MCP-05 tests and implement `render_to_drawio`
- `tmp_domain` fixture is reusable across plans 04-02 and 04-03 without modification

---
*Phase: 04-draw-io-tools*
*Completed: 2026-03-11*
