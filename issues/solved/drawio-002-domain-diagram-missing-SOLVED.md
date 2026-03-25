# No Domain Diagram Renderer

**ID:** drawio-002
**Status:** Solved
**Domain/Component:** tools/drawio.py — domain diagram renderer

## Root Cause

`DOMAINS.yaml` is parsed and validated but there is no `render_to_drawio_domains()`
function. The domain chart (domains as boxes, bridges as directed dashed edges with
operation labels) is never rendered.

## Fix Applied

1. **schema/drawio_schema.py** — Added `STYLE_DOMAIN` box style constant, `domain_box_id()`
   and `bridge_edge_id()` ID functions. Updated `BIJECTION_TABLE` to include domain and
   bridge edge ID mappings, and added both functions to `__all__`.

2. **tools/drawio.py** — Added `render_to_drawio_domains()` function that reads `DOMAINS.yaml`
   and writes `domain-diagram.drawio` alongside it. Added helper functions `_build_domain_diagram_xml()`,
   `_compute_expected_domain_ids()`, and `_structure_matches_domains()`. Wired into
   `render_to_drawio()` orchestrator as the first rendering step.

3. **Tests** — Added comprehensive test suite covering schema additions and rendering logic,
   including fixtures for domain test data.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-25 | schema/drawio_schema.py | Added STYLE_DOMAIN, domain_box_id(), bridge_edge_id(), updated BIJECTION_TABLE and __all__ |
| 2026-03-25 | tools/drawio.py | Added render_to_drawio_domains(), _build_domain_diagram_xml(), _compute_expected_domain_ids(), _structure_matches_domains(); wired into render_to_drawio() |
| 2026-03-25 | tests/test_drawio_schema.py | Added 4 tests for schema additions |
| 2026-03-25 | tests/test_drawio_tools.py | Added tmp_domains fixture, 5 tests (basic render, content assertions, no bridges, missing file, skip unchanged) |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| tests/test_drawio_schema.py | test_style_domain_exists | Yes | Yes |
| tests/test_drawio_schema.py | test_domain_box_id | Yes | Yes |
| tests/test_drawio_schema.py | test_bridge_edge_id | Yes | Yes |
| tests/test_drawio_schema.py | test_bijection_table_has_domain | Yes | Yes |
| tests/test_drawio_tools.py | test_render_domain_diagram | Yes | Yes |
| tests/test_drawio_tools.py | test_domain_diagram_contains_expected_cells | Yes | Yes |
| tests/test_drawio_tools.py | test_render_domain_diagram_no_bridges | Yes | Yes |
| tests/test_drawio_tools.py | test_render_domain_diagram_missing_file | Yes | Yes |
| tests/test_drawio_tools.py | test_render_domain_diagram_skips_when_unchanged | Yes | Yes |
| tests/test_drawio_tools.py | test_render_to_drawio_includes_domain_diagram | Yes | Yes |
