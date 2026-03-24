"""
drawio — Draw.io rendering, validation, and sync tools.

Implemented in plan 04-02 (Phase 4).
validate_drawio and sync_from_drawio added in plan 04-03.

Public API:
    render_to_drawio(domain)           -> list[dict]
    render_to_drawio_class(domain)     -> list[dict]
    render_to_drawio_state(domain, class_name) -> list[dict]
    validate_drawio(domain, xml)       -> list[dict]
    sync_from_drawio(domain, class_name, xml) -> list[dict]
"""
from __future__ import annotations

import html
import io
import math
import re
from itertools import combinations
from pathlib import Path

import defusedxml.ElementTree as DET
import igraph as ig
import yaml
from lxml import etree
from ruamel.yaml import YAML as RuamelYAML

from schema.drawio_schema import (
    BIJECTION_TABLE,
    STYLE_ASSOC_LABEL,
    STYLE_ASSOCIATION,
    STYLE_ATTRIBUTE,
    STYLE_CLASS,
    STYLE_CLASS_ACTIVE,
    STYLE_GENERALIZATION,
    STYLE_INITIAL_PSEUDO,
    STYLE_SEPARATOR,
    STYLE_STATE,
    STYLE_TRANSITION,
    association_id,
    association_label_id,
    class_id,
    separator_id,
    state_id,
    transition_id,
)
from schema.yaml_schema import ClassDiagramFile, StateDiagramFile

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

HEADER_H = 26    # swimlane startSize
ROW_H = 20       # px per attr/method row
SEP_H = 8        # separator height
CLASS_W = 220    # fixed class width
STATE_W = 160    # fixed state width
STATE_H = 50     # fixed state height (minimum)
INIT_SIZE = 20   # initial pseudostate diameter
MARGIN = 120     # canvas margin
LABEL_OFFSET_X = "-0.3"   # edge-label x: toward source (-1 to +1)
LABEL_OFFSET_Y = "-15"    # edge-label y: pixels above the line
LABEL_PERP_OFFSET = 5     # px perpendicular from edge to label vertex (mult/phrase on opposite sides)
PHRASE_TARGET_RATIO = 2.0 # target width:height ratio for action phrase wrapping

# Self-loop corner pairs: (exitX, exitY, entryX, entryY)
# Each pair uses two adjacent sides of the box to form a tight corner loop.
# Assigned round-robin when a vertex has multiple self-loops.
_SELF_LOOP_CORNERS = [
    (1.0, 0.2,  0.8,  0.0),   # top-right corner
    (1.0, 0.8,  0.8,  1.0),   # bottom-right corner
    (0.2, 1.0,  0.0,  0.8),   # bottom-left corner
    (0.2, 0.0,  0.0,  0.2),   # top-left corner
]

MODEL_ROOT = Path(".design/model")

