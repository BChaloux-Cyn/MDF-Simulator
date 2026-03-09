---
phase: 03-validation-tool
plan: 03
subsystem: validation
tags: [pydantic, networkx, lark, yaml, state-diagram, mcp, validation]

requires:
  - phase: 03-validation-tool
    provides: StateDiagramFile.initial_state field and networkx/lark installed (03-01)
  - phase: 03-validation-tool
    provides: pycca/grammar.py with GUARD_PARSER and STATEMENT_PARSER (03-02)
  - phase: 02-mcp-server-model-io
    provides: _resolve_domain_path, _pydantic_errors_to_issues, MODEL_ROOT pattern

provides:
  - tools/validation.py with validate_model, validate_domain, validate_class
  - Missing-file checks with report_missing=True/False suppression
  - Referential integrity checks covering all named references in class and state diagrams
  - Graph reachability via NetworkX (unreachable states=error, trap states=warning)
  - Bridge operation referential integrity vs DOMAINS.yaml
  - server.py with FastMCP and @mcp.tool registrations for all three validation functions
  - mcp>=1.26.0 runtime dependency installed

affects:
  - 03-04 (guard completeness analysis builds on this validation infrastructure)
  - Phase 5 (simulation imports validated model structure)
  - All agents/skills using validation tools via MCP

tech-stack:
  added:
    - mcp>=1.26.0 (FastMCP server framework for @mcp.tool registrations)
  patterns:
    - Issue accumulator: all three functions accumulate to list[dict] and return — never raise
    - _make_issue: five-field dict (issue, location, value, fix, severity) — extended from model_io pattern
    - Reachability-after-integrity: _check_reachability only runs if initial_state referential integrity passes
    - report_missing suppresses at issue-append point, not at file-read point
    - _validate_domain_data accepts optional domains_file — None for validate_domain/class, populated for validate_model

key-files:
  created:
    - tools/validation.py
    - server.py
    - tests/test_validation.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "validate_domain and validate_class do not load DOMAINS.yaml — bridge referential integrity only fires in validate_model() scope where domains_file is available"
  - "Reachability check guarded by initial_state referential integrity result — avoids nx.descendants() NetworkXError on missing node"
  - "Specializes exception: active subtype class with specializes set skips missing-state-diagram check if state file absent"
  - "server.py uses FastMCP with @mcp.tool() decorator — wrapper functions (validate_model_tool etc.) keep MCP tool names distinct from imported function names"
  - "mcp package installed as blocking Rule 3 deviation — server.py cannot register @mcp.tool without MCP framework; no architectural change (MCP was part of design from day 1)"

patterns-established:
  - "Five-field issue dict: {issue, location, value, fix, severity} — all validation functions produce this format"
  - "Exception firewall: public functions wrap entire body in try/except Exception; all errors converted to issues"
  - "Domain-data helper: _validate_domain_data is the shared core called by all three public functions"

requirements-completed:
  - MCP-04

duration: 15min
completed: 2026-03-09
---

# Phase 3 Plan 03: Validation Tools Implementation Summary

**Three MCP validation tools (validate_model, validate_domain, validate_class) with referential integrity, NetworkX graph reachability, and bridge cross-reference checks registered as FastMCP @mcp.tool in server.py.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-09T18:10:00Z
- **Completed:** 2026-03-09T18:23:45Z
- **Tasks:** 2 (TDD RED + implementation)
- **Files modified:** 5 (tools/validation.py, server.py, tests/test_validation.py, pyproject.toml, uv.lock)

## Accomplishments

- Implemented `validate_model`, `validate_domain`, `validate_class` in `tools/validation.py` — all return `list[dict]`, never raise
- Missing-file checks with `report_missing` flag suppression at append point (not file-read point)
- Referential integrity: association endpoints, specializes/formalizes R-numbers, attribute/method types, initial_state, transition.to/event, bridge operations vs DOMAINS.yaml
- Graph reachability via NetworkX: unreachable states reported as `severity="error"`, trap states as `severity="warning"`
- Created `server.py` with FastMCP and `@mcp.tool` registrations for all three validation functions (plus model I/O tools)
- All 59 tests pass (15 new validation tests + 44 pre-existing)

## Task Commits

Each task was committed atomically:

1. **TDD RED: failing test scaffold for validation tools** - `643d4e1` (test)
2. **implement validation tools and register MCP tools in server.py** - `b13458b` (feat)

_Note: TDD task has two commits — RED (failing test) then GREEN (implementation)_

## Files Created/Modified

- `tools/validation.py` — Three public tool functions + private helpers for missing-file, referential integrity, reachability
- `server.py` — FastMCP server with @mcp.tool registrations for validate_model, validate_domain, validate_class, plus model I/O tools
- `tests/test_validation.py` — 15 tests covering no-raise contract, missing-file, referential integrity, graph reachability
- `pyproject.toml` — Added mcp>=1.26.0 dependency
- `uv.lock` — Updated by uv add (mcp 1.26.0 + transitive deps)

## Decisions Made

- `validate_domain` and `validate_class` do not load `DOMAINS.yaml` — bridge referential integrity only fires in `validate_model()` scope where `domains_file` is passed in. This avoids re-loading DOMAINS.yaml on every domain call and keeps the function boundaries clean.
- Reachability check is guarded by initial_state referential integrity: if `initial_state` not in graph, skip `nx.descendants()` (would raise `NetworkXError`).
- `_validate_domain_data` accepts an optional `domains_file: DomainsFile | None` parameter — `None` when called from `validate_domain`/`validate_class`, populated from the parsed DOMAINS.yaml when called from `validate_model`.
- Active subtype class with `specializes` set skips the missing-state-diagram check if the state file is absent — inherits from supertype.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed mcp package and created server.py from scratch**
- **Found during:** Task 2 (register MCP tools in server.py)
- **Issue:** `server.py` did not exist and `mcp` package was not installed; `@mcp.tool` registration is impossible without the MCP framework
- **Fix:** Ran `uv add mcp` (installs mcp 1.26.0), created `server.py` with FastMCP server pattern and `@mcp.tool()` decorators for all three validation functions plus model I/O tools
- **Files modified:** `server.py` (created), `pyproject.toml`, `uv.lock`
- **Verification:** `uv run python -c "from tools.validation import validate_model, validate_domain, validate_class; print('ok')"` — prints `ok`; `grep validate server.py` shows all three registered
- **Committed in:** `b13458b` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Server.py was always part of the design (CONTEXT.md lists it as an integration point). Creation was necessary to satisfy the must_haves truths. No scope creep.

## Issues Encountered

None beyond the missing server.py and mcp package, which was handled as a Rule 3 deviation above.

## Next Phase Readiness

- Validation tool API stable and tested — Plan 04 (guard completeness) can import `tools/validation.py` helpers
- `server.py` established with FastMCP pattern — future MCP tool registrations follow the same `@mcp.tool()` decorator pattern
- All 59 tests pass; full test suite green

## Self-Check: PASSED

- `tools/validation.py` exists and exports validate_model, validate_domain, validate_class
- `tests/test_validation.py` exists with 15 tests (all passing)
- `server.py` exists with @mcp.tool registrations for all three validation functions
- Commits `643d4e1` and `b13458b` confirmed in git log
- `uv run pytest tests/ -q` → 59 passed

---
*Phase: 03-validation-tool*
*Completed: 2026-03-09*
