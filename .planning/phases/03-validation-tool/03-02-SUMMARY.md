---
phase: 03-validation-tool
plan: 02
subsystem: parser
tags: [lark, pycca, grammar, earley, lalr, action-language]

requires:
  - phase: 03-validation-tool
    provides: lark>=1.1 installed as runtime dependency (03-01)

provides:
  - pycca/grammar.py with PYCCA_GRAMMAR string, GUARD_PARSER (Earley, start=expr), STATEMENT_PARSER (LALR, start=start)
  - All 7 MDF action language statement types parseable via STATEMENT_PARSER
  - Guard expressions (simple_compare, inequality, equality) parseable via GUARD_PARSER
  - Phase 5 can import grammar.py without modification to add a Transformer

affects:
  - 03-validation-tool (03-03+ imports GUARD_PARSER for interval analysis in _check_guard_completeness)
  - Phase 5 simulation (PYCCA_GRAMMAR imported to build Transformer on top)

tech-stack:
  added: []
  patterns:
    - "LALR-with-Earley-fallback: STATEMENT_PARSER attempts LALR compile first; falls back to Earley on GrammarError to prioritize correctness over speed"
    - "Shared grammar string: GUARD_PARSER and STATEMENT_PARSER both compile from PYCCA_GRAMMAR — no duplication"
    - "?expr inline rule: lark ? prefix collapses single-child expression trees, avoiding redundant wrapper nodes"

key-files:
  created:
    - pycca/grammar.py
    - tests/test_pycca_grammar.py
  modified:
    - pycca/__init__.py

key-decisions:
  - "STATEMENT_PARSER uses LALR (faster) with Earley fallback — grammar compiled as LALR successfully; no fallback needed in practice"
  - "simple_compare uses two atom children, not NAME OP NUMBER — supports cardinality expressions as LHS and avoids needing separate rules per operand type; semantic type validation deferred to validator layer"
  - "GUARD_PARSER uses Earley (start=expr); guard expressions can be ambiguous — Earley handles ambiguity gracefully"

patterns-established:
  - "Grammar-as-module: raw grammar string exported as PYCCA_GRAMMAR so Phase 5 can import it and add a Transformer without reimplementing the grammar"

requirements-completed:
  - MCP-04

duration: 5min
completed: 2026-03-09
---

# Phase 3 Plan 02: Pycca Grammar Module Summary

**Lark grammar module for MDF action language with Earley GUARD_PARSER and LALR STATEMENT_PARSER covering all 7 statement types, exported from pycca/grammar.py for use by Phase 3 validator and Phase 5 interpreter.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-09T18:20:00Z
- **Completed:** 2026-03-09T18:25:00Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 3

## Accomplishments

- Created `pycca/grammar.py` exporting PYCCA_GRAMMAR, GUARD_PARSER (Earley), and STATEMENT_PARSER (LALR)
- Grammar covers all 7 MDF statement types: assignment, generate, bridge_call, create, delete, select, if
- GUARD_PARSER.parse("pressure >= 100") returns Tree with data `simple_compare` — ready for interval analysis
- All 13 grammar tests pass; full suite green at 44/44

## Task Commits

Each task was committed atomically:

1. **TDD RED: add failing tests for pycca grammar module** - `99f7c0b` (test)
2. **Task 2: implement pycca/grammar.py lark grammar module** - `04f9590` (feat)

_Note: TDD task has two commits — RED (failing test) then GREEN (implementation)_

## Files Created/Modified

- `pycca/grammar.py` - Lark grammar string + GUARD_PARSER (Earley, start=expr) + STATEMENT_PARSER (LALR, start=start)
- `tests/test_pycca_grammar.py` - 13 tests covering import, all guard expression forms, all 7 statement types
- `pycca/__init__.py` - Updated docstring to document Phase 3 grammar ownership and Phase 5 interpreter scope

## Decisions Made

- STATEMENT_PARSER compiles successfully as LALR — no Earley fallback needed at runtime, but the try/except guard remains for future grammar extensions
- `simple_compare` rule accepts two `atom` children rather than constraining operand types — keeps the grammar syntax-only and defers type validation to the semantic validator layer in 03-03+
- `?expr` prefix on the expr rule inlines single-child trees so `GUARD_PARSER.parse("x < 5")` returns `Tree('simple_compare', ...)` directly rather than a redundant `expr` wrapper

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Self-Check: PASSED

- `pycca/grammar.py` exists and is importable
- `tests/test_pycca_grammar.py` exists with 13 tests
- Commits `99f7c0b` and `04f9590` confirmed in git log
- `uv run pytest tests/ -q` → 44 passed

## Next Phase Readiness

- `from pycca.grammar import GUARD_PARSER` ready for use in `tools/validation.py::_check_guard_completeness`
- `PYCCA_GRAMMAR` string ready for Phase 5 Transformer to import without grammar duplication
- `STATEMENT_PARSER` ready for Phase 5 action block execution

---
*Phase: 03-validation-tool*
*Completed: 2026-03-09*
