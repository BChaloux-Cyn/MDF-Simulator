---
phase: 03-validation-tool
verified: 2026-03-09T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 3: Validation Tool Verification Report

**Phase Goal:** Structural model errors are caught automatically with actionable, location-specific issue lists — not pass/fail booleans
**Verified:** 2026-03-09
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `validate_model(domain)` returns a list of `{issue, location, value, fix}` objects — never raises an exception, never returns a boolean | VERIFIED | All three public functions wrap entire body in `try/except Exception` and return `list[dict]`. Every issue dict contains all five fields: `issue`, `location`, `value`, `fix`, `severity`. Confirmed live: calling with no model dir returns `[{issue, location, value, fix, severity}]`. Tests `test_validate_model_returns_list`, `test_validate_domain_returns_list`, `test_validate_class_returns_list` all pass. |
| 2 | Unreachable states (states with no incoming transition from reachable states) are detected and reported with state name and domain location | VERIFIED | `_check_reachability` builds `nx.DiGraph`, computes `nx.descendants(G, sd.initial_state)`, reports every state not in `reachable` set as `severity="error"` with the state name and `location=f"{domain}::state-diagrams/{sd.class_name}.yaml::states"`. Confirmed live: 'Orphaned' state with no incoming transitions reports `("State 'Orphaned' is unreachable from initial state 'Idle'", 'error')`. Test `test_unreachable_state_detected` passes. |
| 3 | Trap states (states with no outgoing transitions) are detected and reported | VERIFIED | Same `_check_reachability` function checks `G.out_degree(state) == 0` for every state name and appends `severity="warning"` issue. Confirmed live: 'Opening' and 'Orphaned' (no outgoing transitions) both produce warnings. Test `test_trap_state_warning` passes. |
| 4 | Referential integrity errors (association referencing a class that does not exist, transition targeting a state that does not exist) are reported with specific names | VERIFIED | `_check_referential_integrity_class_diagram` checks `assoc.point_1` and `assoc.point_2` against `class_names` set. `_check_referential_integrity_state_diagram` checks `transition.to` against `state_names`, `transition.event` against `event_names`, and `initial_state` against `state_names`. All report the offending name in both the `issue` string and `value` field. Confirmed live: bad association endpoint and bad transition target both produce errors with the offending name. Tests `test_bad_association_class`, `test_bad_transition_target`, `test_bad_transition_event`, `test_bad_initial_state` all pass. |

