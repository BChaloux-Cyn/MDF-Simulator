"""
Draw.io canonical bijection constants — style strings for all MDF model elements.

These constants are the canonical bijection between YAML model elements and
Draw.io mxCell style strings. They are locked values derived from RESEARCH.md.

Do not modify these strings without updating validate_drawio and sync_from_drawio
in Phase 4.
"""

__all__ = [
    "STYLE_CLASS",
    "STYLE_ATTRIBUTE",
    "STYLE_SEPARATOR",
    "STYLE_ASSOCIATION",
    "STYLE_ASSOC_LABEL",
    "STYLE_STATE",
    "STYLE_INITIAL_PSEUDO",
    "STYLE_TRANSITION",
    "STYLE_BRIDGE",
    "BIJECTION_TABLE",
    "class_id",
    "attribute_id",
    "separator_id",
    "association_id",
    "state_id",
    "transition_id",
    "render_sample_xml",
]

# ---------------------------------------------------------------------------
# Style constants — immutable canonical mxCell style strings
# ---------------------------------------------------------------------------

STYLE_CLASS = (
    "swimlane;fontStyle=1;horizontal=1;"
    "startSize=26;fillColor=#dae8fc;strokeColor=#6c8ebf;rounded=0;"
)

STYLE_ATTRIBUTE = (
    "text;strokeColor=none;fillColor=none;align=left;"
    "verticalAlign=top;spacingLeft=4;spacingRight=4;"
    "html=1;overflow=hidden;rotatable=0;"
)

STYLE_SEPARATOR = (
    "line;strokeColor=inherit;fillColor=none;align=left;"
    "verticalAlign=middle;spacingTop=-1;spacingBottom=-1;"
    "spacingLeft=3;spacingRight=3;rotatable=0;"
)

STYLE_ASSOCIATION = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"

STYLE_ASSOC_LABEL = "edgeLabel;align=center;"

STYLE_STATE = "rounded=1;whiteSpace=wrap;html=1;arcSize=10;"

STYLE_INITIAL_PSEUDO = (
    "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    "fillColor=#000000;strokeColor=#000000;"
)

STYLE_TRANSITION = "edgeStyle=orthogonalEdgeStyle;html=1;"

STYLE_BRIDGE = "dashed=1;endArrow=open;endFill=0;html=1;"

# ---------------------------------------------------------------------------
# Bijection table — maps element type name to its style constant
# ---------------------------------------------------------------------------

BIJECTION_TABLE: dict[str, str] = {
    "class":          STYLE_CLASS,
    "attribute":      STYLE_ATTRIBUTE,
    "association":    STYLE_ASSOCIATION,
    "assoc_label":    STYLE_ASSOC_LABEL,
    "state":          STYLE_STATE,
    "initial_pseudo": STYLE_INITIAL_PSEUDO,
    "transition":     STYLE_TRANSITION,
    "bridge":         STYLE_BRIDGE,
    "separator":      STYLE_SEPARATOR,
}

# ---------------------------------------------------------------------------
# Deterministic ID generator functions
# Domain is always lowercased — this is the canonical form.
# ---------------------------------------------------------------------------


def class_id(domain: str, class_name: str) -> str:
    """Return deterministic mxCell ID for a class element."""
    return f"{domain.lower()}:class:{class_name}"


def attribute_id(domain: str, class_name: str, attr_name: str) -> str:
    """Return deterministic mxCell ID for an attribute element."""
    return f"{domain.lower()}:attr:{class_name}:{attr_name}"


def separator_id(domain: str, class_name: str) -> str:
    """Return deterministic mxCell ID for the attribute/method divider in a class."""
    return f"{domain.lower()}:sep:{class_name}"


def association_id(domain: str, assoc_name: str) -> str:
    """Return deterministic mxCell ID for an association element."""
    return f"{domain.lower()}:assoc:{assoc_name}"


def state_id(domain: str, class_name: str, state_name: str) -> str:
    """Return deterministic mxCell ID for a state element."""
    return f"{domain.lower()}:state:{class_name}:{state_name}"


def transition_id(
    domain: str, class_name: str, from_state: str, event: str, idx: int
) -> str:
    """Return deterministic mxCell ID for a transition element.

    idx disambiguates multiple transitions on the same (from_state, event) pair.
    """
    return f"{domain.lower()}:trans:{class_name}:{from_state}:{event}:{idx}"


