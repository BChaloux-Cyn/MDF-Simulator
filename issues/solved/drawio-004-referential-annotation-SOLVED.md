# Draw.io should render referential annotations on attributes

**ID:** DRAWIO-004
**Status:** Solved
**Domain/Component:** drawio renderer

## Root Cause

When an attribute has both `identifier` and `referential` fields, the
draw.io renderer only showed the identifier tag (e.g., `{I1}`). The
referential annotation was not displayed.

## Fix Applied

Updated `_attr_label()` and `_estimate_class_width()` in `tools/drawio.py`
to collect both identifier and referential tags into a single list, then
render them as a combined suffix (e.g., `{I1, R2}`).

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-24 | tools/drawio.py | Updated `_attr_label()` to accept and render `referential` param |
| 2026-03-24 | tools/drawio.py | Updated `_estimate_class_width()` to include referential in width calc |
| 2026-03-24 | tools/drawio.py | Updated call site to pass `a.referential` |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| (visual) | Verified `{I1, R2}` etc. appear in generated drawio XML | Yes (only `{I1}`) | Yes |
