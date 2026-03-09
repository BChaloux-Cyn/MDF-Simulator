---
phase: 01-schema-foundation
plan: "04"
subsystem: schema
tags: [drawio, lxml, defusedxml, xml, round-trip, uml]

requires:
  - phase: 01-02
    provides: drawio_schema.py bijection constants and ID generator functions
  - phase: 01-03
    provides: complete BIJECTION_TABLE and all 7 SCHEMA-03 tests passing

provides:
  - render_sample_xml() function in drawio_schema.py generating uncompressed Draw.io mxfile XML
  - 2 passing automated round-trip tests in test_roundtrip.py (well-formedness + structural equality)
  - Human-confirmed Draw.io open-save-reparse cycle with all 5 canonical IDs surviving
  - STYLE_SEPARATOR constant and separator_id() for UML class two-section layout
  - visibility and scope fields on Attribute and visibility on Method in yaml_schema.py
  - UML label helpers _attr_label and _method_label with +/-/# prefix and class-scope underline

affects:
  - 01-05
  - Phase 2 (model_io parser): canonical ID format confirmed, compressed=false is the safe mode
  - Phase 4 (rendering tools): render_sample_xml() pattern is the reference implementation

tech-stack:
  added: [lxml (etree XML builder), defusedxml (safe XML parsing for tests)]
  patterns:
    - "compressed=false on mxfile root — prevents base64/zlib save by Draw.io"
    - "Two-section UML swimlane: attributes above STYLE_SEPARATOR, methods below"
    - "Visibility UML prefix: + public, - private, # protected via _VIS dict"
    - "Class-scope members HTML-underlined (<u>name</u>) with html=1 in STYLE_ATTRIBUTE"
    - "TDD: write failing import-level test first, then implement, then verify GREEN"

key-files:
  created:
    - mdf-server/tests/test_roundtrip.py
    - .gitignore
  modified:
    - mdf-server/mdf_server/schema/drawio_schema.py
    - mdf-server/mdf_server/schema/yaml_schema.py
    - mdf-server/tests/test_drawio_schema.py
    - mdf-server/tests/test_yaml_schema.py
    - templates/CLASS_DIAGRAM.yaml.tmpl
    - .planning/STATE.md
    - .planning/phases/01-schema-foundation/01-CONTEXT.md

key-decisions:
  - "compressed=false set on mxfile element — Draw.io will not base64-encode diagram content on save, making saved files directly parseable"
  - "STYLE_SEPARATOR added to BIJECTION_TABLE — two-section UML class layout (attributes / methods) requires explicit divider cell"
  - "Attribute gains visibility (default private) and scope (default instance); Method gains visibility — enables UML +/-/# rendering from YAML"
  - "File-per-diagram-type structure: class-diagram.yaml maps to class-diagram.drawio, not one file per domain with pages"
  - "render_sample_xml() is test-only; it is the reference pattern for Phase 4 rendering tools"

patterns-established:
  - "render_sample_xml() pattern: use lxml etree, STYLE_* constants, ID functions, compressed=false"
  - "Attribute/Method labels: _attr_label/_method_label helpers encode visibility+scope into UML string"

requirements-completed: [SCHEMA-04]

duration: ~60min
completed: 2026-03-06
---

# Phase 01 Plan 04: Draw.io Round-Trip Test Summary

**render_sample_xml() generates valid uncompressed Draw.io mxfile XML confirmed parseable before and after a real Draw.io open-save cycle; UML visibility/scope fields and two-section class layout locked into schema and bijection**

## Performance

- **Duration:** ~60 min
- **Completed:** 2026-03-06
- **Tasks:** 2 (1 automated TDD + 1 human-verify checkpoint)
- **Files modified:** 8

## Accomplishments

- `render_sample_xml()` builds a representative Draw.io XML (2 classes, 1 association, 2 states, 1 transition, initial pseudostate) using lxml and the canonical STYLE_* constants
- 2 automated tests pass: well-formedness via defusedxml and structural equality by canonical mxCell ID
- Human-verified: all 5 canonical IDs (Valve class, ActuatorPosition class, Idle state, Opening state, Idle->Opening transition) show FOUND after real Draw.io open-save
- Design refinements discovered during verification: STYLE_SEPARATOR, visibility/scope fields, two-section UML layout, UML label helper functions
- 28 total tests pass (up from 26)

## Task Commits

1. **Task 1: Add render_sample_xml() and implement test_roundtrip.py** - `5e0ffa1` (feat)
2. **Design refinements from Draw.io verification** - `32466e4` (feat)
3. **Add .gitignore** - `7cf4dd9` (chore)

