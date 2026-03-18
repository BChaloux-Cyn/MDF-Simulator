# Render overwrites user layout changes on state diagrams

**ID:** DRAWIO-003
**Status:** Open
**Domain/Component:** drawio renderer

## Root Cause

When `render_to_drawio` is called with `force=True`, it regenerates all
diagrams from scratch, discarding any manual layout changes the user made
in Draw.io (e.g., repositioning states, adjusting edge routing, adding
visual annotations). If the underlying state machine YAML has not changed,
the diagram should not be regenerated — or at minimum, structural changes
(positions, styles) made by the user should be preserved.

## Fix Applied

*Not yet applied.* Possible approaches:
- Skip regeneration if the YAML source has not changed since the last render
- Merge new content into the existing .drawio XML, preserving user-modified
  geometry and styles for elements that still exist
- Add a `--layout-only` flag that only updates content (labels, new states)
  without touching positions

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | | | |
