"""Render and quality tests for the Elevator state diagram.

Generates output to tests/output/ for visual inspection:
  elevator-Elevator-state-diagram.drawio  — production output
"""
import re
import yaml
from pathlib import Path

import pytest
from lxml import etree

from schema.yaml_schema import StateDiagramFile
from tools.drawio import STATE_H, STATE_W, INIT_SIZE, _build_state_diagram_xml

FIXTURE_YAML = Path(__file__).parent / "fixtures" / "elevator-state-diagram.yaml"
OUTPUT_DIR = Path(__file__).parent / "output"
DOMAIN = "Elevator"
CLASS_NAME = "Elevator"


def _load_sd() -> StateDiagramFile:
    return StateDiagramFile(**yaml.safe_load(FIXTURE_YAML.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def diagram_xml() -> bytes:
    OUTPUT_DIR.mkdir(exist_ok=True)
    sd = _load_sd()
    xml = _build_state_diagram_xml(DOMAIN, sd)
    (OUTPUT_DIR / "elevator-Elevator-state-diagram.drawio").write_bytes(xml)
    return xml


def _cells_by_id(xml_bytes: bytes) -> dict:
    root = etree.fromstring(xml_bytes)
    return {el.get("id"): el for el in root.iter("mxCell") if el.get("id")}


def _port_vals(style: str) -> dict[str, float]:
    return {m.group(1) + m.group(2): float(m.group(3))
            for m in re.finditer(r'(exit|entry)([XY])=([0-9.]+)', style)}


# ---------------------------------------------------------------------------
# Structural completeness
# ---------------------------------------------------------------------------

def test_all_states_present(diagram_xml):
    sd = _load_sd()
    cells = _cells_by_id(diagram_xml)
    for st in sd.states:
        sid = f"{DOMAIN.lower()}:state:{CLASS_NAME}:{st.name}"
        assert sid in cells, f"State cell missing: {sid}"


def test_initial_pseudostate_present(diagram_xml):
    cells = _cells_by_id(diagram_xml)
    init_id = f"{DOMAIN.lower()}:state:{CLASS_NAME}:__initial__"
    assert init_id in cells, "Initial pseudostate cell missing"


def test_all_transitions_have_edge_cells(diagram_xml):
    sd = _load_sd()
    cells = _cells_by_id(diagram_xml)
    trans_cells = [k for k in cells if ":trans:" in k and "__initial__" not in k]
    assert len(trans_cells) == len(sd.transitions), (
        f"Expected {len(sd.transitions)} transition edges, got {len(trans_cells)}"
    )


def test_initial_transition_has_no_label(diagram_xml):
    cells = _cells_by_id(diagram_xml)
    init_trans = next(
        (el for cid, el in cells.items()
         if ":trans:" in cid and "__initial__" in cid),
        None,
    )
    assert init_trans is not None, "Initial transition cell not found"
    assert init_trans.get("value", "") == "", (
        f"Initial transition should have empty label, got: {init_trans.get('value')!r}"
    )


# ---------------------------------------------------------------------------
# Layout quality
# ---------------------------------------------------------------------------

def test_no_overlapping_states(diagram_xml):
    cells = _cells_by_id(diagram_xml)
    boxes = []
    for cid, el in cells.items():
        if f":state:{CLASS_NAME}:" in cid and "__initial__" not in cid:
            geo = el.find("mxGeometry")
            if geo is not None:
                boxes.append((
                    int(geo.get("x", 0)), int(geo.get("y", 0)),
                    int(geo.get("width", STATE_W)), int(geo.get("height", STATE_H)),
                    cid,
                ))

    GAP = 10
    for i, (x1, y1, w1, h1, id1) in enumerate(boxes):
        for x2, y2, w2, h2, id2 in boxes[i + 1:]:
            h_sep = (x2 - (x1 + w1)) if x2 >= x1 else (x1 - (x2 + w2))
            v_sep = (y2 - (y1 + h1)) if y2 >= y1 else (y1 - (y2 + h2))
            assert h_sep >= GAP or v_sep >= GAP, (
                f"{id1} and {id2} overlap or are too close "
                f"(h_sep={h_sep}px, v_sep={v_sep}px, need {GAP}px on at least one axis)"
            )


def test_states_within_canvas(diagram_xml):
    root = etree.fromstring(diagram_xml)
    model = root.find(".//mxGraphModel")
    canvas_w = int(model.get("pageWidth", 9999))
    canvas_h = int(model.get("pageHeight", 9999))
    cells = _cells_by_id(diagram_xml)
    for cid, el in cells.items():
        if f":state:{CLASS_NAME}:" in cid and "__initial__" not in cid:
            geo = el.find("mxGeometry")
            x = int(geo.get("x", 0))
            y = int(geo.get("y", 0))
            h = int(geo.get("height", STATE_H))
            assert x + STATE_W <= canvas_w, f"{cid} extends past right edge"
            assert y + h <= canvas_h, f"{cid} extends past bottom edge"


def test_no_duplicate_exit_anchors(diagram_xml):
    root = etree.fromstring(diagram_xml)
    from collections import defaultdict
    exits_by_source: dict[str, list[tuple]] = defaultdict(list)
    for el in root.iter("mxCell"):
        if el.get("edge") != "1":
            continue
        src = el.get("source")
        if not src or "__initial__" in src:
            continue
        style = el.get("style", "")
        ports = _port_vals(style)
        if "exitX" in ports and "exitY" in ports:
            exits_by_source[src].append((ports["exitX"], ports["exitY"], el.get("id")))

    for src, anchors in exits_by_source.items():
        coords = [(x, y) for x, y, _ in anchors]
        dups = [a for a in anchors if coords.count((a[0], a[1])) > 1]
        assert not dups, f"Duplicate exit anchors on {src}: {dups}"


def test_no_duplicate_entry_anchors(diagram_xml):
    root = etree.fromstring(diagram_xml)
    from collections import defaultdict
    entries_by_target: dict[str, list[tuple]] = defaultdict(list)
    for el in root.iter("mxCell"):
        if el.get("edge") != "1":
            continue
        tgt = el.get("target")
        if not tgt or "__initial__" in tgt:
            continue
        style = el.get("style", "")
        ports = _port_vals(style)
        if "entryX" in ports and "entryY" in ports:
            entries_by_target[tgt].append((ports["entryX"], ports["entryY"], el.get("id")))

    for tgt, anchors in entries_by_target.items():
        coords = [(x, y) for x, y, _ in anchors]
        dups = [a for a in anchors if coords.count((a[0], a[1])) > 1]
        assert not dups, f"Duplicate entry anchors on {tgt}: {dups}"


# ---------------------------------------------------------------------------
# Visual / label quality
# ---------------------------------------------------------------------------

def test_transition_labels_contain_event(diagram_xml):
    sd = _load_sd()
    cells = _cells_by_id(diagram_xml)
    for trans in sd.transitions:
        trans_cells = [
            el for cid, el in cells.items()
            if ":trans:" in cid and f":{trans.from_state}:{trans.event}:" in cid
        ]
        assert trans_cells, f"No cell found for transition {trans.from_state} --{trans.event}--> {trans.to}"
        for el in trans_cells:
            label = el.get("value", "")
            assert trans.event in label, (
                f"Transition label for {trans.event} does not contain event name: {label!r}"
            )


def test_self_loop_transitions_have_waypoints(diagram_xml):
    sd = _load_sd()
    self_loop_events = {t.event for t in sd.transitions if t.from_state == t.to}
    assert self_loop_events, "No self-loop transitions in fixture — update test"

    root = etree.fromstring(diagram_xml)
    for el in root.iter("mxCell"):
        if el.get("edge") != "1" or el.get("source") != el.get("target"):
            continue
        if "__initial__" in (el.get("id") or ""):
            continue
        geo = el.find("mxGeometry")
        assert geo is not None
        arr = geo.find("Array")
        assert arr is not None, f"Self-loop {el.get('id')} missing waypoint Array"
        pts = arr.findall("mxPoint")
        assert len(pts) >= 3, f"Self-loop {el.get('id')} has fewer than 3 waypoints"


def test_states_with_entry_action_are_taller(diagram_xml):
    sd = _load_sd()
    cells = _cells_by_id(diagram_xml)
    for st in sd.states:
        sid = f"{DOMAIN.lower()}:state:{CLASS_NAME}:{st.name}"
        el = cells.get(sid)
        assert el is not None
        h = int(el.find("mxGeometry").get("height", 0))
        if st.entry_action:
            assert h > STATE_H, f"{st.name} has entry_action but height {h} == STATE_H ({STATE_H})"
        else:
            assert h == STATE_H, f"{st.name} has no entry_action but height {h} != STATE_H ({STATE_H})"


def test_initial_state_is_target_of_init_transition(diagram_xml):
    sd = _load_sd()
    cells = _cells_by_id(diagram_xml)
    init_trans = next(
        (el for cid, el in cells.items() if ":trans:" in cid and "__initial__" in cid),
        None,
    )
    assert init_trans is not None
    expected_target = f"{DOMAIN.lower()}:state:{CLASS_NAME}:{sd.initial_state}"
    assert init_trans.get("target") == expected_target, (
        f"Init transition targets {init_trans.get('target')!r}, expected {expected_target!r}"
    )