## Files Created/Modified

- `mdf-server/mdf_server/schema/drawio_schema.py` - Added render_sample_xml(), STYLE_SEPARATOR, separator_id(), _attr_label/_method_label helpers; fixed STYLE_ATTRIBUTE (html=1, verticalAlign=top); removed childLayout=stackLayout; reduced state arcSize to 10
- `mdf-server/tests/test_roundtrip.py` - Created with 2 passing SCHEMA-04 automated tests
- `mdf-server/mdf_server/schema/yaml_schema.py` - Added visibility (default private) and scope (default instance) to Attribute; visibility to Method
- `mdf-server/tests/test_yaml_schema.py` - 2 new tests for visibility/scope defaults and explicit values
- `mdf-server/tests/test_drawio_schema.py` - Updated imports and REQUIRED_ELEMENT_TYPES to include separator
- `templates/CLASS_DIAGRAM.yaml.tmpl` - Added visibility and scope fields to attribute and method blocks
- `.gitignore` - Created: __pycache__, *.pyc, lock files
- `.planning/STATE.md` - Recorded file-per-diagram-type layout decision
- `.planning/phases/01-schema-foundation/01-CONTEXT.md` - Documented one-.drawio-per-diagram-type file structure

## Decisions Made

- `compressed="false"` on mxfile is mandatory — prevents base64/zlib encoding on save, making saved files directly parseable without decompression
- `STYLE_SEPARATOR` added to bijection table — two-section UML swimlane (attributes above line, methods below) requires a distinct divider cell type
- `Attribute.visibility` and `Attribute.scope` default to `"private"` and `"instance"` respectively — absence in YAML means private instance member
- File-per-diagram-type (not file-per-domain with pages): `class-diagram.yaml` → `class-diagram.drawio`, `state-diagrams/Valve.yaml` → `state-diagrams/Valve.drawio`

## Deviations from Plan

The plan specified Task 1 (automated TDD) + Task 2 (human-verify). The human-verify checkpoint revealed design refinements not in the original plan scope.

### Out-of-Plan Refinements (approved by user during checkpoint)

**1. [Rule 2 - Missing Critical] UML visibility and scope fields on Attribute/Method**
- **Found during:** Task 2 human-verify (Draw.io inspection revealed attributes render without UML visibility markers)
- **Issue:** Attributes and methods lacked visibility (+/-/#) and class-scope underline — needed to produce correct UML notation in render_sample_xml()
- **Fix:** Added `visibility` and `scope` to `Attribute`; `visibility` to `Method`; added `_attr_label`/`_method_label` helpers; added `_VIS` dict
- **Files modified:** yaml_schema.py, drawio_schema.py, test_yaml_schema.py, templates/CLASS_DIAGRAM.yaml.tmpl
- **Committed in:** `32466e4`

**2. [Rule 2 - Missing Critical] STYLE_SEPARATOR for two-section class layout**
- **Found during:** Task 2 human-verify (class swimlane lacked attribute/method divider)
- **Fix:** Added `STYLE_SEPARATOR`, `separator_id()`, entry in `BIJECTION_TABLE`; updated test_drawio_schema.py imports and REQUIRED_ELEMENT_TYPES
- **Committed in:** `32466e4`

**3. [Rule 1 - Bug] STYLE_ATTRIBUTE style corrections**
- **Found during:** Task 2 human-verify (attribute text rendering issues in Draw.io)
- **Fix:** Added `html=1`, `overflow=hidden`, `rotatable=0`; changed `verticalAlign` from `middle` to `top`; removed `childLayout=stackLayout` from STYLE_CLASS
- **Committed in:** `32466e4`

---

**Total deviations:** 3 out-of-plan refinements, all approved by user
**Impact on plan:** All refinements essential for correct UML rendering. SCHEMA-04 round-trip confirmed. No scope creep beyond what Draw.io verification revealed.

## Issues Encountered

None during automated tasks. Draw.io verification revealed rendering gaps that were addressed as design refinements.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SCHEMA-04 signed off: bijection survives real Draw.io round-trip with compressed=false
- All 5 canonical IDs (class, state, transition) confirmed stable across open-save cycle
- render_sample_xml() is the reference pattern for Phase 4 rendering tool implementation
- UML visibility/scope schema fields locked — Phase 2 parser can read and propagate them
- 28 tests passing across all schema modules

---
*Phase: 01-schema-foundation*
*Completed: 2026-03-06*