_VIS = {"public": "+", "private": "-", "protected": "#"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _make_issue(
    issue: str,
    location: str,
    value: object = None,
    fix: str | None = None,
    severity: str = "error",
) -> dict:
    """Build an issue dict matching the tools/validation.py pattern."""
    return {
        "issue": issue,
        "location": location,
        "value": value,
        "fix": fix,
        "severity": severity,
    }


def _class_height(n_attrs: int, n_methods: int) -> int:
    """Return total height of a UML class swimlane cell."""
    return HEADER_H + max(n_attrs, 1) * ROW_H + SEP_H + max(n_methods, 1) * ROW_H


def _state_height(entry_action: str | None) -> int:
    """Estimate state box height from entry_action line count."""
    if not entry_action:
        return STATE_H
    n_lines = entry_action.count('\n') + 1
    # name row + divider + "entry /" row + action lines + vertical padding
    h = (3 + n_lines) * ROW_H
    return max(STATE_H, h)


_STATE_CHARS_PER_PX = 7.2   # approximate px per character for Courier New 11px (monospace)
_STATE_PAD_X = 10            # horizontal padding (each side)


def _state_width(state_name: str, entry_action: str | None) -> int:
    """Estimate state box width from the longest text line."""
    lines: list[str] = [state_name]
    if entry_action:
        lines += entry_action.split('\n')
    max_chars = max(len(line) for line in lines)
    return max(STATE_W, int(max_chars * _STATE_CHARS_PER_PX))


def _assign_edge_ports(
    edges: list[tuple[int, int]],
    positions: list[tuple[float, float]],
) -> list[str]:
    """Return per-edge style suffix strings for exit/entry anchor points.

    Distributes multiple edges from/to the same vertex side across distinct anchor points.
    Self-loops return empty string (let Draw.io auto-route).
    """
    if not edges or not positions:
        return [""] * len(edges)

    # First pass: determine which side each edge exits/enters
    edge_info = []
    for src, tgt in edges:
        if src == tgt:
            edge_info.append(None)
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        dx = tx - sx
        dy = ty - sy
        if abs(dx) >= abs(dy):
            src_side = "right" if dx >= 0 else "left"
            tgt_side = "left" if dx >= 0 else "right"
        else:
            src_side = "bottom" if dy >= 0 else "top"
            tgt_side = "top" if dy >= 0 else "bottom"
        edge_info.append((src, src_side, tgt, tgt_side))

    # Group all connections on a vertex-side together (exits AND entries pooled).
    # Pooling prevents bidirectional edges from independently landing on the same
    # anchor: A→B and B→A both touch B's left side and must share that space.
    side_slots: dict[tuple, list[tuple[int, str]]] = {}  # (vertex, side) → [(idx, direction)]
    for idx, info in enumerate(edge_info):
        if info is None:
            continue
        src, src_side, tgt, tgt_side = info
        side_slots.setdefault((src, src_side), []).append((idx, "exit"))
        side_slots.setdefault((tgt, tgt_side), []).append((idx, "entry"))

    # Build per-edge port data with defaults
    port_data: list[dict] = [
        {"exitX": 0.5, "exitY": 1.0, "entryX": 0.5, "entryY": 0.0}
        for _ in edges
    ]

    def side_coords(side: str, k: int, n: int) -> tuple[float, float]:
        t = (k + 1) / (n + 1)
        if side == "top":
            return t, 0.0
        elif side == "bottom":
            return t, 1.0
        elif side == "left":
            return 0.0, t
        else:  # right
            return 1.0, t

    for (vertex, side), slot_list in side_slots.items():
        n = len(slot_list)
        # Sort by position of the other endpoint along the side's spreading axis so
        # anchor order matches spatial order — minimises edge crossings at the border.
        dim = 0 if side in ("top", "bottom") else 1
        sorted_slots = sorted(
            slot_list,
            key=lambda item: positions[edges[item[0]][1 if item[1] == "exit" else 0]][dim],
        )
        for k, (idx, direction) in enumerate(sorted_slots):
            x, y = side_coords(side, k, n)
            if direction == "exit":
                port_data[idx]["exitX"] = x
                port_data[idx]["exitY"] = y
            else:
                port_data[idx]["entryX"] = x
                port_data[idx]["entryY"] = y

    result = []
    for idx, (src, tgt) in enumerate(edges):
        if src == tgt:
            result.append("")  # self-loops handled by XML builders with waypoints
            continue
        pd = port_data[idx]
        suffix = (
            f"exitX={round(pd['exitX'], 4)};exitY={round(pd['exitY'], 4)};"
            f"exitDx=0;exitDy=0;"
            f"entryX={round(pd['entryX'], 4)};entryY={round(pd['entryY'], 4)};"
            f"entryDx=0;entryDy=0;"
        )
        result.append(suffix)

    return result


def _self_loop_corner(
    vertex: int,
    loop_idx: int,
    all_edges: list[tuple[int, int]],
    positions: list[tuple[float, float]],
) -> int:
    """Return corner index (0=top-right, 1=bottom-right, 2=bottom-left, 3=top-left).

    Picks the corner whose two adjacent sides have the fewest non-self-loop connections
    already attached to this vertex. Cycles through corners for multiple self-loops.
    """
    side_count: dict[str, int] = {"top": 0, "bottom": 0, "left": 0, "right": 0}
    for src, tgt in all_edges:
        if src == tgt:
            continue
        if src != vertex and tgt != vertex:
            continue
        if not positions or src >= len(positions) or tgt >= len(positions):
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        dx, dy = tx - sx, ty - sy
        if abs(dx) >= abs(dy):
            if src == vertex:
                side_count["right" if dx >= 0 else "left"] += 1
            else:
                side_count["left" if dx >= 0 else "right"] += 1
        else:
            if src == vertex:
                side_count["bottom" if dy >= 0 else "top"] += 1
            else:
                side_count["top" if dy >= 0 else "bottom"] += 1

    # Score each corner by (a) combined side occupancy and (b) proximity of other
    # nodes in that corner's outward quadrant.  Corners pointing toward nearby boxes
    # are penalised so the self-loop routes into open space.
    corner_sides = [
        ("right", "top"),     # 0: top-right
        ("right", "bottom"),  # 1: bottom-right
        ("bottom", "left"),   # 2: bottom-left
        ("top",   "left"),    # 3: top-left
    ]
    # Outward quadrant direction for each corner (dx_sign, dy_sign)
    corner_quadrants = [(1, -1), (1, 1), (-1, 1), (-1, -1)]
    vx, vy = positions[vertex]
    proximity: list[float] = []
    for qdx, qdy in corner_quadrants:
        min_dist = float("inf")
        for j, (nx, ny) in enumerate(positions):
            if j == vertex:
                continue
            dx, dy = nx - vx, ny - vy
            if dx * qdx > 0 and dy * qdy > 0:
                min_dist = min(min_dist, math.hypot(dx, dy))
        proximity.append(0.0 if min_dist == float("inf") else 1.0 / min_dist)

    scores = sorted(
        range(len(corner_sides)),
        key=lambda i: (
            side_count[corner_sides[i][0]] + side_count[corner_sides[i][1]],
            proximity[i],
            i,
        ),
    )
    return scores[loop_idx % len(scores)]


def _self_loop_waypoints(
    corner_idx: int,
    bx: float,
    by: float,
    box_w: int,
    box_h: int,
    offset: int = 40,
) -> list[tuple[float, float]]:
    """Return 3 exterior waypoints that force a clean orthogonal self-loop around a corner.

    WP1: straight out from the exit anchor (perpendicular to exit side)
    WP2: the exterior corner connecting WP1 and WP3
    WP3: straight out from the entry anchor (perpendicular to entry side)

    This guarantees 4 right-angle segments:
        exit → WP1 → WP2 → WP3 → entry
    """
    ex, ey, nx, ny = _SELF_LOOP_CORNERS[corner_idx]
    epx = bx + ex * box_w  # exit pixel x
    epy = by + ey * box_h  # exit pixel y
    npx = bx + nx * box_w  # entry pixel x
    npy = by + ny * box_h  # entry pixel y

    if corner_idx == 0:    # top-right: exit right, entry top
        wp1 = (epx + offset, epy)
        wp2 = (epx + offset, npy - offset)
        wp3 = (npx,          npy - offset)
    elif corner_idx == 1:  # bottom-right: exit right, entry bottom
        wp1 = (epx + offset, epy)
        wp2 = (epx + offset, npy + offset)
        wp3 = (npx,          npy + offset)
    elif corner_idx == 2:  # bottom-left: exit bottom, entry left
        wp1 = (epx,          epy + offset)
        wp2 = (npx - offset, epy + offset)
        wp3 = (npx - offset, npy)
    else:                  # top-left: exit top, entry left
        wp1 = (epx,          epy - offset)
        wp2 = (npx - offset, epy - offset)
        wp3 = (npx - offset, npy)

    return [wp1, wp2, wp3]


def _grid_layout(
    n_vertices: int,
    col_gap: int = CLASS_W + 40,
    row_gap: int = 200,
    margin: int = MARGIN,
) -> list[tuple[float, float]]:
    """Place vertices in a left-to-right grid, wrapping at ceil(sqrt(n)) columns."""
    import math
    if n_vertices == 0:
        return []
    cols = max(1, math.ceil(math.sqrt(n_vertices)))
    return [
        (margin + (i % cols) * col_gap, margin + (i // cols) * row_gap)
        for i in range(n_vertices)
    ]


def _scale_for_min_spacing(
    positions: list[tuple[float, float]],
    min_dist: float,
    margin: int = MARGIN,
) -> list[tuple[float, float]]:
    """Scale and translate positions so the closest pair of node centers is at
    least *min_dist* apart, then shift so the top-left node sits at (margin, margin).

    This preserves the topology of the layout while guaranteeing that boxes of
    width/height up to min_dist will not overlap their nearest neighbour.
    """
    if len(positions) <= 1:
        return [(float(margin), float(margin))] * len(positions)

    closest = min(
        math.hypot(positions[i][0] - positions[j][0], positions[i][1] - positions[j][1])
        for i, j in combinations(range(len(positions)), 2)
    )
    scale = (min_dist / closest) if closest > 0 else 1.0

    min_x = min(x for x, _ in positions)
    min_y = min(y for _, y in positions)
    return [
        ((x - min_x) * scale + margin, (y - min_y) * scale + margin)
        for x, y in positions
    ]


def _remove_overlaps(
    positions: list[tuple[float, float]],
    widths:    list[int],
    heights:   list[int],
    gap:       int = 10,
    max_iter:  int = 100,
) -> list[tuple[float, float]]:
    """Iterative SAT minimum-axis push to separate overlapping boxes.

    *positions* are top-left corners (same convention as mxGeometry x/y).
    Returns translated positions so the minimum top-left corner lands at
    (MARGIN, MARGIN).
    """
    if len(positions) <= 1:
        if positions:
            return [(float(MARGIN), float(MARGIN))]
        return []

    pos = [list(p) for p in positions]  # mutable working copy

    for _ in range(max_iter):
        moved = False
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                cx_i = pos[i][0] + widths[i] / 2
                cy_i = pos[i][1] + heights[i] / 2
                cx_j = pos[j][0] + widths[j] / 2
                cy_j = pos[j][1] + heights[j] / 2
                dx = cx_j - cx_i
                dy = cy_j - cy_i
                half_w = (widths[i] + widths[j]) / 2 + gap
                half_h = (heights[i] + heights[j]) / 2 + gap
                dist = math.hypot(dx, dy)
                if dist < 1e-6:
                    # Coincident: push j in +x, i in -x
                    push = half_w / 2
                    pos[j][0] += push
                    pos[i][0] -= push
                    moved = True
                    continue
                if abs(dx) < half_w and abs(dy) < half_h:
                    push_x = half_w - abs(dx)
                    push_y = half_h - abs(dy)
                    if push_x <= push_y:
                        sign = 1.0 if dx >= 0 else -1.0
                        pos[j][0] += sign * push_x / 2
                        pos[i][0] -= sign * push_x / 2
                    else:
                        sign = 1.0 if dy >= 0 else -1.0
                        pos[j][1] += sign * push_y / 2
                        pos[i][1] -= sign * push_y / 2
                    moved = True
        if not moved:
            break

    # Translate so minimum top-left corner lands at (MARGIN, MARGIN)
    min_x = min(p[0] for p in pos)
    min_y = min(p[1] for p in pos)
    offset_x = MARGIN - min_x
    offset_y = MARGIN - min_y
    return [(p[0] + offset_x, p[1] + offset_y) for p in pos]


_PORT_FRAC_RE = re.compile(r'(exit|entry)(X|Y)=([^;]+)')


def _route_edges_around_boxes(
    edges:         list[tuple[int, int]],
    positions:     list[tuple[float, float]],
    widths:        list[int],
    heights:       list[int],
    port_suffixes: list[str],
    gap:           int = 10,
) -> list[list[tuple[float, float]]]:
    """Return one waypoint list per edge; empty means no waypoint needed.

    Self-loops always return []. For each non-self-loop edge, checks if any
    third box blocks the straight anchor-to-anchor path and adds one waypoint
    (perpendicular detour around the first blocker found).
    """
    result: list[list[tuple[float, float]]] = []
    n = len(positions)

    for e_idx, (src, tgt) in enumerate(edges):
        if src == tgt:
            result.append([])
            continue

        # Parse exit/entry port fractions to compute anchor pixels
        suffix = port_suffixes[e_idx] if e_idx < len(port_suffixes) else ""
        exit_x_frac = exit_y_frac = entry_x_frac = entry_y_frac = 0.5
        for m in _PORT_FRAC_RE.finditer(suffix):
            kind, axis, val = m.group(1), m.group(2), float(m.group(3))
            if kind == "exit" and axis == "X":
                exit_x_frac = val
            elif kind == "exit" and axis == "Y":
                exit_y_frac = val
            elif kind == "entry" and axis == "X":
                entry_x_frac = val
            elif kind == "entry" and axis == "Y":
                entry_y_frac = val

        ax = positions[src][0] + exit_x_frac * widths[src]
        ay = positions[src][1] + exit_y_frac * heights[src]
        bx = positions[tgt][0] + entry_x_frac * widths[tgt]
        by = positions[tgt][1] + entry_y_frac * heights[tgt]

        seg_dx = bx - ax
        seg_dy = by - ay
        seg_len = math.hypot(seg_dx, seg_dy)

        waypoints: list[tuple[float, float]] = []
        for k in range(n):
            if k == src or k == tgt:
                continue
            # Slab test uses no gap (box body only) to avoid false positives
            # when anchor points sit near the edge of an adjacent node.
            kx0 = positions[k][0]
            ky0 = positions[k][1]
            kx1 = positions[k][0] + widths[k]
            ky1 = positions[k][1] + heights[k]

            # Liang-Barsky slab test: does segment (A→B) intersect this AABB?
            # Standard form: p_k*t <= q_k; p<0 → t_min update, p>0 → t_max update.
            t_min, t_max = 0.0, 1.0
            blocked = True
            for p, q in [
                (-seg_dx, ax - kx0),   # left boundary:   ax + t*dx >= kx0
                ( seg_dx, kx1 - ax),   # right boundary:  ax + t*dx <= kx1
                (-seg_dy, ay - ky0),   # bottom boundary: ay + t*dy >= ky0
                ( seg_dy, ky1 - ay),   # top boundary:    ay + t*dy <= ky1
            ]:
                if p == 0:
                    if q < 0:          # parallel and outside this slab
                        blocked = False
                        break
                else:
                    t = q / p
                    if p < 0:
                        t_min = max(t_min, t)
                    else:
                        t_max = min(t_max, t)
            if not blocked or t_min > t_max:
                continue

            # Box k blocks this edge — place one waypoint via perpendicular detour
            ux = seg_dx / seg_len if seg_len > 1e-6 else 1.0
            uy = seg_dy / seg_len if seg_len > 1e-6 else 0.0
            px, py = -uy, ux   # left-normal perpendicular
            mx, my = (ax + bx) / 2, (ay + by) / 2
            kcx = positions[k][0] + widths[k] / 2
            kcy = positions[k][1] + heights[k] / 2
            cross = ux * (kcy - ay) - uy * (kcx - ax)
            side = -1.0 if cross > 0 else 1.0
            half_ext = abs(px) * widths[k] / 2 + abs(py) * heights[k] / 2
            offset = (half_ext + gap) * 2
            waypoints = [(mx + side * px * offset, my + side * py * offset)]
            break  # only first blocker per edge

        result.append(waypoints)

    return result


# ---------------------------------------------------------------------------
# Optimized edge routing helpers
# ---------------------------------------------------------------------------

_SIDES = ("top", "right", "bottom", "left")


def _anchor_point(
    vertex: int,
    side: str,
    t: float,
    positions: list[tuple[float, float]],
    widths: list[int],
    heights: list[int],
) -> tuple[float, float]:
    """Return the pixel coordinate of a point at fraction t along *side* of *vertex*."""
    x0, y0 = positions[vertex]
    w, h = widths[vertex], heights[vertex]
    if side == "top":
        return x0 + t * w, y0
    elif side == "bottom":
        return x0 + t * w, y0 + h
    elif side == "left":
        return x0, y0 + t * h
    else:  # right
        return x0 + w, y0 + t * h


def _segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """Return True if segment p1→p2 properly intersects segment p3→p4."""
    def _cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def _route_path(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    src_idx: int,
    tgt_idx: int,
    positions: list[tuple[float, float]],
    widths: list[int],
    heights: list[int],
    gap: int,
) -> tuple[list[tuple[float, float]], int]:
    """Route from anchor (ax,ay) to anchor (bx,by) around intervening boxes.

    Returns (waypoints, box_crossing_count).  Uses the same slab-test logic as
    _route_edges_around_boxes but counts all crossing boxes (not just the first).
    """
    seg_dx = bx - ax
    seg_dy = by - ay
    seg_len = math.hypot(seg_dx, seg_dy)

    n = len(positions)
    crossings = 0
    first_blocker: int | None = None

    for k in range(n):
        if k == src_idx or k == tgt_idx:
            continue
        kx0 = positions[k][0]
        ky0 = positions[k][1]
        kx1 = kx0 + widths[k]
        ky1 = ky0 + heights[k]

        t_min, t_max = 0.0, 1.0
        blocked = True
        for p, q in [
            (-seg_dx, ax - kx0),
            ( seg_dx, kx1 - ax),
            (-seg_dy, ay - ky0),
            ( seg_dy, ky1 - ay),
        ]:
            if p == 0:
                if q < 0:
                    blocked = False
                    break
            else:
                t = q / p
                if p < 0:
                    t_min = max(t_min, t)
                else:
                    t_max = min(t_max, t)
        if blocked and t_min <= t_max:
            crossings += 1
            if first_blocker is None:
                first_blocker = k

    waypoints: list[tuple[float, float]] = []
    if first_blocker is not None:
        k = first_blocker
        ux = seg_dx / seg_len if seg_len > 1e-6 else 1.0
        uy = seg_dy / seg_len if seg_len > 1e-6 else 0.0
        px, py = -uy, ux
        mx, my = (ax + bx) / 2, (ay + by) / 2
        kcx = positions[k][0] + widths[k] / 2
        kcy = positions[k][1] + heights[k] / 2
        cross = ux * (kcy - ay) - uy * (kcx - ax)
        side = -1.0 if cross > 0 else 1.0
        half_ext = abs(px) * widths[k] / 2 + abs(py) * heights[k] / 2
        offset = (half_ext + gap) * 2
        waypoints = [(mx + side * px * offset, my + side * py * offset)]

    return waypoints, crossings


def _optimize_edge_routing(
    edges: list[tuple[int, int]],
    positions: list[tuple[float, float]],
    node_widths: list[int],
    node_heights: list[int],
    gap: int = 10,
) -> tuple[list[str], list[list[tuple[float, float]]]]:
    """Return (port_suffixes, waypoints) per edge, jointly optimized.

    For each non-self-loop edge, tries all 16 (exit_side × entry_side) combinations.
    Scores each by: box_crossings * 10000 + edge_crossings * 1000 + path_length.
    Runs 3 iterative passes so later edges' choices inform earlier ones' revisions.
    After side selection, anchors are spread within each side to avoid collisions,
    then final waypoints are generated from the spread anchors.
    """
    if not edges or not positions:
        return [""] * len(edges), [[] for _ in edges]

    W_BOX  = 10_000
    W_EDGE = 1_000
    W_LEN  = 1

    n_edges = len(edges)

    # ------------------------------------------------------------------
    # Edge ordering: pseudostate edges first, then by combined box area.
    # ------------------------------------------------------------------
    def _order_key(idx):
        src, tgt = edges[idx]
        if src == 0 or tgt == 0:
            return (0, 0)
        area = node_widths[src] * node_heights[src] + node_widths[tgt] * node_heights[tgt]
        return (1, -area)

    process_order = sorted(range(n_edges), key=_order_key)

    # selected_sides[idx] = (exit_side, entry_side) | None for self-loops
    selected_sides: dict[int, tuple[str, str] | None] = {}
    # paths[idx] = list of (x,y) points along the routed path (for edge-crossing detection)
    paths: dict[int, list[tuple[float, float]] | None] = {i: None for i in range(n_edges)}

    # ------------------------------------------------------------------
    # 3-pass iterative side selection
    # ------------------------------------------------------------------
    for _pass in range(3):
        for idx in process_order:
            src, tgt = edges[idx]
            if src == tgt:
                selected_sides[idx] = None
                paths[idx] = None
                continue

            context_paths: list[list[tuple[float, float]]] = [
                p for i, p in paths.items()
                if i != idx and p is not None
            ]

            best_score = float("inf")
            best_pair: tuple[str, str] = ("bottom", "top")
            best_path: list[tuple[float, float]] = []

            for exit_side in _SIDES:
                for entry_side in _SIDES:
                    # Use center of side for scoring pass
                    ax, ay = _anchor_point(src, exit_side, 0.5, positions, node_widths, node_heights)
                    bx, by = _anchor_point(tgt, entry_side, 0.5, positions, node_widths, node_heights)

                    wps, box_cross = _route_path(
                        ax, ay, bx, by, src, tgt,
                        positions, node_widths, node_heights, gap,
                    )

                    # Build path polyline for edge-crossing detection
                    path_pts: list[tuple[float, float]] = [(ax, ay)] + wps + [(bx, by)]

                    # Count crossings with already-placed edges
                    edge_cross = 0
                    for ctx_path in context_paths:
                        for ci in range(len(ctx_path) - 1):
                            for pi in range(len(path_pts) - 1):
                                if _segments_intersect(
                                    ctx_path[ci], ctx_path[ci + 1],
                                    path_pts[pi], path_pts[pi + 1],
                                ):
                                    edge_cross += 1

                    path_len = sum(
                        math.hypot(path_pts[i + 1][0] - path_pts[i][0],
                                   path_pts[i + 1][1] - path_pts[i][1])
                        for i in range(len(path_pts) - 1)
                    )

                    score = W_BOX * box_cross + W_EDGE * edge_cross + W_LEN * path_len
                    if score < best_score:
                        best_score = score
                        best_pair = (exit_side, entry_side)
                        best_path = path_pts

            selected_sides[idx] = best_pair
            paths[idx] = best_path

    # ------------------------------------------------------------------
    # Anchor spreading pass — same pooled logic as _assign_edge_ports
    # ------------------------------------------------------------------
    def side_coords(side: str, k: int, n: int) -> tuple[float, float]:
        t = (k + 1) / (n + 1)
        if side == "top":
            return t, 0.0
        elif side == "bottom":
            return t, 1.0
        elif side == "left":
            return 0.0, t
        else:  # right
            return 1.0, t

    port_data: list[dict] = [
        {"exitX": 0.5, "exitY": 1.0, "entryX": 0.5, "entryY": 0.0}
        for _ in edges
    ]

    # Pool all connections on a (vertex, side) together
    side_slots: dict[tuple, list[tuple[int, str]]] = {}
    for idx, (src, tgt) in enumerate(edges):
        if src == tgt or selected_sides.get(idx) is None:
            continue
        exit_side, entry_side = selected_sides[idx]  # type: ignore[misc]
        side_slots.setdefault((src, exit_side), []).append((idx, "exit"))
        side_slots.setdefault((tgt, entry_side), []).append((idx, "entry"))

    for (vertex, side), slot_list in side_slots.items():
        n = len(slot_list)
        dim = 0 if side in ("top", "bottom") else 1
        sorted_slots = sorted(
            slot_list,
            key=lambda item: positions[edges[item[0]][1 if item[1] == "exit" else 0]][dim],
        )
        for k, (idx, direction) in enumerate(sorted_slots):
            x, y = side_coords(side, k, n)
            if direction == "exit":
                port_data[idx]["exitX"] = x
                port_data[idx]["exitY"] = y
            else:
                port_data[idx]["entryX"] = x
                port_data[idx]["entryY"] = y

    # ------------------------------------------------------------------
    # Build port suffix strings
    # ------------------------------------------------------------------
    port_suffixes: list[str] = []
    for idx, (src, tgt) in enumerate(edges):
        if src == tgt:
            port_suffixes.append("")
            continue
        pd = port_data[idx]
        suffix = (
            f"exitX={round(pd['exitX'], 4)};exitY={round(pd['exitY'], 4)};"
            f"exitDx=0;exitDy=0;"
            f"entryX={round(pd['entryX'], 4)};entryY={round(pd['entryY'], 4)};"
            f"entryDx=0;entryDy=0;"
        )
        port_suffixes.append(suffix)

    # ------------------------------------------------------------------
    # Final waypoint pass using spread anchors
    # ------------------------------------------------------------------
    edge_waypoints: list[list[tuple[float, float]]] = []
    for idx, (src, tgt) in enumerate(edges):
        if src == tgt:
            edge_waypoints.append([])
            continue
        pd = port_data[idx]
        ax = positions[src][0] + pd["exitX"] * node_widths[src]
        ay = positions[src][1] + pd["exitY"] * node_heights[src]
        bx = positions[tgt][0] + pd["entryX"] * node_widths[tgt]
        by = positions[tgt][1] + pd["entryY"] * node_heights[tgt]
        wps, _ = _route_path(ax, ay, bx, by, src, tgt, positions, node_widths, node_heights, gap)
        edge_waypoints.append(wps)

    return port_suffixes, edge_waypoints


def _layout_for_canvas(
    n_vertices: int,
    edges: list[tuple[int, int]],
    min_dist: float,
    margin: int = MARGIN,
    method: str = "sugiyama",
    weights: list[float] | None = None,
) -> list[tuple[float, float]]:
    """Run a graph layout and return (x, y) per vertex with guaranteed minimum spacing.

    Replaces fit_into with _scale_for_min_spacing so that the closest pair of
    node centres is at least *min_dist* pixels apart regardless of canvas size.
    Canvas dimensions are derived from the resulting positions by the caller.

    method:
      "sugiyama"     — layered hierarchical (igraph layout_sugiyama)
      "kamada_kawai" — force-directed spring embedder (igraph layout_kamada_kawai)
    """
    if n_vertices == 0:
        return []
    if n_vertices == 1:
        return [(float(margin), float(margin))]

    g = ig.Graph(n=n_vertices, edges=edges, directed=True)
    if method == "kamada_kawai":
        raw = g.layout_kamada_kawai(weights=weights)
    else:
        raw = g.layout_sugiyama()
    # Sugiyama may inflate vertex count with dummy nodes — slice back to original
    coords = [(raw.coords[i][0], raw.coords[i][1]) for i in range(n_vertices)]
    return _scale_for_min_spacing(coords, min_dist, margin)


def _html_escape_type(t: str) -> str:
    """Escape < and > in type names for Draw.io HTML cell values."""
    return t.replace("<", "&lt;").replace(">", "&gt;")


# Approximate px per character for label width estimation (11px default font)
_LABEL_CHAR_PX = 6.0
_LABEL_PAD_PX = 16  # spacingLeft + spacingRight + symbol


def _estimate_class_width(cls) -> int:
    """Estimate minimum width for a class box based on longest label text."""
    lines: list[str] = []
    # Class header
    lines.append(f"<<{cls.stereotype}>> {cls.name}")
    # Attribute labels (strip HTML tags for width estimation)
    for a in cls.attributes:
        label = f"- {a.name}: {a.type}"
        tags: list[str] = []
        if a.identifier:
            tags.extend(f"I{i}" for i in sorted(a.identifier))
        if a.referential:
            tags.append(a.referential)
        if tags:
            label += f" {{{', '.join(tags)}}}"
        lines.append(label)
    # Method labels
    for m in cls.methods:
        param_sig = ", ".join(f"{p.name}: {p.type}" for p in m.params)
        ret = f": {m.return_type}" if m.return_type else ""
        lines.append(f"- {m.name}({param_sig}){ret}")
    max_chars = max((len(l) for l in lines), default=10)
    return max(CLASS_W, int(max_chars * _LABEL_CHAR_PX + _LABEL_PAD_PX))


def _attr_label(vis: str, scope: str, name: str, type_: str,
                identifier: list[int] | None = None,
                referential: str | None = None) -> str:
    """Format a UML attribute label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    text = f"{name}: {_html_escape_type(type_)}"
    tags: list[str] = []
    if identifier:
        tags.extend(f"I{i}" for i in sorted(identifier))
    if referential:
        tags.append(referential)
    if tags:
        text += f" {{{', '.join(tags)}}}"
    if scope == "class":
        text = f"<u>{text}</u>"
    return f"{sym} {text}"


def _method_label(
    vis: str,
    scope: str,
    name: str,
    params: list,
    return_type: str | None,
) -> str:
    """Format a UML method label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    param_sig = ", ".join(f"{p.name}: {_html_escape_type(p.type)}" for p in params)
    ret = f": {_html_escape_type(return_type)}" if return_type else ""
    sig = f"{name}({param_sig}){ret}"
    if scope == "class":
        sig = f"<u>{sig}</u>"
    return f"{sym} {sig}"


def _extract_drawio_ids(xml_path: Path) -> frozenset[str] | None:
    """Parse an existing .drawio file and return the set of IDs containing ':'.

    Returns None if the file does not exist or is malformed XML.
    """
    if not xml_path.exists():
        return None
    try:
        tree = etree.parse(str(xml_path))
        ids = frozenset(
            el.get("id", "")
            for el in tree.iter("mxCell")
            if ":" in el.get("id", "")
        )
        return ids
    except etree.XMLSyntaxError:
        return None


def _compute_expected_class_ids(domain: str, cd: ClassDiagramFile) -> frozenset[str]:
    """Return frozenset of all cell IDs that _build_class_diagram_xml would generate."""
    ids: set[str] = set()
    for cls in cd.classes:
        cid = class_id(domain, cls.name)
        ids.add(cid)
        ids.add(f"{cid}:attrs")
        ids.add(separator_id(domain, cls.name))
        ids.add(f"{cid}:methods")
    for assoc in cd.associations:
        ids.add(association_id(domain, assoc.name))
        for suffix in ("src_mult", "src_phrase", "tgt_mult", "tgt_phrase"):
            ids.add(association_label_id(domain, assoc.name, suffix))
    return frozenset(ids)


def _structure_matches_class(
    domain_path: Path, domain: str, cd: ClassDiagramFile
) -> bool:
    """Return True if existing class-diagram.drawio has the same element set."""
    drawio_path = domain_path.parent / "diagrams" / f"{domain}-class-diagram.drawio"
    existing = _extract_drawio_ids(drawio_path)
    if existing is None:
        return False
    expected = _compute_expected_class_ids(domain, cd)
    return existing == expected


def _compute_expected_state_ids(
    domain: str, sd: StateDiagramFile
) -> frozenset[str]:
    """Return frozenset of all cell IDs that _build_state_diagram_xml would generate."""
    ids: set[str] = set()
    # initial pseudostate
    init_id = f"{domain.lower()}:state:{sd.class_name}:__initial__"
    ids.add(init_id)
    init_trans_id = f"{domain.lower()}:trans:{sd.class_name}:__initial__:__init__:0"
    ids.add(init_trans_id)
    for st in sd.states:
        ids.add(state_id(domain, sd.class_name, st.name))
    for idx, trans in enumerate(sd.transitions):
        ids.add(transition_id(domain, sd.class_name, trans.from_state, trans.event, idx))
    return frozenset(ids)


def _structure_matches_state(
    domain_path: Path, domain: str, class_name: str, sd: StateDiagramFile
) -> bool:
    """Return True if existing state diagram .drawio has the same element set."""
    drawio_path = domain_path.parent / "diagrams" / f"{domain}-{class_name}.drawio"
    existing = _extract_drawio_ids(drawio_path)
    if existing is None:
        return False
    expected = _compute_expected_state_ids(domain, sd)
    return existing == expected


def _build_class_diagram_xml(
    domain: str,
    cd: ClassDiagramFile,
    use_layout: bool = True,
    layout: str = "kamada_kawai",
    include_edges: bool = True,
    route_edges: bool = True,
) -> bytes:
    """Build the full mxfile XML for a class diagram. Returns UTF-8 bytes."""
    classes = cd.classes
    n = len(classes)

    name_to_idx = {cls.name: i for i, cls in enumerate(classes)}

    # Build generalization map first so all subtype→supertype edges enter the layout.
    # cd.associations only lists ONE subtype per generalization relationship; the rest
    # are declared via cls.specializes/cls.partitions and would be invisible to the
    # layout engine if we relied solely on cd.associations.
    gen_map: dict[str, dict] = {}
    for cls in classes:
        if cls.partitions:
            for p in cls.partitions:
                gen_map[p.name] = {"supertype": cls.name, "subtypes": list(p.subtypes)}

    # Build edges from associations (index-based).
    # layout_edges excludes self-loops (igraph Sugiyama doesn't need them for placement).
    # all_edges includes self-loops so _assign_edge_ports can assign corner anchors.
    # Generalization associations are skipped here — all their subtype edges are added
    # below from gen_map so every subtype participates in the layout.
    layout_edges: list[tuple[int, int]] = []
    all_edges: list[tuple[int, int]] = []
    assoc_edge_idx: list[int | None] = []
    for assoc in cd.associations:
        if assoc.name in gen_map:
            assoc_edge_idx.append(None)
            continue
        src = name_to_idx.get(assoc.point_1)
        tgt = name_to_idx.get(assoc.point_2)
        if src is not None and tgt is not None:
            assoc_edge_idx.append(len(all_edges))
            all_edges.append((src, tgt))
            if src != tgt:
                layout_edges.append((src, tgt))
        else:
            assoc_edge_idx.append(None)

    # Add every subtype→supertype edge from gen_map into both edge lists
    for info in gen_map.values():
        sup_idx = name_to_idx.get(info["supertype"])
        if sup_idx is None:
            continue
        for subtype in info["subtypes"]:
            sub_idx = name_to_idx.get(subtype)
            if sub_idx is not None:
                all_edges.append((sub_idx, sup_idx))
                layout_edges.append((sub_idx, sup_idx))

    # Per-node dimensions: all classes share CLASS_W; height varies
    node_widths:  list[int] = [_estimate_class_width(cls) for cls in cd.classes]
    node_heights: list[int] = [_class_height(len(cls.attributes), len(cls.methods)) for cls in classes]

    H_GAP = 40
    avg_h = sum(node_heights) / max(len(node_heights), 1)
    avg_w = sum(node_widths) / max(len(node_widths), 1)
    min_dist = math.hypot(avg_w + H_GAP, avg_h + H_GAP)

    if use_layout:
        positions = _layout_for_canvas(n, layout_edges, min_dist, method=layout)
    else:
        positions = _grid_layout(n)
    positions = _remove_overlaps(positions, node_widths, node_heights, gap=H_GAP)

    max_x = max((positions[i][0] + node_widths[i]  for i in range(n)), default=0)
    max_y = max((positions[i][1] + node_heights[i] for i in range(n)), default=0)
    canvas_w = int(max_x) + MARGIN
    canvas_h = int(max_y) + MARGIN

    if route_edges:
        port_suffixes, edge_waypoints = _optimize_edge_routing(all_edges, positions, node_widths, node_heights, gap=H_GAP)
    else:
        port_suffixes = [""] * len(all_edges)
        edge_waypoints = [[] for _ in all_edges]

    # Derive class_heights from node_heights (still needed for self-loop waypoints)
    class_heights = {i: node_heights[i] for i in range(n)}

    # Build XML
    mxfile = etree.Element("mxfile", compressed="false", version="24.0.0")
    diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
    etree.SubElement(
        diagram, "mxGraphModel",
        dx="1034", dy="546", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth=str(canvas_w), pageHeight=str(canvas_h),
        math="0", shadow="0", background="#FFFFFF",
    )
    model_el = diagram[0]
    root_el = etree.SubElement(model_el, "root")
    etree.SubElement(root_el, "mxCell", id="0")
    etree.SubElement(root_el, "mxCell", id="1", parent="0")

    for i, cls in enumerate(classes):
        x = int(positions[i][0])
        y = int(positions[i][1])
        w = node_widths[i]
        height = _class_height(len(cls.attributes), len(cls.methods))
        cid = class_id(domain, cls.name)

        # Swimlane cell — active classes get a distinct green fill
        cls_style = STYLE_CLASS_ACTIVE if cls.stereotype == "active" else STYLE_CLASS
        cls_cell = etree.SubElement(
            root_el, "mxCell",
            id=cid, value=f"<<{cls.stereotype}>>\n{cls.name}",
            style=cls_style, vertex="1", parent="1",
        )
        etree.SubElement(
            cls_cell, "mxGeometry",
            x=str(x), y=str(y), width=str(w), height=str(height),
            attrib={"as": "geometry"},
        )

        # Attributes cell
        attrs_h = max(len(cls.attributes), 1) * ROW_H
        attr_text = "<br>".join(
            _attr_label(a.visibility, a.scope, a.name, a.type, a.identifier, a.referential)
            for a in cls.attributes
        ) if cls.attributes else ""
        attrs_cell = etree.SubElement(
            root_el, "mxCell",
            id=f"{cid}:attrs", value=attr_text,
            style=STYLE_ATTRIBUTE, vertex="1", parent=cid,
        )
        etree.SubElement(
            attrs_cell, "mxGeometry",
            y=str(HEADER_H), width=str(w), height=str(attrs_h),
            attrib={"as": "geometry"},
        )

        # Separator
        sep_y = HEADER_H + attrs_h
        sep_cell = etree.SubElement(
            root_el, "mxCell",
            id=separator_id(domain, cls.name), value="",
            style=STYLE_SEPARATOR, vertex="1", parent=cid,
        )
        etree.SubElement(
            sep_cell, "mxGeometry",
            y=str(sep_y), width=str(w), height=str(SEP_H),
            attrib={"as": "geometry"},
        )

        # Methods cell
        methods_h = max(len(cls.methods), 1) * ROW_H
        method_text = "<br>".join(
            _method_label(m.visibility, m.scope, m.name, m.params, m.return_type)
            for m in cls.methods
        ) if cls.methods else ""
        methods_cell = etree.SubElement(
            root_el, "mxCell",
            id=f"{cid}:methods", value=method_text,
            style=STYLE_ATTRIBUTE, vertex="1", parent=cid,
        )
        etree.SubElement(
            methods_cell, "mxGeometry",
            y=str(sep_y + SEP_H), width=str(w), height=str(methods_h),
            attrib={"as": "geometry"},
        )

    if not include_edges:
        etree.indent(mxfile, space="  ")
        return etree.tostring(mxfile, encoding="unicode", xml_declaration=False).encode("utf-8")

    # Association edges (skip generalizations — rendered separately below)
    self_loop_count: dict[int, int] = {}
    for i, assoc in enumerate(cd.associations):
        if assoc.name in gen_map:
            continue

        aid = association_id(domain, assoc.name)
        src_cid = class_id(domain, assoc.point_1)
        tgt_cid = class_id(domain, assoc.point_2)
        src_v = name_to_idx.get(assoc.point_1)
        tgt_v = name_to_idx.get(assoc.point_2)

        waypoints: list[tuple[float, float]] = []
        if src_v is not None and src_v == tgt_v:
            # Self-loop: pick the least-populated corner and compute 3-point exterior path
            loop_idx = self_loop_count.get(src_v, 0)
            self_loop_count[src_v] = loop_idx + 1
            corner = _self_loop_corner(src_v, loop_idx, all_edges, positions)
            ex, ey, nx, ny = _SELF_LOOP_CORNERS[corner]
            port_suffix = (
                f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
                f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
            )
            bx, by = positions[src_v]
            waypoints = _self_loop_waypoints(corner, bx, by, node_widths[src_v], class_heights[src_v])
        else:
            edge_idx = assoc_edge_idx[i]
            port_suffix = port_suffixes[edge_idx] if edge_idx is not None else ""

        assoc_cell = etree.SubElement(
            root_el, "mxCell",
            id=aid, value=assoc.name,
            style=STYLE_ASSOCIATION + port_suffix, edge="1",
            source=src_cid, target=tgt_cid, parent="1",
        )
        geo = etree.SubElement(
            assoc_cell, "mxGeometry",
            attrib={"relative": "1", "as": "geometry"},
        )
        route_wps = edge_waypoints[assoc_edge_idx[i]] if assoc_edge_idx[i] is not None else []
        all_wps = waypoints if waypoints else route_wps
        if all_wps:
            arr = etree.SubElement(geo, "Array", attrib={"as": "points"})
            for wx, wy in all_wps:
                etree.SubElement(arr, "mxPoint", x=str(int(wx)), y=str(int(wy)))

        # Multiplicity + verb phrase labels: split into 4 separate cells.
        # Each label gets its own alignment — mult and phrase sit on opposite sides
        # of a vertical edge, so they need opposite left/right alignment.
        mult_src_y,   phrase_src_y   = _label_perp_y(port_suffix, "exit")
        mult_tgt_y,   phrase_tgt_y   = _label_perp_y(port_suffix, "entry")
        mult_src_style   = STYLE_ASSOC_LABEL + f"align={_label_align(port_suffix, 'exit',   mult_src_y)};verticalAlign={_label_valign(port_suffix, 'exit',   mult_src_y)};"
        phrase_src_style = STYLE_ASSOC_LABEL + f"align={_label_align(port_suffix, 'exit',   phrase_src_y)};verticalAlign={_label_valign(port_suffix, 'exit',   phrase_src_y)};"
        mult_tgt_style   = STYLE_ASSOC_LABEL + f"align={_label_align(port_suffix, 'entry',  mult_tgt_y)};verticalAlign={_label_valign(port_suffix, 'entry',  mult_tgt_y)};"
        phrase_tgt_style = STYLE_ASSOC_LABEL + f"align={_label_align(port_suffix, 'entry',  phrase_tgt_y)};verticalAlign={_label_valign(port_suffix, 'entry',  phrase_tgt_y)};"

        def _emit_label(cell_id, value, style, x, perp_y):
            cell = etree.SubElement(root_el, "mxCell",
                id=cell_id, value=value, style=style,
                vertex="1", connectable="0", parent=aid)
            etree.SubElement(cell, "mxGeometry",
                x=str(x), y=str(perp_y),
                attrib={"relative": "1", "as": "geometry"})

        _emit_label(association_label_id(domain, assoc.name, "src_mult"),
                    assoc.mult_2_to_1,
                    mult_src_style,   -1.0, mult_src_y)
        _emit_label(association_label_id(domain, assoc.name, "src_phrase"),
                    _wrap_squarest(assoc.phrase_2_to_1),
                    phrase_src_style, -1.0, phrase_src_y)
        _emit_label(association_label_id(domain, assoc.name, "tgt_mult"),
                    assoc.mult_1_to_2,
                    mult_tgt_style,    1.0, mult_tgt_y)
        _emit_label(association_label_id(domain, assoc.name, "tgt_phrase"),
                    _wrap_squarest(assoc.phrase_1_to_2),
                    phrase_tgt_style,  1.0, phrase_tgt_y)

    # Generalization edges — one edge per subtype, hollow-triangle pointing at supertype
    for rname, info in gen_map.items():
        supertype = info["supertype"]
        subtypes = info["subtypes"]
        sup_idx = name_to_idx.get(supertype)
        if sup_idx is None:
            continue

        sup_x, sup_y = positions[sup_idx]

        # Compute average subtype position to determine which side of supertype they face
        sub_positions = [positions[name_to_idx[s]] for s in subtypes if name_to_idx.get(s) is not None]
        if not sub_positions:
            continue
        avg_sub_x = sum(p[0] for p in sub_positions) / len(sub_positions)
        avg_sub_y = sum(p[1] for p in sub_positions) / len(sub_positions)
        dx = avg_sub_x - sup_x
        dy = avg_sub_y - sup_y

        # Determine entry port on supertype
        if abs(dy) >= abs(dx):
            if dy >= 0:
                entry_port = "entryX=0.5;entryY=1.0;entryDx=0;entryDy=0;"  # subtypes below → enter bottom
            else:
                entry_port = "entryX=0.5;entryY=0.0;entryDx=0;entryDy=0;"  # subtypes above → enter top
        else:
            if dx >= 0:
                entry_port = "entryX=1.0;entryY=0.5;entryDx=0;entryDy=0;"  # subtypes right → enter right
            else:
                entry_port = "entryX=0.0;entryY=0.5;entryDx=0;entryDy=0;"  # subtypes left → enter left

        for k, subtype in enumerate(subtypes):
            sub_idx = name_to_idx.get(subtype)
            if sub_idx is None:
                continue
            sub_x, sub_y = positions[sub_idx]

            # Exit port on subtype: toward supertype
            sdx = sup_x - sub_x
            sdy = sup_y - sub_y
            if abs(sdy) >= abs(sdx):
                if sdy >= 0:
                    exit_port = "exitX=0.5;exitY=1.0;exitDx=0;exitDy=0;"
                else:
                    exit_port = "exitX=0.5;exitY=0.0;exitDx=0;exitDy=0;"
            else:
                if sdx >= 0:
                    exit_port = "exitX=1.0;exitY=0.5;exitDx=0;exitDy=0;"
                else:
                    exit_port = "exitX=0.0;exitY=0.5;exitDx=0;exitDy=0;"

            # First subtype edge carries the R-name label; rest are empty
            edge_value = rname if k == 0 else ""
            edge_id = association_id(domain, rname) + f":{subtype}"

            gen_cell = etree.SubElement(
                root_el, "mxCell",
                id=edge_id, value=edge_value,
                style=STYLE_GENERALIZATION + exit_port + entry_port, edge="1",
                source=class_id(domain, subtype),
                target=class_id(domain, supertype),
                parent="1",
            )
            etree.SubElement(gen_cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    etree.indent(mxfile, space="  ")
    return etree.tostring(mxfile, encoding="unicode", xml_declaration=False).encode("utf-8")


def _build_state_diagram_xml(domain: str, sd: StateDiagramFile) -> bytes:
    """Build the full mxfile XML for a state diagram. Returns UTF-8 bytes."""
    class_name = sd.class_name
    state_names = [s.name for s in sd.states]

    # Vertices: index 0 = initial pseudostate, indices 1..N = states
    # Find index of initial_state in state_names
    initial_state_name = sd.initial_state
    try:
        initial_state_vertex_idx = 1 + state_names.index(initial_state_name)
    except ValueError:
        initial_state_vertex_idx = 1  # fallback — validator should catch this

    n_vertices = 1 + len(state_names)  # 0=initial_pseudo, 1..N=states

    # Build edges
    state_name_to_idx = {name: 1 + i for i, name in enumerate(state_names)}
    edges: list[tuple[int, int]] = []
    # Initial -> initial_state edge
    edges.append((0, initial_state_vertex_idx))
    # Transition edges — track which transitions map to which edge index
    trans_edge_idx: list[int | None] = []
    for trans in sd.transitions:
        src = state_name_to_idx.get(trans.from_state)
        tgt = state_name_to_idx.get(trans.to)
        if src is not None and tgt is not None:
            trans_edge_idx.append(len(edges))
            edges.append((src, tgt))
        else:
            trans_edge_idx.append(None)

    # Per-node dimensions: vertex 0 = initial pseudostate, vertices 1..N = states
    node_widths:  list[int] = [INIT_SIZE] + [_state_width(st.name, st.entry_action) for st in sd.states]
    node_heights: list[int] = [INIT_SIZE] + [_state_height(st.entry_action)          for st in sd.states]

    # Compact initial scaling using average box diagonal (not max)
    S_GAP = 100
    avg_w = sum(node_widths)  / len(node_widths)
    avg_h = sum(node_heights) / len(node_heights)
    min_dist = math.hypot(avg_w + S_GAP, avg_h + S_GAP)

    # Per-edge weights: ideal center-to-center distance for each endpoint pair.
    # Larger boxes get larger weights → Kamada-Kawai places them further apart.
    edge_weights = [
        math.hypot(
            (node_widths[src]  + node_widths[tgt])  / 2 + S_GAP,
            (node_heights[src] + node_heights[tgt]) / 2 + S_GAP,
        )
        for src, tgt in edges
    ]

    positions = _layout_for_canvas(n_vertices, edges, min_dist, method="kamada_kawai", weights=edge_weights)
    positions = _remove_overlaps(positions, node_widths, node_heights, gap=S_GAP)
    port_suffixes, edge_waypoints = _optimize_edge_routing(edges, positions, node_widths, node_heights, gap=S_GAP)

    # Canvas from actual extents
    max_x = max(positions[i][0] + node_widths[i]  for i in range(n_vertices))
    max_y = max(positions[i][1] + node_heights[i] for i in range(n_vertices))
    canvas_w = int(max_x) + MARGIN
    canvas_h = int(max_y) + MARGIN

    # Build XML
    mxfile = etree.Element("mxfile", compressed="false", version="24.0.0")
    diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
    etree.SubElement(
        diagram, "mxGraphModel",
        dx="1034", dy="546", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth=str(canvas_w), pageHeight=str(canvas_h),
        math="0", shadow="0", background="#FFFFFF",
    )
    model_el = diagram[0]
    root_el = etree.SubElement(model_el, "root")
    etree.SubElement(root_el, "mxCell", id="0")
    etree.SubElement(root_el, "mxCell", id="1", parent="0")

    # Initial pseudostate
    init_cid = f"{domain.lower()}:state:{class_name}:__initial__"
    x0 = int(positions[0][0])
    y0 = int(positions[0][1])
    init_cell = etree.SubElement(
        root_el, "mxCell",
        id=init_cid, value="",
        style=STYLE_INITIAL_PSEUDO, vertex="1", parent="1",
    )
    etree.SubElement(
        init_cell, "mxGeometry",
        x=str(x0), y=str(y0), width=str(INIT_SIZE), height=str(INIT_SIZE),
        attrib={"as": "geometry"},
    )

    # Pre-compute per-state dimensions for rendering and self-loop waypoints
    # vertex index 1+i maps to sd.states[i]; derived from node_* lists
    state_heights = {1 + i: node_heights[1 + i] for i in range(len(sd.states))}
    state_widths  = {1 + i: node_widths[1 + i]  for i in range(len(sd.states))}

    # State nodes
    for i, st in enumerate(sd.states):
        vertex_idx = 1 + i
        x = int(positions[vertex_idx][0])
        y = int(positions[vertex_idx][1])
        sid = state_id(domain, class_name, st.name)
        value = st.name
        if st.entry_action:
            action_html = html.escape(st.entry_action).replace('\n', '<br>')
            value = f"{st.name}<br>──────────────────<br><i>entry /</i><br>{action_html}"
        state_cell = etree.SubElement(
            root_el, "mxCell",
            id=sid, value=value,
            style=STYLE_STATE, vertex="1", parent="1",
        )
        etree.SubElement(
            state_cell, "mxGeometry",
            x=str(x), y=str(y), width=str(state_widths[vertex_idx]), height=str(state_heights[vertex_idx]),
            attrib={"as": "geometry"},
        )

    # Initial -> initial_state transition (no label)
    init_trans_cid = f"{domain.lower()}:trans:{class_name}:__initial__:__init__:0"
    init_target_sid = state_id(domain, class_name, initial_state_name)
    init_trans = etree.SubElement(
        root_el, "mxCell",
        id=init_trans_cid, value="",
        style=STYLE_TRANSITION + port_suffixes[0], edge="1",
        source=init_cid, target=init_target_sid, parent="1",
    )
    geo = etree.SubElement(init_trans, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
    if edge_waypoints[0]:
        arr = etree.SubElement(geo, "Array", attrib={"as": "points"})
        for wx, wy in edge_waypoints[0]:
            etree.SubElement(arr, "mxPoint", x=str(int(wx)), y=str(int(wy)))

    # Transition edges
    # Build event lookup map for param sigs
    event_map = {e.name: e for e in sd.events} if sd.events else {}
    trans_self_loop_count: dict[int, int] = {}

    for idx, trans in enumerate(sd.transitions):
        tid = transition_id(domain, class_name, trans.from_state, trans.event, idx)
        src_sid = state_id(domain, class_name, trans.from_state)
        tgt_sid = state_id(domain, class_name, trans.to)

        # Build label: {trans_id}<br>{event}({params})[<br>[{guard}]]
        event_def = event_map.get(trans.event)
        if event_def and event_def.params:
            param_sig = ", ".join(f"{p.name}: {p.type}" for p in event_def.params)
            event_line = f"{trans.event}({param_sig})"
        else:
            event_line = f"{trans.event}()"
        label = f"{tid}<br>{event_line}"
        if trans.guard is not None:
            label += f"<br>[{trans.guard}]"

        edge_idx = trans_edge_idx[idx]
        src_v = state_name_to_idx.get(trans.from_state)
        tgt_v = state_name_to_idx.get(trans.to)

        trans_waypoints: list[tuple[float, float]] = []
        route_wps: list[tuple[float, float]] = []
        if src_v is not None and src_v == tgt_v:
            # Self-loop: density-aware corner + 3-point exterior path
            loop_idx = trans_self_loop_count.get(src_v, 0)
            trans_self_loop_count[src_v] = loop_idx + 1
            corner = _self_loop_corner(src_v, loop_idx, edges, positions)
            ex, ey, nx, ny = _SELF_LOOP_CORNERS[corner]
            port_suffix = (
                f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
                f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
            )
            bx, by = positions[src_v]
            trans_waypoints = _self_loop_waypoints(corner, bx, by, state_widths[src_v], state_heights[src_v])
        else:
            port_suffix = port_suffixes[edge_idx] if edge_idx is not None else ""
            route_wps = edge_waypoints[edge_idx] if edge_idx is not None else []

        trans_cell = etree.SubElement(
            root_el, "mxCell",
            id=tid, value=label,
            style=STYLE_TRANSITION + port_suffix, edge="1",
            source=src_sid, target=tgt_sid, parent="1",
        )
        geo = etree.SubElement(
            trans_cell, "mxGeometry",
            x=LABEL_OFFSET_X, y=LABEL_OFFSET_Y,
            attrib={"relative": "1", "as": "geometry"},
        )
        all_wps = trans_waypoints if trans_waypoints else route_wps
        if all_wps:
            arr = etree.SubElement(geo, "Array", attrib={"as": "points"})
            for wx, wy in all_wps:
                etree.SubElement(arr, "mxPoint", x=str(int(wx)), y=str(int(wy)))

    etree.indent(mxfile, space="  ")
    return etree.tostring(mxfile, encoding="unicode", xml_declaration=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_to_drawio_class(domain: str, *, force: bool = False) -> list[dict]:
    """Render class-diagram.yaml to class-diagram.drawio.

    Returns a list of per-file result dicts with 'file' and 'status' keys.
    Errors are returned as issue dicts with 'severity': 'error'.
    """
    domain_path = MODEL_ROOT / domain
    if not domain_path.exists():
        return [_make_issue(
            f"Domain path not found: {domain_path}",
            location=f"domain={domain}",
            severity="error",
        )]

    yaml_path = domain_path / "class-diagram.yaml"
    if not yaml_path.exists():
        return [_make_issue(
            f"class-diagram.yaml not found: {yaml_path}",
            location=f"domain={domain}",
            severity="error",
        )]

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        cd = ClassDiagramFile.model_validate(raw)
    except Exception as exc:
        return [_make_issue(
            f"Failed to load class-diagram.yaml: {exc}",
            location=str(yaml_path),
            severity="error",
        )]

    diagrams_dir = domain_path.parent / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    drawio_path = diagrams_dir / f"{domain}-class-diagram.drawio"

    if not force and _structure_matches_class(domain_path, domain, cd):
        return [{"file": str(drawio_path), "status": "skipped"}]

    xml_bytes = _build_class_diagram_xml(domain, cd)
    drawio_path.write_bytes(xml_bytes)
    return [{"file": str(drawio_path), "status": "written"}]


def render_to_drawio_state(domain: str, class_name: str, *, force: bool = False) -> list[dict]:
    """Render state-diagrams/<class_name>.yaml to state-diagrams/<class_name>.drawio.

    Returns a list of per-file result dicts with 'file' and 'status' keys.
    Errors are returned as issue dicts with 'severity': 'error'.
    """
    domain_path = MODEL_ROOT / domain
    if not domain_path.exists():
        return [_make_issue(
            f"Domain path not found: {domain_path}",
            location=f"domain={domain}",
            severity="error",
        )]

    yaml_path = domain_path / "state-diagrams" / f"{class_name}.yaml"
    if not yaml_path.exists():
        return [_make_issue(
            f"State diagram YAML not found: {yaml_path}",
            location=f"domain={domain}, class={class_name}",
            severity="error",
        )]

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        sd = StateDiagramFile.model_validate(raw)
    except Exception as exc:
        return [_make_issue(
            f"Failed to load {class_name}.yaml: {exc}",
            location=str(yaml_path),
            severity="error",
        )]

    drawio_dir = domain_path.parent / "diagrams"
    drawio_dir.mkdir(parents=True, exist_ok=True)
    drawio_path = drawio_dir / f"{domain}-{class_name}.drawio"

    if not force and _structure_matches_state(domain_path, domain, class_name, sd):
        return [{"file": str(drawio_path), "status": "skipped"}]

    xml_bytes = _build_state_diagram_xml(domain, sd)
    drawio_path.write_bytes(xml_bytes)
    return [{"file": str(drawio_path), "status": "written"}]


def render_to_drawio(domain: str, *, force: bool = False) -> list[dict]:
    """Render all diagrams for a domain: class diagram + all active-class state diagrams.

    Returns combined list of per-file result dicts (class diagram first,
    then state diagrams in class list order).
    Errors are returned as issue dicts with 'severity': 'error'.
    """
    results: list[dict] = []

    # Render class diagram
    class_results = render_to_drawio_class(domain, force=force)
    results.extend(class_results)

    # Check if any errors were returned from the class diagram render
    has_error = any(r.get("severity") == "error" for r in class_results)
    if has_error:
        return results

    # Load class diagram to find active classes
    domain_path = MODEL_ROOT / domain
    yaml_path = domain_path / "class-diagram.yaml"
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        cd = ClassDiagramFile.model_validate(raw)
    except Exception as exc:
        results.append(_make_issue(
            f"Failed to reload class-diagram.yaml for active class discovery: {exc}",
            location=str(yaml_path),
            severity="error",
        ))
        return results

    # Render state diagram for each active class
    for cls in cd.classes:
        if cls.stereotype == "active":
            state_results = render_to_drawio_state(domain, cls.name, force=force)
            results.extend(state_results)

    return results


# ---------------------------------------------------------------------------
# Private helpers for validate_drawio and sync_from_drawio
# ---------------------------------------------------------------------------


def _to_xml_bytes(xml: bytes | str) -> bytes:
    """Normalize xml input to bytes for defusedxml parsing."""
    if isinstance(xml, str):
        return xml.encode("utf-8")
    return xml


def _valid_styles() -> frozenset[str]:
    """Return the set of valid canonical style strings from BIJECTION_TABLE."""
    return frozenset(BIJECTION_TABLE.values())


_PORT_RE = re.compile(r'(exit|entry)[XYDxy]+=[^;]*;?')
_PORT_VAL_RE = re.compile(r'(exit|entry)([XY])=([0-9.]+)')


def _strip_port_tokens(style: str) -> str:
    return _PORT_RE.sub('', style)


def _label_align(port_suffix: str, end: str, perp_y: int = 0) -> str:
    """Return 'left', 'right', or 'center' alignment for a label near a given edge end.

    For horizontal exits (left/right sides), text must extend AWAY from the box.
    For vertical exits (top/bottom), text extends away from the edge line based on
    which side (left/right) the label sits on, determined by the sign of perp_y.
    end: 'exit' for the source label, 'entry' for the target label.
    perp_y: perpendicular offset for this specific label (from _label_perp_y).
    """
    if not port_suffix:
        return "center"
    vals: dict[str, float] = {}
    for m in _PORT_VAL_RE.finditer(port_suffix):
        direction, axis, value = m.group(1), m.group(2), float(m.group(3))
        if direction == end:
            vals[axis] = value
    px = vals.get("X")
    if px is None:
        return "center"
    if px < 0.01:
        return "right"   # left-side exit: text extends leftward (right-align)
    if px > 0.99:
        return "left"    # right-side exit: text extends rightward (left-align)
    # Vertical exit/entry: determine if edge goes upward at this endpoint.
    # Draw.io perpendicular y is edge-direction-relative, so the sign meaning
    # flips for upward edges: y > 0 = canvas LEFT (not RIGHT).
    py = vals.get("Y", 0.5)
    edge_upward = (py < 0.1 and end == "exit") or (py > 0.9 and end == "entry")
    effective_perp = -perp_y if edge_upward else perp_y
    if effective_perp > 0:
        return "left"
    if effective_perp < 0:
        return "right"
    return "center"


def _wrap_squarest(text: str) -> str:
    """Wrap text at a single word boundary closest to PHRASE_TARGET_RATIO (width:height)."""
    words = text.split()
    n = len(words)
    if n <= 1:
        return text
    CHAR_W, LINE_H = 7, 16

    def _score(lines):
        w = max(len(l) for l in lines) * CHAR_W
        h = len(lines) * LINE_H
        return abs(w / max(h, 1) - PHRASE_TARGET_RATIO)

    best, best_score = text, _score([text])
    for i in range(1, n):
        candidate = " ".join(words[:i]) + "\n" + " ".join(words[i:])
        s = _score(candidate.split("\n"))
        if s < best_score:
            best_score, best = s, candidate
    return best


def _label_perp_y(port_suffix: str, end: str) -> tuple[int, int]:
    """Return signed perpendicular y offsets for (multiplicity, phrase) labels.

    Puts mult on visual-left (vertical edge) or visual-top (horizontal edge).
    end: 'exit' for source labels, 'entry' for target labels.
    """
    if not port_suffix:
        return (-LABEL_PERP_OFFSET, +LABEL_PERP_OFFSET)
    vals: dict[str, float] = {}
    for m in _PORT_VAL_RE.finditer(port_suffix):
        if m.group(1) == end:
            vals[m.group(2)] = float(m.group(3))
    px, py = vals.get("X", 0.5), vals.get("Y", 0.5)
    if end == "exit":
        positive = (py > 0.9) or (px < 0.1)   # exit bottom or exit left
    else:
        positive = (py < 0.1) or (px > 0.9)   # entry top or entry right
    mult_y = +LABEL_PERP_OFFSET if positive else -LABEL_PERP_OFFSET
    return mult_y, -mult_y


def _label_valign(port_suffix: str, end: str, perp_y: int = 0) -> str:
    """Return verticalAlign for a label at the given end.

    Pins a vertex of the label box to the exit/entry anchor:
      bottom exit → 'top'    (label hangs below the anchor)
      top exit    → 'bottom' (label sits above the anchor)
      left/right  → 'top' or 'bottom' based on perp_y sign (vertex pinning)
    end: 'exit' for source labels, 'entry' for target labels.
    perp_y: perpendicular offset for this specific label (from _label_perp_y).
    """
    if not port_suffix:
        return "middle"
    vals: dict[str, float] = {}
    for m in _PORT_VAL_RE.finditer(port_suffix):
        if m.group(1) == end:
            vals[m.group(2)] = float(m.group(3))
    px = vals.get("X", 0.5)
    py = vals.get("Y", 0.5)
    if py > 0.9:
        return "top"      # exits/enters through bottom face
    if py < 0.1:
        return "bottom"   # exits/enters through top face
    # Horizontal exit/entry (left or right face): pin the near vertex of the label.
    # Draw.io perpendicular y is edge-direction-relative, so the sign meaning
    # flips for right-going edges: y > 0 = canvas UP (not DOWN).
    edge_rightward = (px > 0.99 and end == "exit") or (px < 0.01 and end == "entry")
    effective_perp = -perp_y if edge_rightward else perp_y
    if effective_perp > 0:
        return "top"    # label displaced downward → pin top vertex at anchor
    if effective_perp < 0:
        return "bottom" # label displaced upward   → pin bottom vertex at anchor
    return "middle"



def _style_is_valid(style: str, valid: frozenset[str]) -> bool:
    """Check if a style string matches a canonical style (with optional trailing semicolon or port tokens)."""
    if style in valid:
        return True
    if style.rstrip(";") in valid:
        return True
    port_stripped = _strip_port_tokens(style).rstrip(";")
    if port_stripped in valid:
        return True
    # Strip dynamic per-cell alignment properties (appended after base style)
    s = re.sub(r';verticalAlign=[^;]+$', '', port_stripped)
    s = re.sub(r';align=[^;]+$', '', s)
    return s in valid


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common HTML entities."""
    clean = re.sub(r"<[^>]+>", "", text)
    return (
        clean.replace("&lt;", "<")
             .replace("&gt;", ">")
             .replace("&amp;", "&")
             .replace("&nbsp;", " ")
    )


def _parse_trans_label(label: str) -> tuple[str, str | None]:
    """Return (event_name, guard_or_None) from a multi-line transition label.

    Label format (from render_to_drawio_state):
        {trans_id}<br>{event}({params})<br>[{guard}]
    Lines are split on '<br>' and HTML-stripped.
    Line 0: canonical ID (skip)
    Line 1: event signature
    Line 2+ (optional, starts with '['): guard
    """
    lines = [_strip_html(part).strip() for part in label.split("<br>")]
    lines = [l for l in lines if l]  # remove blanks
    event_line = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
    event_name = event_line.split("(")[0].strip()
    guard = None
    for line in lines[2:]:
        if line.startswith("[") and line.endswith("]"):
            guard = line[1:-1]
    return event_name, guard


def _read_yaml_roundtrip(path: Path):
    """Load a YAML file using ruamel.yaml round-trip mode (preserves comments/order)."""
    rt = RuamelYAML()
    return rt.load(path.read_text(encoding="utf-8"))


def _write_yaml_roundtrip(data, path: Path) -> None:
    """Write a ruamel CommentedMap back to a YAML file."""
    rt = RuamelYAML()
    rt.default_flow_style = False
    buf = io.StringIO()
    rt.dump(data, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API — validate_drawio and sync_from_drawio
# ---------------------------------------------------------------------------


def validate_drawio(domain: str, xml: bytes | str) -> list[dict]:
    """Validate Draw.io XML against the canonical MDF bijection schema.

    Returns empty list for valid canonical XML (all mxCell styles recognized).
    Returns error issues for any mxCell with an unrecognized style string.
    Returns a parse-error issue if the XML is malformed.
    Never raises.
    """
    issues: list[dict] = []
    xml_bytes = _to_xml_bytes(xml)

    try:
        root = DET.fromstring(xml_bytes)
    except Exception as exc:
        return [_make_issue(
            f"XML parse error: {exc}",
            location="xml_input",
            severity="error",
        )]

    valid = _valid_styles()
    for cell in root.iter("mxCell"):
        cell_id = cell.get("id", "")
        if cell_id in ("0", "1"):
            continue
        style = cell.get("style")
        if style is None:
            continue
        if not _style_is_valid(style, valid):
            issues.append(_make_issue(
                "Unrecognized Draw.io cell style",
                location=f"xml:cell:{cell_id}",
                value=style,
                fix="Use only canonical MDF style strings from BIJECTION_TABLE",
                severity="error",
            ))

    return issues


def sync_from_drawio(domain: str, class_name: str, xml: bytes | str) -> list[dict]:
    """Sync Draw.io XML topology changes for one active class back to its state YAML.

    Merges structural changes (add/remove states, transitions) while preserving
    YAML-only fields (pycca action bodies, guards).
    Automatically runs validate_domain after sync; its issues appear in returned list.
    Returns info-severity issues for each new/deleted element.
    Unrecognized cell styles produce an issue and are skipped — sync does not abort.
    Never raises.
    """
    issues: list[dict] = []
    xml_bytes = _to_xml_bytes(xml)

    # 1. Parse XML safely
    try:
        root = DET.fromstring(xml_bytes)
    except Exception as exc:
        return [_make_issue(
            f"XML parse error: {exc}",
            location="xml_input",
            severity="error",
        )]

    # 2. Locate domain path
    domain_path = MODEL_ROOT / domain
    if not domain_path.exists():
        return [_make_issue(
            f"Domain path not found: {domain_path}",
            location=f"domain={domain}",
            severity="error",
        )]

    # 3. Load state YAML with ruamel round-trip mode to preserve entry_action
    yaml_path = domain_path / "state-diagrams" / f"{class_name}.yaml"
    if not yaml_path.exists():
        return [_make_issue(
            f"State diagram YAML not found: {yaml_path}",
            location=f"domain={domain}, class={class_name}",
            severity="error",
        )]

    try:
        sd_data = _read_yaml_roundtrip(yaml_path)
    except Exception as exc:
        return [_make_issue(
            f"Failed to load {class_name}.yaml: {exc}",
            location=str(yaml_path),
            severity="error",
        )]

    valid = _valid_styles()

    # 4. Scan mxCells and classify
    # Build lookup: state_name -> existing YAML dict (CommentedMap)
    existing_states: dict[str, object] = {}
    if "states" in sd_data and sd_data["states"]:
        for s in sd_data["states"]:
            existing_states[s["name"]] = s

    existing_transitions: list[dict] = list(sd_data.get("transitions") or [])

    # Build a mapping from canonical trans ID -> existing transition dict
    # (trans IDs: domain:trans:ClassName:from_state:event:idx)
    existing_trans_by_id: dict[str, dict] = {}
    for idx, t in enumerate(existing_transitions):
        from_state = t.get("from", "")
        event = t.get("event", "")
        tid = transition_id(domain, class_name, from_state, event, idx)
        existing_trans_by_id[tid] = t

    # Build a reverse mapping: canonical state_id -> state_name
    state_id_to_name: dict[str, str] = {}
    for sname in existing_states:
        state_id_to_name[state_id(domain, class_name, sname)] = sname

    # Scan cells from Draw.io
    drawio_state_names: set[str] = set()
    drawio_trans_ids: set[str] = set()
    new_states: list[str] = []  # state names to add
    new_transitions: list[dict] = []  # transition dicts to add

    for cell in root.iter("mxCell"):
        cell_id = cell.get("id", "")
        if cell_id in ("0", "1"):
            continue

        cell_style = cell.get("style")
        if cell_style is None:
            continue

        # Check style is recognized (with trailing-semicolon tolerance) for ALL cells
        if not _style_is_valid(cell_style, valid):
            issues.append(_make_issue(
                "Unrecognized Draw.io cell style — cell skipped during sync",
                location=f"xml:cell:{cell_id}",
                value=cell_style,
                fix="Use only canonical MDF style strings from BIJECTION_TABLE",
                severity="warning",
            ))
            continue

        # Only process canonical MDF cells (ID contains ":")
        if ":" not in (cell_id or ""):
            continue

        # Parse ID parts: domain:type:...
        parts = cell_id.split(":")
        if len(parts) < 3:
            continue
        id_domain = parts[0]
        type_part = parts[1]

        # Skip cells from other domains (shouldn't happen but be safe)
        if id_domain.lower() != domain.lower():
            continue

        if type_part == "state":
            # format: domain:state:ClassName:state_name
            if len(parts) < 4:
                continue
            state_class = parts[2]
            state_name = parts[3]
            if state_class != class_name:
                continue
            if state_name == "__initial__":
                continue  # pseudostate — not synced
            drawio_state_names.add(state_name)
            if state_name not in existing_states:
                new_states.append(state_name)

        elif type_part == "trans":
            # format: domain:trans:ClassName:from_state:event:idx
            if len(parts) < 6:
                continue
            trans_class = parts[2]
            if trans_class != class_name:
                continue
            from_state_name_raw = parts[3]
            if from_state_name_raw == "__initial__":
                continue  # initial pseudo transition — not synced

            drawio_trans_ids.add(cell_id)

            if cell_id not in existing_trans_by_id:
                # New transition — parse label
                label = cell.get("value", "")
                event_name, guard = _parse_trans_label(label) if label else ("", None)

                # Resolve source and target state names from cell attributes
                source_cell_id = cell.get("source", "")
                target_cell_id = cell.get("target", "")
                from_state_name = state_id_to_name.get(source_cell_id, from_state_name_raw)
                to_state_name = state_id_to_name.get(target_cell_id, parts[4] if len(parts) > 4 else "")

                new_transitions.append({
                    "from": from_state_name,
                    "to": to_state_name,
                    "event": event_name or parts[4],
                    "guard": guard,
                    "action": None,
                })

        # Skip: attr, sep, attrs, methods, assoc, class, initial_pseudo, bridge
        # (class-diagram sync is out of scope for this per-class function)

    # 5. Apply state changes
    # Add new states
    for sname in new_states:
        sd_data["states"].append({"name": sname, "entry_action": None})
        issues.append(_make_issue(
            f"New state '{sname}' added from Draw.io",
            location=f"state-diagrams/{class_name}.yaml",
            value=sname,
            severity="info",
        ))

    # Remove deleted states (in YAML but not in Draw.io)
    deleted_states = set(existing_states) - drawio_state_names
    if deleted_states and drawio_state_names:  # only delete if Draw.io had any state cells
        remaining = [s for s in sd_data["states"] if s["name"] not in deleted_states]
        sd_data["states"] = remaining
        for sname in deleted_states:
            issues.append(_make_issue(
                f"State '{sname}' removed (not present in Draw.io)",
                location=f"state-diagrams/{class_name}.yaml",
                value=sname,
                severity="info",
            ))

    # Add new transitions
    if "transitions" not in sd_data or sd_data["transitions"] is None:
        sd_data["transitions"] = []
    for t in new_transitions:
        sd_data["transitions"].append(t)
        issues.append(_make_issue(
            f"New transition '{t['event']}' from '{t['from']}' to '{t['to']}' added",
            location=f"state-diagrams/{class_name}.yaml",
            severity="info",
        ))

    # Remove deleted transitions (canonical ID no longer in Draw.io)
    if drawio_trans_ids is not None and existing_trans_by_id:
        deleted_trans_ids = set(existing_trans_by_id) - drawio_trans_ids
        if deleted_trans_ids and drawio_trans_ids:
            # Rebuild transitions list excluding deleted ones
            remaining_trans = [t for tid, t in existing_trans_by_id.items() if tid not in deleted_trans_ids]
            # Append any newly added transitions
            sd_data["transitions"] = remaining_trans + new_transitions
            for tid in deleted_trans_ids:
                issues.append(_make_issue(
                    f"Transition '{tid}' removed (not present in Draw.io)",
                    location=f"state-diagrams/{class_name}.yaml",
                    value=tid,
                    severity="info",
                ))

    # 6. Write updated state YAML with ruamel round-trip (preserves entry_action)
    try:
        _write_yaml_roundtrip(sd_data, yaml_path)
    except Exception as exc:
        issues.append(_make_issue(
            f"Failed to write {class_name}.yaml: {exc}",
            location=str(yaml_path),
            severity="error",
        ))
        return issues

    # 7. Run validate_class for this class and append its issues
    try:
        from tools.validation import validate_class
        validation_issues = validate_class(domain, class_name, report_missing=False)
        issues.extend(validation_issues)
    except Exception as exc:
        issues.append(_make_issue(
            f"validate_class raised an unexpected error: {exc}",
            location=f"domain={domain}, class={class_name}",
            severity="error",
        ))

    return issues
