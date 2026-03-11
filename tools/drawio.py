"""
drawio — Draw.io rendering, validation, and sync tools.

Implemented in plan 04-02 (Phase 4).

Public API:
    render_to_drawio(domain)           -> list[dict]
    render_to_drawio_class(domain)     -> list[dict]
    render_to_drawio_state(domain, class_name) -> list[dict]
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import igraph as ig
import yaml
from lxml import etree

from schema.drawio_schema import (
    STYLE_ASSOCIATION,
    STYLE_ATTRIBUTE,
    STYLE_CLASS,
    STYLE_INITIAL_PSEUDO,
    STYLE_SEPARATOR,
    STYLE_STATE,
    STYLE_TRANSITION,
    association_id,
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
STATE_H = 50     # fixed state height
INIT_SIZE = 20   # initial pseudostate diameter
MARGIN = 60      # canvas margin

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
    return frozenset(ids)


def _structure_matches_class(
    domain_path: Path, domain: str, cd: ClassDiagramFile
) -> bool:
    """Return True if existing class-diagram.drawio has the same element set."""
    drawio_path = domain_path / "class-diagram.drawio"
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
    drawio_path = domain_path / "state-diagrams" / f"{class_name}.drawio"
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
    name_to_idx = {cls.name: i for i, cls in enumerate(classes)}
    edges: list[tuple[int, int]] = []
    for assoc in cd.associations:
        src = name_to_idx.get(assoc.point_1)
        tgt = name_to_idx.get(assoc.point_2)
        if src is not None and tgt is not None and src != tgt:
            edges.append((src, tgt))

    canvas_w = max(1200, n * 280)
    canvas_h = max(800, 600)

    positions = _layout_for_canvas(n, edges, canvas_w, canvas_h)

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
    for assoc in cd.associations:
        aid = association_id(domain, assoc.name)
        src_cid = class_id(domain, assoc.point_1)
        tgt_cid = class_id(domain, assoc.point_2)
        assoc_cell = etree.SubElement(
            root_el, "mxCell",
            id=aid, value=assoc.name,
            style=STYLE_ASSOCIATION, edge="1",
            source=src_cid, target=tgt_cid, parent="1",
        )
        etree.SubElement(
            assoc_cell, "mxGeometry",
            attrib={"relative": "1", "as": "geometry"},
        )

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
    # Transition edges
    for trans in sd.transitions:
        src = state_name_to_idx.get(trans.from_state)
        tgt = state_name_to_idx.get(trans.to)
        if src is not None and tgt is not None:
            edges.append((src, tgt))

    canvas_w = max(800, n_vertices * 200)
    canvas_h = max(600, 400)

    positions = _layout_for_canvas(n_vertices, edges, canvas_w, canvas_h)

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

    # State nodes
    for i, st in enumerate(sd.states):
        vertex_idx = 1 + i
        x = int(positions[vertex_idx][0])
        y = int(positions[vertex_idx][1])
        sid = state_id(domain, class_name, st.name)
        value = st.name
        if st.entry_action:
            value = f"{st.name}<br>──────────────────<br><i>entry /</i><br>{st.entry_action}"
        state_cell = etree.SubElement(
            root_el, "mxCell",
            id=sid, value=value,
            style=STYLE_STATE, vertex="1", parent="1",
        )
        etree.SubElement(
            state_cell, "mxGeometry",
            x=str(x), y=str(y), width=str(STATE_W), height=str(STATE_H),
            attrib={"as": "geometry"},
        )

    # Initial -> initial_state transition (no label)
    init_trans_cid = f"{domain.lower()}:trans:{class_name}:__initial__:__init__:0"
    init_target_sid = state_id(domain, class_name, initial_state_name)
    init_trans = etree.SubElement(
        root_el, "mxCell",
        id=init_trans_cid, value="",
        style=STYLE_TRANSITION, edge="1",
        source=init_cid, target=init_target_sid, parent="1",
    )
    etree.SubElement(init_trans, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    # Transition edges
    # Build event lookup map for param sigs
    event_map = {e.name: e for e in sd.events} if sd.events else {}

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

        trans_cell = etree.SubElement(
            root_el, "mxCell",
            id=tid, value=label,
            style=STYLE_TRANSITION, edge="1",
            source=src_sid, target=tgt_sid, parent="1",
        )
        etree.SubElement(
            trans_cell, "mxGeometry",
            attrib={"relative": "1", "as": "geometry"},
        )

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

    drawio_path = domain_path / "class-diagram.drawio"

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

    drawio_dir = domain_path / "state-diagrams"
    drawio_dir.mkdir(parents=True, exist_ok=True)
    drawio_path = drawio_dir / f"{class_name}.drawio"

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
# Stubs for plans 04-03
# ---------------------------------------------------------------------------


def validate_drawio(domain: str, xml_bytes: bytes) -> list[dict]:
    """Validate Draw.io XML against the domain model. Implemented in plan 04-03."""
    raise NotImplementedError("validate_drawio is implemented in plan 04-03")


def sync_from_drawio(domain: str, class_name: str, xml_bytes: bytes) -> list[dict]:
    """Sync state diagram changes from Draw.io XML back to YAML. Implemented in plan 04-03."""
    raise NotImplementedError("sync_from_drawio is implemented in plan 04-03")
