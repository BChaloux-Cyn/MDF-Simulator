---
phase: 03-validation-tool
plan: "04"
subsystem: validation
tags: [guard-completeness, pycca, interval-analysis, enum-checking, tdd]
dependency_graph:
  requires: [03-02, 03-03]
  provides: [guard-completeness-validation]
  affects: [tools/validation.py, tests/test_validation.py]
tech_stack:
  added: [lark (GUARD_PARSER), math (interval analysis)]
  patterns: [TDD red-green, groupby transition grouping, half-open interval normalization]
key_files:
  modified:
    - tools/validation.py
    - tests/test_validation.py
decisions:
  - Guard completeness integrated into _validate_active_class_state_diagram (not _validate_domain_data) — state diagram scope is where guard analysis belongs
  - types_map loaded per state-diagram call (not cached at domain level) — consistency with existing _load_domain_types pattern
  - Integer/Real gap detection reports severity=warning regardless of whether range is defined — plan spec says warning for gaps in both cases
  - Guard variable lookup is event-param-only — class attributes not consulted (requires cross-file lookup that is out of scope)
  - Multiple variables in one (from, event) group silently skipped — cannot determine completeness without grouping by variable
metrics:
  duration_minutes: 12
  completed_date: "2026-03-09"
  tasks_completed: 2
  files_modified: 2
---

# Phase 3 Plan 04: Guard Completeness Validation Summary

**One-liner:** Guard completeness checker using GUARD_PARSER interval analysis and enum coverage for (from_state, event) transition groups.

## What Was Built

Added `_check_guard_completeness` to `tools/validation.py`, integrated into the `_validate_active_class_state_diagram` pipeline after referential integrity and before reachability. The function detects five distinct guard problems:

1. **Multiple unguarded transitions** on the same `(from_state, event)` pair → `severity="error"` (ambiguous)
2. **AND/OR compound guard expressions** → `severity="warning"` (completeness cannot be determined)
3. **String-typed event parameter** used in a guard → `severity="error"` (strings forbidden in guards)
4. **Enum-typed parameter with missing values** not covered by any guard → `severity="error"` naming the missing enum values
5. **Integer/Real interval gaps** between guard expressions → `severity="warning"`

### New Helpers

- `_load_types_map(domain_path)` — loads `types.yaml`, returns `{type_name: TypeDef}` dict or `None` if absent/invalid
- `_normalize_interval(op, value)` — converts `(OP, N)` to a half-open `[lo, hi)` interval using integer-compatible normalization
- `_intervals_cover_range(intervals, lo, hi)` — finds uncovered sub-intervals within a defined range

### Guard Variable Resolution

Guard variables are resolved against the triggering event's `params` list (from `sd.events`). If a variable is not found in the event's params, completeness analysis is silently skipped — cross-file attribute lookup is deferred.

## Test Coverage

Seven new tests added to `tests/test_validation.py`:

| Test | Scenario | Expected |
|------|----------|----------|
| `test_guard_string_type_error` | String param in guard | `severity="error"` |
| `test_guard_enum_missing_value` | Enum missing 1 of 3 values | `severity="error"` with missing name |
| `test_guard_enum_complete` | All 3 enum values covered | no guard issue |
| `test_guard_multiple_unguarded_same_event` | 2 unguarded on same (from, event) | `severity="error"` |
| `test_guard_interval_gap` | `x < 5` and `x > 5` | `severity="warning"` |
| `test_guard_interval_full_coverage` | `x < 5` and `x >= 5` | no gap issue |
| `test_guard_complex_expression_warning` | AND/OR guard | `severity="warning"` |

Full suite: **66 passed, 0 failed**.

## Commits

| Hash | Message |
|------|---------|
| `96c453c` | `test(03-04): add failing guard completeness tests (RED)` |
| `266af61` | `feat(03-04): implement _check_guard_completeness in validation.py` |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `tools/validation.py` modified with `_check_guard_completeness` — FOUND
- `tests/test_validation.py` modified with 7 new tests — FOUND
- Commit `96c453c` — FOUND
- Commit `266af61` — FOUND
- Full test suite: 66 passed — VERIFIED
