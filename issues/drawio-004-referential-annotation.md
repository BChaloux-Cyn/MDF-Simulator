# Draw.io should render referential annotations on attributes

**ID:** DRAWIO-004
**Status:** Open
**Domain/Component:** drawio renderer

## Root Cause

When an attribute has both `identifier` and `referential` fields, the
draw.io renderer currently only shows the identifier tag (e.g., `{I1}`).
The referential should also be displayed alongside it.

**Expected rendering examples:**
- `identifier: 1, referential: R2` → `shaft_id: UniqueID {I1, R2}`
- `identifier: [1, 2], referential: R3` → `floor_num: FloorNumber {I1, I2, R3}`
- `referential: R4` (no identifier) → `some_attr: UniqueID {R4}`

This matches standard Shlaer-Mellor notation where both identity and
formalization are visible on the class box.

## Fix Applied

*Not yet applied.* Update `_attr_label()` in `tools/drawio.py` to
include the referential tag in the suffix when `attr.referential` is set.

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | | | |
