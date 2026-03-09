---
phase: 01-schema-foundation
plan: 05
subsystem: testing
tags: [templates, yaml, markdown, pytest, pydantic, mdf]

# Dependency graph
requires:
  - phase: 01-01
    provides: project structure, mdf-server layout, test stub patterns established
provides:
  - 6 template files in templates/ — scaffold for /mdf:new-project skill (Phase 9)
  - DOMAINS.yaml.tmpl with schema_version, domains list, bridges list
  - CLASS_DIAGRAM.yaml.tmpl with entity, active, associative class examples
  - STATE_DIAGRAM.yaml.tmpl with events, states, transitions, guards
  - behavior-domain.md.tmpl with Purpose, Scope, Bridge Contracts sections
  - behavior-class.md.tmpl with Purpose, Attributes, Lifecycle, Methods sections
  - behavior-state.md.tmpl with Purpose, States, Event Catalog sections
  - 9 passing tests in mdf-server/tests/test_templates.py (SCHEMA-05, TMPL-01..04)
affects:
  - Phase 9 (/mdf:new-project skill copies these templates into new project .design/)
  - Any plan that references templates/ directory

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Template files use .tmpl extension so editors treat them as plain text by default"
    - "Templates are populated examples with placeholder syntax <FieldName> — not empty skeletons"
    - "YAML templates start with schema_version as the first field (SCHEMA-02 requirement)"
    - "Behavior doc templates use ## headings matching CONTEXT.md behavior doc format exactly"

key-files:
  created:
    - templates/DOMAINS.yaml.tmpl
    - templates/CLASS_DIAGRAM.yaml.tmpl
    - templates/STATE_DIAGRAM.yaml.tmpl
    - templates/behavior-domain.md.tmpl
    - templates/behavior-class.md.tmpl
    - templates/behavior-state.md.tmpl
  modified:
    - mdf-server/tests/test_templates.py

key-decisions:
  - "Templates use <PlaceholderName> syntax (angle-bracket) to signal fill-in-the-blank fields — consistent with existing CONTEXT.md structure"
  - "No yaml-language-server schema comments in YAML templates — Pydantic is the validator, not JSON Schema"

patterns-established:
  - "Stub-to-concrete pattern: @pytest.mark.skip stubs replaced with real assertions in the implementing plan"

requirements-completed: [SCHEMA-05, TMPL-01, TMPL-02, TMPL-03, TMPL-04]

# Metrics
duration: 8min
completed: 2026-03-06
---

# Phase 1 Plan 05: Template Files and Tests Summary

**6 YAML and Markdown template files seeding /mdf:new-project with populated schema-version-stamped scaffolds; 9 template tests converted from skipped stubs to passing assertions**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-06T17:18:50Z
- **Completed:** 2026-03-06T17:26:30Z
- **Tasks:** 2
- **Files modified:** 7 (6 created, 1 rewritten)

## Accomplishments

- Created templates/ directory at repo root with exactly 6 template files
- All YAML templates start with schema_version per SCHEMA-02 requirement
- All behavior doc templates contain the exact section headers required by SCHEMA-05
- Replaced all 9 @pytest.mark.skip stubs with concrete passing assertions
- Full test suite: 24 passed, 2 skipped (no regressions)

## Task Commits

1. **Task 1: Create all six template files in templates/** - `831c58d` (feat)
2. **Task 2: Fill in test_templates.py with concrete passing tests** - `90fdea8` (feat)

## Files Created/Modified

- `templates/DOMAINS.yaml.tmpl` - DOMAINS.yaml scaffold with schema_version, domains, bridges
- `templates/CLASS_DIAGRAM.yaml.tmpl` - Class diagram scaffold with entity, active, associative examples and bridge sections
- `templates/STATE_DIAGRAM.yaml.tmpl` - State diagram scaffold with events, states, transitions, guards
- `templates/behavior-domain.md.tmpl` - Domain behavior doc with Purpose, Scope, Bridge Contracts
- `templates/behavior-class.md.tmpl` - Class behavior doc with Purpose, Attributes, Lifecycle, Methods
- `templates/behavior-state.md.tmpl` - State machine behavior doc with Purpose, States, Event Catalog
- `mdf-server/tests/test_templates.py` - 9 concrete tests replacing skip stubs (SCHEMA-05, TMPL-01..04)

## Decisions Made

- Templates use `<PlaceholderName>` angle-bracket syntax for fill-in-the-blank fields, consistent with CONTEXT.md structure.
- No `# yaml-language-server: $schema=` comments in YAML templates — Pydantic is the validator, not a JSON Schema file.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All Phase 1 templates complete; ready for Phase 9 (/mdf:new-project skill)
- Phase 1 schema foundation plans 01-04 cover Pydantic schema, Draw.io bijection, validator, and round-trip — this plan (05) completes the template layer
- No blockers

---
*Phase: 01-schema-foundation*
*Completed: 2026-03-06*
