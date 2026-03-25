# Association Edges May Route Through Other Class Boxes

**ID:** drawio-001
**Status:** Solved
**Domain/Component:** tools/drawio.py — class/state diagram renderer

## Root Cause

Two issues contributed to edge overlap in rendered diagrams:

1. **Box routing** — Draw.io's orthogonal router could path edges through unrelated boxes
   when nodes were tightly packed. Addressed by `_optimize_edge_routing()` which uses
   3-pass iterative side selection with Liang-Barsky slab-test blocking detection and
   `mxPoint` waypoint injection to route around intervening boxes.

2. **Bidirectional edge overlap** — When two states have transitions in both directions
   (e.g., Moving→Floor_Updating and Floor_Updating→Moving), Draw.io's orthogonal router
   collapses them into the same corridor, making them appear as a single line.

## Fix Applied

**Box-avoidance routing** (pre-existing): `_optimize_edge_routing()` tries all 16
exit/entry side combinations per edge, scores by box crossings + edge crossings + path
length, and injects detour waypoints around blocking boxes. `_remove_overlaps()` ensures
minimum node spacing.

**Bidirectional edge separation** (this fix): After the anchor-spreading pass in
`_optimize_edge_routing()`, detect edges sharing the same two vertices (in opposite
directions) and:

1. Nudge port fractions apart along the shared face (`BIDIR_PORT_GAP = 0.12`)
2. Add two waypoints per edge at a direction-aware turn X: the edge going toward
   the target turns at `mid_x + BIDIR_SPREAD/2` (toward target), so the vertical
   segments of the two edges don't cross each other's horizontal runs.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-25 | tools/drawio.py | Added bidirectional pair detection and offset waypoint injection in `_optimize_edge_routing()` |
| 2026-03-25 | tests/test_drawio_tools.py | Added `test_optimize_routing_separates_bidirectional_edges` |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| tests/test_drawio_tools.py | test_optimize_routing_separates_bidirectional_edges | Yes | Yes |