**Score:** 4/4 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tools/validation.py` | Three public tool functions, referential integrity, graph reachability, guard completeness | VERIFIED | 1007 lines. Exports `validate_model`, `validate_domain`, `validate_class`. Implements `_check_referential_integrity_class_diagram`, `_check_referential_integrity_state_diagram`, `_check_reachability`, `_check_guard_completeness`. |
| `tests/test_validation.py` | 22 tests covering no-raise contract, missing-file, referential integrity, graph reachability, guard completeness | VERIFIED | 22 tests, all pass. Covers every truth and guard completeness scenario. |
| `server.py` | FastMCP `@mcp.tool` registrations for all three validation functions | VERIFIED | All three registered as `validate_model_tool`, `validate_domain_tool`, `validate_class_tool` with `@mcp.tool()` decorator. |
| `pycca/grammar.py` | `PYCCA_GRAMMAR`, `GUARD_PARSER`, `STATEMENT_PARSER` exports | VERIFIED | Exports all three. `GUARD_PARSER` uses Earley, `STATEMENT_PARSER` uses LALR with Earley fallback. |
| `schema/yaml_schema.py` | `StateDiagramFile` with required `initial_state: str` field | VERIFIED | Line 259: `initial_state: str  # Required — no default`. No default value — Pydantic will reject YAML without it. |
| `pyproject.toml` | `networkx>=3.4`, `lark>=1.1`, `mcp>=1.26.0` dependencies | VERIFIED | All three present on lines 12, 14, 15. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tools/validation.py` | `schema/yaml_schema.py` | `from schema.yaml_schema import ClassDiagramFile, StateDiagramFile, DomainsFile, ...` | WIRED | Line 16-24 of validation.py. All required types imported. |
| `tools/validation.py` | `networkx` | `import networkx as nx; nx.DiGraph(); nx.descendants()` | WIRED | Line 10: `import networkx as nx`. `nx.DiGraph()` at line 356, `nx.descendants()` at line 366. |
| `tools/validation.py` | `tools/model_io.py` | `from tools.model_io import _resolve_domain_path, _pydantic_errors_to_issues` | WIRED | Line 25. Both imported and used (`_resolve_domain_path` called in all three public functions). |
| `tools/validation.py` | `server.py` | `@mcp.tool` registration of all three validation functions | WIRED | `server.py` line 9 imports all three; lines 42, 53, 64 register with `@mcp.tool()`. |
| `tools/validation.py::_check_guard_completeness` | `pycca/grammar.py::GUARD_PARSER` | `from pycca.grammar import GUARD_PARSER; GUARD_PARSER.parse(guard_str)` | WIRED | Line 15: `from pycca.grammar import GUARD_PARSER`. Called at line 512: `tree = GUARD_PARSER.parse(guard_str)`. |
| `tools/validation.py::_check_guard_completeness` | `schema/yaml_schema.py::TypesFile` | `TypesFile.model_validate(data)` in `_load_types_map` | WIRED | `_load_types_map` at line 405: `tf = TypesFile.model_validate(data)`. Called from `_validate_active_class_state_diagram` at line 748. |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MCP-04 | 03-01, 03-02, 03-03, 03-04 | `validate_model(domain)` — returns list of issues: referential integrity, graph reachability (unreachable states, trap states), pycca syntax pre-check; never pass/fail | SATISFIED | All four sub-requirements delivered: (1) list return with no-raise contract, (2) unreachable state detection, (3) trap state detection, (4) referential integrity with specific names. Guard completeness (pycca pre-check) also implemented. 22/22 tests pass. |

---

## Anti-Patterns Found

None identified. Scanned `tools/validation.py`, `pycca/grammar.py`, `server.py`, `tests/test_validation.py`:

- No `TODO`, `FIXME`, `PLACEHOLDER` comments in implementation files.
- No `return null` / `return {}` / `return []` stubs — all empty-list returns are correct accumulator initializations.
- No handlers that only `console.log` / `preventDefault`.
- No API routes returning static data instead of computed results.
- Exception firewall is real: every public function has `try/except Exception` wrapping the full body, converting to issue list.
- `report_missing` suppression is implemented correctly at the issue-append point, not at the file-read point.
- `_check_reachability` correctly guards against `nx.descendants()` call when `initial_state` is not in graph nodes (line 363-364).

---

## Human Verification Required

None. All goal truths are verifiable programmatically through the test suite and live smoke tests. The validation tool is a pure computation (no UI, no real-time behavior, no external service).

---

## Summary

Phase 3 goal is fully achieved. All four success criteria from ROADMAP.md are satisfied:

1. `validate_model()`, `validate_domain()`, and `validate_class()` each return `list[dict]` with five fields (`issue`, `location`, `value`, `fix`, `severity`). The exception firewall (`try/except Exception`) guarantees they never raise. Confirmed by three dedicated tests and live smoke test.

2. Unreachable states are detected via NetworkX BFS from `initial_state`. Each unreachable state produces a `severity="error"` issue naming the state and the `{domain}::state-diagrams/{class}.yaml::states` location. Confirmed by `test_unreachable_state_detected` and live test.

3. Trap states (no outgoing transitions) are detected in the same `_check_reachability` pass using `G.out_degree(state) == 0`. Each produces a `severity="warning"` issue. Confirmed by `test_trap_state_warning` and live test.

4. Referential integrity errors name the offending value: bad association endpoint names the missing class, bad transition target names the missing state, bad event reference names the missing event. All confirmed by dedicated tests and live test producing `| error` output with the offending name visible.

Additional beyond minimum: guard completeness analysis (`_check_guard_completeness`) was also implemented and tested (7 additional tests), covering String-typed guards, enum coverage gaps, integer interval gaps, AND/OR compound expressions, and multiple unguarded ambiguous transitions.

Full test suite: **66 passed, 0 failed**.
Requirement MCP-04: **SATISFIED**.

---

_Verified: 2026-03-09_
_Verifier: Claude (gsd-verifier)_
