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

import io
import re
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
    h = (3 + n_lines) * ROW_H + 16
    return max(STATE_H, h)


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

    # Group edge indices by (vertex, side, direction)
    slot_edges: dict[tuple, list[int]] = {}
    for idx, info in enumerate(edge_info):
        if info is None:
            continue
        src, src_side, tgt, tgt_side = info
        slot_edges.setdefault((src, src_side, "exit"), []).append(idx)
        slot_edges.setdefault((tgt, tgt_side, "entry"), []).append(idx)

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

    for (vertex, side, direction), idxs in slot_edges.items():
        n = len(idxs)
        for k, idx in enumerate(idxs):
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

    # Score each corner by combined occupancy of its two adjacent sides
    corner_sides = [
        ("right", "top"),     # 0: top-right
        ("right", "bottom"),  # 1: bottom-right
        ("bottom", "left"),   # 2: bottom-left
        ("top",   "left"),    # 3: top-left
    ]
    scores = sorted(
        range(len(corner_sides)),
        key=lambda i: (side_count[corner_sides[i][0]] + side_count[corner_sides[i][1]], i),
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


def _layout_for_canvas(
    n_vertices: int,
    edges: list[tuple[int, int]],
    canvas_w: int,
    canvas_h: int,
    margin: int = MARGIN,
) -> list[tuple[float, float]]:
    """Run Sugiyama layout and return (x, y) per vertex, fitted to the canvas.

    Edge cases:
    - n_vertices == 0 -> returns []
    - n_vertices == 1 -> returns [(canvas_w // 2, canvas_h // 2)] (no igraph call)
    """
    if n_vertices == 0:
        return []
    if n_vertices == 1:
        return [(canvas_w // 2, canvas_h // 2)]

    g = ig.Graph(n=n_vertices, edges=edges, directed=True)
    layout = g.layout_sugiyama()
    # Slice to original vertex count — igraph Sugiyama may inflate with dummy vertices
    sliced = ig.Layout(layout.coords[:n_vertices])
    sliced.fit_into((margin, margin, canvas_w - margin, canvas_h - margin))
    return [(sliced.coords[i][0], sliced.coords[i][1]) for i in range(n_vertices)]


def _attr_label(vis: str, scope: str, name: str, type_: str) -> str:
    """Format a UML attribute label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    text = f"{name}: {type_}"
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
    param_sig = ", ".join(f"{p.name}: {p.type}" for p in params)
    ret = f": {return_type}" if return_type else ""
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
        ids.add(association_label_id(domain, assoc.name, "src"))
        ids.add(association_label_id(domain, assoc.name, "tgt"))
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


def _build_class_diagram_xml(domain: str, cd: ClassDiagramFile) -> bytes:
    """Build the full mxfile XML for a class diagram. Returns UTF-8 bytes."""
    classes = cd.classes
    n = len(classes)

    # Build edges from associations (index-based)
    # layout_edges excludes self-loops (igraph Sugiyama doesn't need them for placement)
    # all_edges includes self-loops so _assign_edge_ports can assign corner anchors
    name_to_idx = {cls.name: i for i, cls in enumerate(classes)}
    layout_edges: list[tuple[int, int]] = []
    all_edges: list[tuple[int, int]] = []
    assoc_edge_idx: list[int | None] = []
    for assoc in cd.associations:
        src = name_to_idx.get(assoc.point_1)
        tgt = name_to_idx.get(assoc.point_2)
        if src is not None and tgt is not None:
            assoc_edge_idx.append(len(all_edges))
            all_edges.append((src, tgt))
            if src != tgt:
                layout_edges.append((src, tgt))
        else:
            assoc_edge_idx.append(None)

    canvas_w = max(1200, n * 280)
    canvas_h = max(800, 600)

    positions = _layout_for_canvas(n, layout_edges, canvas_w, canvas_h)
    port_suffixes = _assign_edge_ports(all_edges, positions)

    # Apply greedy x-axis nudge pass to resolve horizontal overlaps
    # Sort class indices by x position, then ensure each adjacent pair has gap >= CLASS_W
    if n > 1:
        sorted_indices = sorted(range(n), key=lambda i: positions[i][0])
        pos_list = list(positions)
        for k in range(1, len(sorted_indices)):
            prev_i = sorted_indices[k - 1]
            curr_i = sorted_indices[k]
            if pos_list[curr_i][0] - pos_list[prev_i][0] < CLASS_W:
                pos_list[curr_i] = (
                    pos_list[prev_i][0] + CLASS_W,
                    pos_list[curr_i][1],
                )
        positions = pos_list

    # Pre-compute per-class heights for self-loop waypoint calculation
    class_heights = {
        i: _class_height(len(cls.attributes), len(cls.methods))
        for i, cls in enumerate(classes)
    }

    # Build XML
    mxfile = etree.Element("mxfile", compressed="false", version="24.0.0")
    diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
    etree.SubElement(
        diagram, "mxGraphModel",
        dx="1034", dy="546", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth=str(canvas_w), pageHeight=str(canvas_h),
        math="0", shadow="0",
    )
    model_el = diagram[0]
    root_el = etree.SubElement(model_el, "root")
    etree.SubElement(root_el, "mxCell", id="0")
    etree.SubElement(root_el, "mxCell", id="1", parent="0")

    for i, cls in enumerate(classes):
        x = int(positions[i][0])
        y = int(positions[i][1])
        height = _class_height(len(cls.attributes), len(cls.methods))
        cid = class_id(domain, cls.name)

        # Swimlane cell
        cls_cell = etree.SubElement(
            root_el, "mxCell",
            id=cid, value=f"<<{cls.stereotype}>>\n{cls.name}",
            style=STYLE_CLASS, vertex="1", parent="1",
        )
        etree.SubElement(
            cls_cell, "mxGeometry",
            x=str(x), y=str(y), width=str(CLASS_W), height=str(height),
            attrib={"as": "geometry"},
        )

        # Attributes cell
        attrs_h = max(len(cls.attributes), 1) * ROW_H
        attr_text = "<br>".join(
            _attr_label(a.visibility, a.scope, a.name, a.type)
            for a in cls.attributes
        ) if cls.attributes else ""
        attrs_cell = etree.SubElement(
            root_el, "mxCell",
            id=f"{cid}:attrs", value=attr_text,
            style=STYLE_ATTRIBUTE, vertex="1", parent=cid,
        )
        etree.SubElement(
            attrs_cell, "mxGeometry",
            y=str(HEADER_H), width=str(CLASS_W), height=str(attrs_h),
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
            y=str(sep_y), width=str(CLASS_W), height=str(SEP_H),
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
            y=str(sep_y + SEP_H), width=str(CLASS_W), height=str(methods_h),
            attrib={"as": "geometry"},
        )

    # Association edges
    self_loop_count: dict[int, int] = {}
    for i, assoc in enumerate(cd.associations):
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
            waypoints = _self_loop_waypoints(corner, bx, by, CLASS_W, class_heights[src_v])
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
        if waypoints:
            arr = etree.SubElement(geo, "Array", attrib={"as": "points"})
            for wx, wy in waypoints:
                etree.SubElement(arr, "mxPoint", x=str(int(wx)), y=str(int(wy)))

        # Multiplicity + verb phrase near point_1 end
        src_label = etree.SubElement(
            root_el, "mxCell",
            id=association_label_id(domain, assoc.name, "src"),
            value=f"{assoc.mult_2_to_1}\n{assoc.phrase_2_to_1}",
            style=STYLE_ASSOC_LABEL, vertex="1", parent=aid,
        )
        etree.SubElement(src_label, "mxGeometry",
            x="-0.9", y="-10",
            attrib={"relative": "1", "as": "geometry"})

        # Multiplicity + verb phrase near point_2 end
        tgt_label = etree.SubElement(
            root_el, "mxCell",
            id=association_label_id(domain, assoc.name, "tgt"),
            value=f"{assoc.mult_1_to_2}\n{assoc.phrase_1_to_2}",
            style=STYLE_ASSOC_LABEL, vertex="1", parent=aid,
        )
        etree.SubElement(tgt_label, "mxGeometry",
            x="0.9", y="-10",
            attrib={"relative": "1", "as": "geometry"})

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

    canvas_w = max(1200, n_vertices * 250)
    canvas_h = max(900, n_vertices * 220)

    positions = _layout_for_canvas(n_vertices, edges, canvas_w, canvas_h)
    port_suffixes = _assign_edge_ports(edges, positions)

    # Build XML
    mxfile = etree.Element("mxfile", compressed="false", version="24.0.0")
    diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
    etree.SubElement(
        diagram, "mxGraphModel",
        dx="1034", dy="546", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth=str(canvas_w), pageHeight=str(canvas_h),
        math="0", shadow="0",
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

    # Pre-compute per-state heights for self-loop waypoint calculation
    # vertex index 1+i maps to sd.states[i]
    state_heights = {1 + i: _state_height(st.entry_action) for i, st in enumerate(sd.states)}

    # State nodes
    for i, st in enumerate(sd.states):
        vertex_idx = 1 + i
        x = int(positions[vertex_idx][0])
        y = int(positions[vertex_idx][1])
        sid = state_id(domain, class_name, st.name)
        value = st.name
        if st.entry_action:
            action_html = st.entry_action.replace('\n', '<br>')
            value = f"{st.name}<br>──────────────────<br><i>entry /</i><br>{action_html}"
        state_cell = etree.SubElement(
            root_el, "mxCell",
            id=sid, value=value,
            style=STYLE_STATE, vertex="1", parent="1",
        )
        etree.SubElement(
            state_cell, "mxGeometry",
            x=str(x), y=str(y), width=str(STATE_W), height=str(state_heights[vertex_idx]),
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
    etree.SubElement(init_trans, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

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
            trans_waypoints = _self_loop_waypoints(corner, bx, by, STATE_W, state_heights[src_v])
        else:
            port_suffix = port_suffixes[edge_idx] if edge_idx is not None else ""

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
        if trans_waypoints:
            arr = etree.SubElement(geo, "Array", attrib={"as": "points"})
            for wx, wy in trans_waypoints:
                etree.SubElement(arr, "mxPoint", x=str(int(wx)), y=str(int(wy)))

    return etree.tostring(mxfile, encoding="unicode", xml_declaration=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_to_drawio_class(domain: str) -> list[dict]:
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

    if _structure_matches_class(domain_path, domain, cd):
        return [{"file": str(drawio_path), "status": "skipped"}]

    xml_bytes = _build_class_diagram_xml(domain, cd)
    drawio_path.write_bytes(xml_bytes)
    return [{"file": str(drawio_path), "status": "written"}]


def render_to_drawio_state(domain: str, class_name: str) -> list[dict]:
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

    if _structure_matches_state(domain_path, domain, class_name, sd):
        return [{"file": str(drawio_path), "status": "skipped"}]

    xml_bytes = _build_state_diagram_xml(domain, sd)
    drawio_path.write_bytes(xml_bytes)
    return [{"file": str(drawio_path), "status": "written"}]


def render_to_drawio(domain: str) -> list[dict]:
    """Render all diagrams for a domain: class diagram + all active-class state diagrams.

    Returns combined list of per-file result dicts (class diagram first,
    then state diagrams in class list order).
    Errors are returned as issue dicts with 'severity': 'error'.
    """
    results: list[dict] = []

    # Render class diagram
    class_results = render_to_drawio_class(domain)
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
            state_results = render_to_drawio_state(domain, cls.name)
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


def _strip_port_tokens(style: str) -> str:
    return _PORT_RE.sub('', style)


def _style_is_valid(style: str, valid: frozenset[str]) -> bool:
    """Check if a style string matches a canonical style (with optional trailing semicolon or port tokens)."""
    if style in valid:
        return True
    if style.rstrip(";") in valid:
        return True
    port_stripped = _strip_port_tokens(style).rstrip(";")
    return port_stripped in valid


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
