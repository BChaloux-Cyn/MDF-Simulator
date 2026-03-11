# No Domain Diagram Renderer

**ID:** drawio-002
**Status:** Open
**Domain/Component:** tools/drawio.py — domain diagram renderer

## Root Cause

`DOMAINS.yaml` is parsed and validated but there is no `render_to_drawio_domains()`
function. The domain chart (domains as boxes, bridges as directed dashed edges with
operation labels) is never rendered.

## Fix Applied

Not yet applied. Requires:

1. `schema/drawio_schema.py` — add `STYLE_DOMAIN` box style, `domain_box_id()`,
   `bridge_edge_id()` ID functions, add both to `BIJECTION_TABLE` and `__all__`.
   `STYLE_BRIDGE` already exists and can be reused for bridge edges.
2. `tools/drawio.py` — add `render_to_drawio_domains(model_root)` that reads
   `DOMAINS.yaml` and writes `domain-diagram.drawio` alongside it.
   Optionally call it from `render_to_drawio()` as the first step.
3. Tests — fixture with 2 domains + 1 bridge; assert domain boxes and bridge edge exist.

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| tests/test_drawio_tools.py | test_render_domain_diagram | ✗ | |
