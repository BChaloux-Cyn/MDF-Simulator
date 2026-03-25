# Render overwrites user layout changes on state diagrams

**ID:** DRAWIO-003
**Status:** Solved
**Domain/Component:** drawio renderer

## Root Cause

When `render_to_drawio` is called, it regenerated all diagrams from scratch,
discarding any manual layout changes the user made in Draw.io (node positions,
box sizes, edge routing, anchor points). The old skip check (`_structure_matches`)
only compared element IDs — it missed content changes like updated entry actions,
guards, attributes, or method signatures.

## Fix Applied

Replaced the ID-only comparison with a **canonical JSON content comparison**.
Both the YAML source and the existing drawio file are independently decomposed
into the same canonical JSON structure (semantic content, no geometry). If the
two JSON strings are identical, the diagram is up-to-date and rendering is
skipped (preserving user layout). If they differ, a full redraw is triggered.

This catches all change directions:
- YAML changed → redraw
- User edited drawio content (labels) → redraw
- User only moved nodes (geometry) → skip

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-25 | schema/drawio_canonical.py | Created Pydantic models for canonical JSON |
| 2026-03-25 | tools/drawio.py | Added _yaml_to_canonical_state, _yaml_to_canonical_class |
| 2026-03-25 | tools/drawio.py | Added _drawio_to_canonical_state, _drawio_to_canonical_class |
| 2026-03-25 | tools/drawio.py | Replaced _structure_matches_* with _content_matches_* |
| 2026-03-25 | tools/drawio.py | Removed _extract_drawio_ids, _compute_expected_*_ids |
| 2026-03-25 | tools/drawio.py | Fixed html.unescape for entry action round-trip |
| 2026-03-25 | schema/drawio_schema.py | Added horizontalStack=0 to class swimlane styles |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| tests/test_drawio_canonical.py | test_fixture_state_baseline_matches_yaml | N/A | Yes |
| tests/test_drawio_canonical.py | test_fixture_state_geometry_changed_still_matches | N/A | Yes |
| tests/test_drawio_canonical.py | test_fixture_state_structure_changed_does_not_match | N/A | Yes |
| tests/test_drawio_canonical.py | test_fixture_class_baseline_matches_yaml | N/A | Yes |
| tests/test_drawio_canonical.py | test_fixture_class_geometry_changed_still_matches | N/A | Yes |
| tests/test_drawio_canonical.py | test_fixture_class_structure_changed_does_not_match | N/A | Yes |
| tests/test_drawio_canonical.py | test_state_diagram_round_trip | N/A | Yes |
| tests/test_drawio_canonical.py | test_class_diagram_round_trip | N/A | Yes |
| tests/test_drawio_canonical.py | test_content_matches_state_skip_on_geometry_change | N/A | Yes |
| tests/test_drawio_canonical.py | test_content_matches_state_redraw_on_label_change | N/A | Yes |
