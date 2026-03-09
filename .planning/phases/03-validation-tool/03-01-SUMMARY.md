---
phase: 03-validation-tool
plan: 01
subsystem: schema
tags: [pydantic, networkx, lark, yaml, state-diagram]

requires:
  - phase: 01-schema-foundation
    provides: StateDiagramFile Pydantic model and test fixtures in test_yaml_schema.py
  - phase: 02-mcp-server-model-io
    provides: stable MCP tool API this validation tool will extend

provides:
  - StateDiagramFile.initial_state required str field (BFS root for graph reachability)
  - networkx>=3.4 runtime dependency installed
  - lark>=1.1 runtime dependency installed
  - All StateDiagramFile test fixtures updated to include initial_state

affects:
  - 03-validation-tool (subsequent plans use initial_state as BFS root)
  - Phase 5 pycca grammar parsing (lark installed and importable)

tech-stack:
  added:
    - networkx>=3.4 (graph analysis for reachability)
    - lark>=1.1 (pycca grammar parsing)
  patterns:
    - Required fields without defaults enforce schema constraints at load time (same as schema_version)
    - initial_state uses no alias — YAML key matches Python field name

key-files:
  created: []
  modified:
    - schema/yaml_schema.py
    - tests/test_yaml_schema.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "initial_state uses no default value — absence of default is the enforcement mechanism (consistent with schema_version pattern)"
  - "initial_state field placed between class_name and events — mirrors YAML author intent; semantic validation (does initial_state name exist in states?) deferred to Phase 3 graph validator"

patterns-established:
  - "Required field enforcement: no default value on Pydantic field — Pydantic raises ValidationError on missing field at parse time"

requirements-completed:
  - MCP-04

duration: 2min
completed: 2026-03-09
---

# Phase 3 Plan 01: Add initial_state Field and Install Graph/Parser Dependencies

**Required `initial_state: str` field added to StateDiagramFile via Pydantic no-default pattern; networkx and lark installed as runtime dependencies; all 31 tests pass.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-09T18:12:00Z
- **Completed:** 2026-03-09T18:13:31Z
- **Tasks:** 2
- **Files modified:** 4 (schema/yaml_schema.py, tests/test_yaml_schema.py, pyproject.toml, uv.lock)

## Accomplishments

- Added `initial_state: str` (required, no default) to `StateDiagramFile` — Pydantic raises ValidationError when absent
- Installed networkx 3.6.1 and lark 1.3.1 via `uv add`; both importable
- Updated `VALID_STATE_DIAGRAM` and the guard-test `bad` dict in test fixtures to include `initial_state: "Idle"`
- All 31 tests across the full test suite pass with zero failures

## Task Commits

Each task was committed atomically:

1. **TDD RED: failing tests for initial_state and deps** - `dc57f69` (test)
2. **Task 1: Add initial_state field + install networkx/lark** - `d30bfba` (feat)
3. **Task 2: Update fixtures to include initial_state** - `59a60ed` (feat)

_Note: TDD tasks have two commits — RED (failing test) then GREEN (implementation)_

## Files Created/Modified

- `schema/yaml_schema.py` - Added `initial_state: str` field to StateDiagramFile between class_name and events
- `tests/test_yaml_schema.py` - Added 3 new tests (missing rejected, accepted, import smoke); updated VALID_STATE_DIAGRAM and guard test bad dict with initial_state
- `pyproject.toml` - Added lark>=1.1 and networkx>=3.4 to dependencies
- `uv.lock` - Updated by uv add (lark 1.3.1, networkx 3.6.1)

## Decisions Made

- `initial_state` has no alias — the YAML key is `initial_state` identical to the Python field name, so no alias needed (unlike `class` which aliases to `class_name`)
- Semantic validation of whether `initial_state` names an actual state in `states` list is explicitly deferred to Phase 3 graph validator — schema layer only enforces presence of the field

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- `StateDiagramFile.initial_state` is available as BFS root for graph reachability analysis in 03-02 and beyond
- networkx imported and ready for graph construction
- lark imported and ready for pycca grammar parsing (Phase 5)

---
*Phase: 03-validation-tool*
*Completed: 2026-03-09*
