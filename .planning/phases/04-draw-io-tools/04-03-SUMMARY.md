---
phase: 04-draw-io-tools
plan: 03
subsystem: api
tags: [drawio, mcp, defusedxml, ruamel-yaml, sync, validation]

# Dependency graph
requires:
  - phase: 04-draw-io-tools plan 02
    provides: render_to_drawio, render_to_drawio_class, render_to_drawio_state, BIJECTION_TABLE
  - phase: 03-validation-tool
    provides: validate_class, validate_domain — called after sync write
provides:
  - validate_drawio(domain, xml) — checks mxCell styles against BIJECTION_TABLE
  - sync_from_drawio(domain, class_name, xml) — merges state topology changes from Draw.io XML to YAML
  - 5 MCP tool wrappers in server.py: render_to_drawio_tool, render_to_drawio_class_tool,
    render_to_drawio_state_tool, validate_drawio_tool, sync_from_drawio_tool
affects:
  - 05-simulation-engine (complete tools/drawio.py public API)
  - any agent/skill using MCP-06/MCP-07

# Tech tracking
tech-stack:
  added: [defusedxml (XML parse), ruamel.yaml (round-trip YAML)]
  patterns:
    - defusedxml.ElementTree.fromstring for safe XML parsing (never lxml for untrusted input)
    - ruamel.yaml round-trip mode for YAML files containing pycca action bodies (preserves comments/formatting)
    - post-sync validation scoped to the class being synced (validate_class, not validate_domain)

key-files:
  created: []
  modified:
    - tools/drawio.py
    - server.py
    - tests/test_drawio_tools.py

key-decisions:
  - "sync_from_drawio signature is (domain, class_name, xml) — per-class scope, not whole-domain, matching tests and stub"
  - "post-sync validation calls validate_class(domain, class_name) not validate_domain — avoids surfacing unrelated class errors from other classes in the same domain"
  - "Unrecognized style check in sync runs on ALL cells (including non-canonical IDs like 'unknown1'), not just colon-containing IDs"
  - "Test fixture bug fixed: added events list to pump_state_diagram so validate_class does not flag unknown event reference"
  - "Trailing-semicolon tolerance in style matching: style.rstrip(';') checked if exact match fails (Draw.io sometimes appends extra semicolon)"

patterns-established:
  - "Style validity check: exact match then rstrip(';') fallback — handles Draw.io trailing semicolons"
  - "ruamel.yaml round-trip: _read_yaml_roundtrip / _write_yaml_roundtrip helpers encapsulate round-trip load/dump"
  - "Sync preservation: existing state dicts in CommentedMap are never touched — only new dicts appended, deleted entries removed"

requirements-completed: [MCP-06, MCP-07]

# Metrics
duration: 25min
completed: 2026-03-11
---

# Phase 4 Plan 03: Draw.io Validation and Sync Summary

**validate_drawio (BIJECTION_TABLE style check) and sync_from_drawio (ruamel.yaml round-trip state merge) implemented; all 5 Draw.io MCP tools registered in server.py**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-11T19:00:00Z
- **Completed:** 2026-03-11T19:25:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `validate_drawio(domain, xml)`: parses XML with defusedxml, checks each mxCell style against `BIJECTION_TABLE.values()` with trailing-semicolon tolerance; returns error issues for unrecognized styles or parse errors
- `sync_from_drawio(domain, class_name, xml)`: loads state YAML with ruamel.yaml round-trip mode, adds/removes states and transitions from Draw.io cells, preserves existing entry_action bodies; calls `validate_class` after write; unrecognized styles produce warning issue and skip (no abort)
- All 5 Draw.io MCP tools registered in server.py and verified via `asyncio.run(mcp.list_tools())`
- 76 tests pass (10 Draw.io tests, 66 from prior phases)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement validate_drawio and sync_from_drawio** - `e2e039b` (feat, TDD GREEN)
2. **Task 2: Register all 5 Draw.io MCP tools in server.py** - `df2903d` (feat)

## Files Created/Modified

- `tools/drawio.py` - Added validate_drawio and sync_from_drawio; new imports (defusedxml, ruamel.yaml, re, io, BIJECTION_TABLE); replaced stubs with full implementations
- `server.py` - Added import of 5 drawio functions; added 5 @mcp.tool() wrappers
- `tests/test_drawio_tools.py` - Removed 6 @pytest.mark.skip decorators; fixed pump_state_diagram fixture to include events list

## Decisions Made

- `sync_from_drawio` uses 3-arg signature `(domain, class_name, xml)` — the test file and existing stub both used this signature; the plan's 2-arg interface description was inconsistent with the tests
- Post-sync validation scoped to `validate_class(domain, class_name)` rather than `validate_domain` — avoids surfacing unrelated class-diagram errors (unknown types in other classes) that would break test assertions about a clean sync
- Style check in sync runs on ALL cells with a style attribute before the canonical-ID check — ensures cells with non-canonical IDs (e.g. `id="unknown1"`) still get flagged for unrecognized styles
- Test fixture amended to add `events: [{name: Start}]` to the pump state diagram — the existing transition referenced event `Start`, which was flagged as unknown by the validator; this was a fixture bug (Rule 1)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixture missing events definition**
- **Found during:** Task 1 (GREEN step — test_sync_runs_validate_model failing)
- **Issue:** pump_state_diagram fixture had transition referencing event `Start` but no `events` list; validate_class flagged "unknown event 'Start'" as error-severity, causing test_sync_runs_validate_model to fail
- **Fix:** Added `events: [{name: Start}]` to pump_state_diagram fixture
- **Files modified:** tests/test_drawio_tools.py
- **Verification:** test_sync_runs_validate_model passes with no error-severity issues
- **Committed in:** e2e039b (Task 1 commit)

**2. [Rule 1 - Bug] Fixed unrecognized style check skipping non-canonical-ID cells**
- **Found during:** Task 1 (GREEN step — test_sync_unrecognized_cell failing)
- **Issue:** Style validity check was gated behind `":" in cell_id`, so cell `id="unknown1"` was never checked and no "unrecognized" issue was produced
- **Fix:** Moved style check before the canonical-ID gate so all cells with a style attribute are checked
- **Files modified:** tools/drawio.py
- **Verification:** test_sync_unrecognized_cell passes with at least 1 "unrecognized" issue
- **Committed in:** e2e039b (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs in test fixture / implementation)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered

- `FastMCP` object has no `_tools` attribute — verification command in plan used wrong API; used `asyncio.run(mcp.list_tools())` instead. No impact on implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 (Draw.io Tools) is now complete — all 5 MCP tools registered and tested
- Phase 5 (Simulation Engine) can proceed; the stable MCP tool API is fully available
- `tools/drawio.py` public API: `render_to_drawio`, `render_to_drawio_class`, `render_to_drawio_state`, `validate_drawio`, `sync_from_drawio`

---
*Phase: 04-draw-io-tools*
*Completed: 2026-03-11*
