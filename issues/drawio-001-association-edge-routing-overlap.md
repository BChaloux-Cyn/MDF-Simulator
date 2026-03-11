# Association Edges May Route Through Other Class Boxes

**ID:** drawio-001
**Status:** Open
**Domain/Component:** tools/drawio.py — class diagram renderer

## Root Cause

Draw.io computes edge routing at display time inside its own engine. Our XML specifies
source, target, and anchor points, but the orthogonal router may still path an edge
through an unrelated class box when nodes are tightly packed. We have no way to
predict the rendered route without running Draw.io itself.

A two-pass approach is not viable — Draw.io does not write computed route geometry
back to the XML file unless the user manually drags an edge.

## Fix Applied

Not yet applied. Proposed approaches in priority order:

1. **Explicit waypoints per edge** — compute 2D segment-vs-rectangle intersection
   for each non-self-loop edge and inject `mxPoint` bend nodes that route around
   intervening boxes. Correct but requires a simple edge router implementation.
2. **Wider inter-node spacing** — increase `MARGIN` and canvas multipliers further
   so the layout engine places nodes far enough apart that routing gaps exist.
3. **Accept + document** — the intended Draw.io workflow is to drag nodes after
   import; overlapping edges are a 30-second drag-to-fix.

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| (visual — not unit-testable without running Draw.io) | | | |
