---
phase: 01-schema-foundation
plan: "02"
subsystem: testing
tags: [python, pydantic, pydantic-v2, yaml, schema, validation]

requires:
  - phase: 01-schema-foundation-plan-01
    provides: uv-managed mdf-server package with stub yaml_schema.py and skipped test stubs

provides:
  - Full Pydantic v2 model hierarchy for all four MDF YAML file types
  - DomainsFile, ClassDiagramFile, StateDiagramFile, TypesFile — all with required semver schema_version
  - SchemaVersionMixin with SEMVER_RE field_validator
  - Guard all-or-none model_validator on StateDiagramFile
  - Associative formalizes model_validator on ClassDef
  - TypeDef discriminated union (EnumType | StructType | ScalarType)
  - BridgeStanza discriminated union (RequiredBridge | ProvidedBridge)
  - 8 passing pytest tests covering SCHEMA-01 and SCHEMA-02 behaviors

affects:
  - 01-03-PLAN.md (drawio_schema constants — same package)
  - 01-04-PLAN.md (round-trip tests depend on yaml_schema models)
  - 01-05-PLAN.md (template tests may reference schema field names)
  - Phase 2+ MCP tools (yaml_schema is the import contract for all tool implementations)

tech-stack:
  added: []
  patterns:
    - Pydantic v2 field_validator with @classmethod for semver validation
    - Pydantic v2 model_validator(mode='after') for cross-field constraints
    - Plain Union (not discriminated) for ScalarType fallback — ScalarType.base uses model_validator instead of Literal
    - Discriminated union via Annotated[Union[...], Field(discriminator=...)] for TypeDef and BridgeStanza
    - Field(alias=...) + ConfigDict(populate_by_name=True) for YAML keyword fields (from, return, class)
    - groupby + sorted for guard all-or-none consistency check across transition groups

key-files:
  created: []
  modified:
    - mdf-server/mdf_server/schema/yaml_schema.py
    - mdf-server/tests/test_yaml_schema.py

key-decisions:
  - "TypeDef uses plain Union (not discriminated) because ScalarType.base is str, not a Literal — model_validator enforces the primitive set constraint"
  - "BridgeStanza uses Annotated discriminated union on direction field (required | provided) — two structurally distinct bridge types"
  - "SchemaVersionMixin has no default on schema_version — absence of default is the enforcement mechanism for SCHEMA-02"
  - "populate_by_name=True set on all models with aliases — allows tests to use Python field names or YAML key names interchangeably"

patterns-established:
  - "All MDF YAML root models inherit SchemaVersionMixin — schema_version validation is centralized and cannot be bypassed"
  - "Python keyword conflicts (from, return, class) resolved with Field(alias=...) consistently across all models"

requirements-completed:
  - SCHEMA-01
  - SCHEMA-02

duration: 5min
completed: "2026-03-06"
---

# Phase 1 Plan 02: YAML Schema Models Summary

**Complete Pydantic v2 model hierarchy for all four MDF YAML types with semver enforcement, guard all-or-none constraint, and 8 passing tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-06T16:14:00Z
- **Completed:** 2026-03-06T16:19:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- yaml_schema.py implements 20+ Pydantic v2 models covering all four YAML schema types (DOMAINS.yaml, class-diagram.yaml, state-diagrams/<Class>.yaml, types.yaml)
- SchemaVersionMixin enforces semver format on all root models with no default — missing schema_version always raises ValidationError
- Two cross-field model validators: guard all-or-none on StateDiagramFile, formalizes required on associative ClassDef
- All 8 tests in test_yaml_schema.py pass (0 skipped, 0 failed) covering SCHEMA-01 and SCHEMA-02 behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Write yaml_schema.py — full Pydantic v2 model hierarchy** - `f24eba3` (feat)
2. **Task 2: Fill in test_yaml_schema.py with concrete passing tests** - `7898718` (feat)

**Plan metadata:** _(to be added)_

## Files Created/Modified

- `mdf-server/mdf_server/schema/yaml_schema.py` - Full Pydantic v2 model hierarchy: SchemaVersionMixin, DomainsFile, ClassDiagramFile, StateDiagramFile, TypesFile, and all nested models
- `mdf-server/tests/test_yaml_schema.py` - 8 concrete tests with inline dicts, no file I/O — covers positive and negative cases for all four root models

## Decisions Made

- TypeDef uses plain `Union[EnumType, StructType, ScalarType]` (not discriminated) because ScalarType.base accepts any of 5 string primitives — model_validator handles validation after EnumType/StructType both fail left-to-right
- BridgeStanza uses `Annotated[Union[RequiredBridge, ProvidedBridge], Field(discriminator="direction")]` — cleanly separates the two structurally incompatible bridge shapes
- All models with Python-keyword YAML fields use `Field(alias=...)` plus `ConfigDict(populate_by_name=True)` — allows both Python names and YAML names in test dicts

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- yaml_schema.py is the import contract for all downstream plans and phases — it is now stable and complete
- Plan 03 (drawio_schema) can proceed immediately; it imports nothing from yaml_schema
- Plans 04/05 can reference yaml_schema models for round-trip and template test assertions
- Phase 2 MCP tools can `from mdf_server.schema.yaml_schema import DomainsFile, ...` as specified in their plan stubs

## Self-Check: PASSED

All commits verified: f24eba3 (Task 1), 7898718 (Task 2) — both present in git log.
Tests verified: `uv run pytest tests/test_yaml_schema.py -v` → 8 passed, 0 failed, 0 skipped.
Full suite verified: `uv run pytest tests/ -x -q` → 8 passed, 13 skipped, 0 failed.

---
*Phase: 01-schema-foundation*
*Completed: 2026-03-06*