# ---------------------------------------------------------------------------
# XML generator — for SCHEMA-04 round-trip testing only
# ---------------------------------------------------------------------------

from lxml import etree  # noqa: E402 — imported here to keep module lighter

_VIS = {"public": "+", "private": "-", "protected": "#"}


def _attr_label(vis: str, scope: str, name: str, type_: str) -> str:
    """Format a UML attribute label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    text = f"{name}: {type_}"
    if scope == "class":
        text = f"<u>{text}</u>"
    return f"{sym} {text}"


def _method_label(vis: str, scope: str, name: str, params: str, return_: str) -> str:
    """Format a UML method label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    sig = f"{name}({params}): {return_}"
    if scope == "class":
        sig = f"<u>{sig}</u>"
    return f"{sym} {sig}"


def render_sample_xml() -> bytes:
    """Generate a minimal representative Draw.io XML for round-trip testing.

    Produces an uncompressed mxfile (compressed='false') so Draw.io does not
    base64-encode the diagram on save, avoiding the Pitfall 2 decompression
    issue documented in RESEARCH.md.

    Class layout: UML two-section swimlane — attributes above divider, methods below.
    Visibility prefix: + public, - private, # protected.
    Class-scope members are HTML-underlined (<u>name</u>); requires html=1 in style.

    Returns UTF-8 encoded bytes of the full mxfile XML.
    """
    domain = "Hydraulics"

    mxfile = etree.Element("mxfile", compressed="false", version="24.0.0")
    diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
    etree.SubElement(
        diagram, "mxGraphModel",
        dx="1034", dy="546", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth="1169", pageHeight="827",
        math="0", shadow="0",
    )
    model_el = diagram[0]
    root_el = etree.SubElement(model_el, "root")
    etree.SubElement(root_el, "mxCell", id="0")
    etree.SubElement(root_el, "mxCell", id="1", parent="0")

    # Row height constants
    ROW_H = 20   # px per text row
    SEP_H = 8    # px for separator line

    HEADER_H = 26  # swimlane startSize — children y=0 is top of header, content starts at HEADER_H

    def _add_class(
        parent_el: etree._Element,
        cid: str,
        name: str,
        stereotype: str,
        x: int,
        y: int,
        width: int,
        attrs: list[tuple[str, str, str, str]],   # (attr_name, vis, scope, type_)
        methods: list[tuple[str, str, str, str, str]],  # (name, vis, scope, params, ret)
    ) -> None:
        """Add a UML class swimlane with two-section layout (attrs / sep / methods).

        Child y coordinates are absolute within the swimlane (y=0 is top of header).
        Content area starts at y=HEADER_H (26). No childLayout=stackLayout — children
        use explicit geometry so Draw.io does not auto-redistribute heights.
        """
        attrs_h = max(len(attrs), 1) * ROW_H
        methods_h = max(len(methods), 1) * ROW_H
        total_h = HEADER_H + attrs_h + SEP_H + methods_h

        cls_cell = etree.SubElement(
            parent_el, "mxCell",
            id=cid, value=f"<<{stereotype}>>\n{name}",
            style=STYLE_CLASS, vertex="1", parent="1",
        )
        etree.SubElement(
            cls_cell, "mxGeometry",
            x=str(x), y=str(y), width=str(width), height=str(total_h),
            attrib={"as": "geometry"},
        )

        # Attributes section — single cell, all lines joined with <br>
        attr_text = "<br>".join(
            _attr_label(vis, scope, n, t) for n, vis, scope, t in attrs
        ) if attrs else ""
        attrs_cell = etree.SubElement(
            parent_el, "mxCell",
            id=f"{cid}:attrs", value=attr_text,
            style=STYLE_ATTRIBUTE, vertex="1", parent=cid,
        )
        etree.SubElement(
            attrs_cell, "mxGeometry",
            y=str(HEADER_H), width=str(width), height=str(attrs_h),
            attrib={"as": "geometry"},
        )

        # Separator
        sep_y = HEADER_H + attrs_h
        sep_cell = etree.SubElement(
            parent_el, "mxCell",
            id=separator_id(domain, name), value="",
            style=STYLE_SEPARATOR, vertex="1", parent=cid,
        )
        etree.SubElement(
            sep_cell, "mxGeometry",
            y=str(sep_y), width=str(width), height=str(SEP_H),
            attrib={"as": "geometry"},
        )

        # Methods section — single cell, all lines joined with <br>
        method_text = "<br>".join(
            _method_label(vis, scope, n, p, r) for n, vis, scope, p, r in methods
        ) if methods else ""
        methods_cell = etree.SubElement(
            parent_el, "mxCell",
            id=f"{cid}:methods", value=method_text,
            style=STYLE_ATTRIBUTE, vertex="1", parent=cid,
        )
        etree.SubElement(
            methods_cell, "mxGeometry",
            y=str(sep_y + SEP_H), width=str(width), height=str(methods_h),
            attrib={"as": "geometry"},
        )

    # --- Class: Valve ---
    valve_cid = class_id(domain, "Valve")
    _add_class(
        root_el, valve_cid, "Valve", "entity", 100, 100, 220,
        attrs=[
            ("valve_id", "private", "instance", "ValveID"),
            ("position", "private", "instance", "Real"),
        ],
        methods=[
            ("open", "public", "instance", "target_position: Real", "null"),
            ("create", "public", "class", "valve_id: ValveID", "Valve"),
        ],
    )

    # --- Class: ActuatorPosition ---
    ap_cid = class_id(domain, "ActuatorPosition")
    _add_class(
        root_el, ap_cid, "ActuatorPosition", "entity", 420, 100, 220,
        attrs=[
            ("actuator_id", "private", "instance", "UniqueID"),
            ("stroke_count", "private", "instance", "Integer"),
        ],
        methods=[],
    )

    # --- Association R1: Valve -> ActuatorPosition ---
    r1_cid = association_id(domain, "R1")
    r1_cell = etree.SubElement(
        root_el, "mxCell",
        id=r1_cid, value="R1",
        style=STYLE_ASSOCIATION, edge="1",
        source=valve_cid, target=ap_cid, parent="1",
    )
    etree.SubElement(r1_cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    # --- State machine: Valve ---
    idle_cid = state_id(domain, "Valve", "Idle")
    idle_cell = etree.SubElement(
        root_el, "mxCell",
        id=idle_cid, value="Idle",
        style=STYLE_STATE, vertex="1", parent="1",
    )
    etree.SubElement(
        idle_cell, "mxGeometry",
        x="100", y="300", width="160", height="50",
        attrib={"as": "geometry"},
    )

    # Opening state — has entry action displayed in a compartment below the name
    opening_cid = state_id(domain, "Valve", "Opening")
    opening_label = (
        "Opening"
        "<br>──────────────────"
        "<br><i>entry /</i>"
        "<br>self.target = rcvd_evt.target_position;"
        "<br>Timer::start_timer(timeout_ms);"
    )
    opening_cell = etree.SubElement(
        root_el, "mxCell",
        id=opening_cid, value=opening_label,
        style=STYLE_STATE, vertex="1", parent="1",
    )
    etree.SubElement(
        opening_cell, "mxGeometry",
        x="360", y="300", width="200", height="100",
        attrib={"as": "geometry"},
    )

    # Initial pseudostate
    init_cid = f"{domain.lower()}:state:Valve:__initial__"
    init_cell = etree.SubElement(
        root_el, "mxCell",
        id=init_cid, value="",
        style=STYLE_INITIAL_PSEUDO, vertex="1", parent="1",
    )
    etree.SubElement(
        init_cell, "mxGeometry",
        x="40", y="315", width="20", height="20",
        attrib={"as": "geometry"},
    )

    # Initial -> Idle (no event label on initial transition)
    init_trans_cid = f"{domain.lower()}:trans:Valve:__initial__:__init__:0"
    init_trans = etree.SubElement(
        root_el, "mxCell",
        id=init_trans_cid, value="",
        style=STYLE_TRANSITION, edge="1",
        source=init_cid, target=idle_cid, parent="1",
    )
    etree.SubElement(init_trans, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    # Idle -> Opening: three-line label — ID / event signature / guard
    trans_cid = transition_id(domain, "Valve", "Idle", "Open", 0)
    trans_label = (
        f"{trans_cid}"
        "<br>Open(target_position: Real)"
        "<br>[self.pressure &lt; max_pressure]"
    )
    trans_cell = etree.SubElement(
        root_el, "mxCell",
        id=trans_cid, value=trans_label,
        style=STYLE_TRANSITION, edge="1",
        source=idle_cid, target=opening_cid, parent="1",
    )
    etree.SubElement(trans_cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

    return etree.tostring(mxfile, encoding="unicode", xml_declaration=False).encode("utf-8")
