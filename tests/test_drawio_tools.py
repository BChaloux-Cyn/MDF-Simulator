"""Tests for Draw.io MCP tools: render_to_drawio, validate_drawio, sync_from_drawio.

Test scaffold for MCP-05, MCP-06, MCP-07. All tests are skipped stubs;
implementations are added in plans 04-02 and 04-03.
"""
import pytest
import yaml
from pathlib import Path

# tools/drawio.py is a stub in Phase 4 plans 04-01 — no functions defined yet.
# Wrap the import so pytest can collect tests even before implementation.
try:
    from tools.drawio import (
        render_to_drawio,
        render_to_drawio_class,
        render_to_drawio_state,
        validate_drawio,
        sync_from_drawio,
        _remove_overlaps,
        _route_edges_around_boxes,
        _anchor_point,
        _segments_intersect,
        _route_path,
        _optimize_edge_routing,
        MARGIN,
    )
except ImportError:
    render_to_drawio = None
    render_to_drawio_class = None
    render_to_drawio_state = None
    validate_drawio = None
    sync_from_drawio = None
    _remove_overlaps = None
    _route_edges_around_boxes = None
    _anchor_point = None
    _segments_intersect = None
    _route_path = None
    _optimize_edge_routing = None
    MARGIN = 120


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_domain(tmp_path, monkeypatch):
    """Create a minimal 'hydraulics' domain under a temp directory tree.

    Directory layout::

        {tmp_path}/
          .design/
            model/
              hydraulics/
                class-diagram.yaml
                state-diagrams/
                  Pump.yaml

    ``monkeypatch.chdir(tmp_path)`` so MODEL_ROOT (.design/model) resolves
    relative to the temp directory, matching tool runtime expectations.

    Returns the domain name string "hydraulics".
    """
    domain_root = tmp_path / ".design" / "model" / "hydraulics"
    domain_root.mkdir(parents=True)
    (domain_root / "state-diagrams").mkdir()

    class_diagram = {
        "schema_version": "1.0.0",
        "domain": "hydraulics",
        "classes": [
            {
                "name": "Valve",
                "stereotype": "entity",
                "attributes": [
                    {"name": "valve_id", "type": "ValveID", "visibility": "private", "scope": "instance"},
                    {"name": "position", "type": "Real", "visibility": "private", "scope": "instance"},
                ],
                "methods": [
                    {
                        "name": "open",
                        "visibility": "public",
                        "scope": "instance",
                        "params": [{"name": "target_position", "type": "Real"}],
                        "return": "null",
                    }
                ],
            },
            {
                "name": "Pump",
                "stereotype": "active",
                "attributes": [
                    {"name": "pump_id", "type": "UniqueID", "visibility": "private", "scope": "instance"},
                ],
                "methods": [],
            },
        ],
        "associations": [
            {
                "name": "R1",
                "point_1": "Valve",
                "point_2": "Pump",
                "1_mult_2": "1",
                "2_mult_1": "M",
                "1_phrase_2": "drives",
                "2_phrase_1": "is driven by",
            }
        ],
        "bridges": [],
    }

    pump_state_diagram = {
        "schema_version": "1.0.0",
        "domain": "hydraulics",
        "class": "Pump",
        "initial_state": "Idle",
        "states": [
            {"name": "Idle"},
            {"name": "Running"},
        ],
        "events": [
            {"name": "Start"},
        ],
        "transitions": [
            {"from": "Idle", "to": "Running", "event": "Start"},
        ],
    }

    (domain_root / "class-diagram.yaml").write_text(
        yaml.dump(class_diagram, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    (domain_root / "state-diagrams" / "Pump.yaml").write_text(
        yaml.dump(pump_state_diagram, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    return "hydraulics"


# ---------------------------------------------------------------------------
# MCP-05: render_to_drawio tests
# ---------------------------------------------------------------------------

def test_render_class_diagram(tmp_domain, tmp_path):
    """MCP-05: Rendered class-diagram.drawio exists and contains class names."""
    result = render_to_drawio(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-class-diagram.drawio"
    assert drawio_path.exists(), "class-diagram.drawio was not created"
    xml_bytes = drawio_path.read_bytes()
    assert b"Valve" in xml_bytes
    assert b"Pump" in xml_bytes


def test_render_idempotent(tmp_domain, tmp_path):
    """MCP-05: Calling render twice produces byte-identical XML."""
    render_to_drawio(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-class-diagram.drawio"
    first_bytes = drawio_path.read_bytes()
    render_to_drawio(tmp_domain)
    second_bytes = drawio_path.read_bytes()
    assert first_bytes == second_bytes, "Render output differs between calls (not idempotent)"


def test_render_skip_unchanged(tmp_domain, tmp_path):
    """MCP-05: Second render does not modify mtime (or reports status 'skipped')."""
    result1 = render_to_drawio(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-class-diagram.drawio"
    mtime_after_first = drawio_path.stat().st_mtime

    result2 = render_to_drawio(tmp_domain)

    # Accept either: mtime unchanged OR at least one entry has status "skipped"
    statuses = [entry.get("status") for entry in result2 if isinstance(entry, dict)]
    mtime_after_second = drawio_path.stat().st_mtime
    assert (mtime_after_second == mtime_after_first) or ("skipped" in statuses), (
        "Second render rewrote the file when content was unchanged"
    )


def test_render_status_list(tmp_domain, tmp_path):
    """MCP-05: render_to_drawio returns a list of dicts with 'file' and 'status' keys."""
    result = render_to_drawio(tmp_domain)
    assert isinstance(result, list), "render_to_drawio must return a list"
    for entry in result:
        assert isinstance(entry, dict), f"Expected dict entry, got {type(entry)}"
        assert "file" in entry, f"Entry missing 'file' key: {entry}"
        assert "status" in entry, f"Entry missing 'status' key: {entry}"


# ---------------------------------------------------------------------------
# MCP-06: validate_drawio tests
# ---------------------------------------------------------------------------

def test_validate_drawio_valid(tmp_domain):
    """MCP-06: Canonical XML from render_sample_xml() produces no validation issues."""
    from schema.drawio_schema import render_sample_xml
    xml_bytes = render_sample_xml()
    issues = validate_drawio(tmp_domain, xml_bytes)
    errors = [i for i in issues if i.get("severity") == "error"]
    assert errors == [], f"Expected no errors on canonical XML, got: {errors}"


def test_validate_drawio_invalid_style(tmp_domain):
    """MCP-06: XML with an unknown mxCell style produces at least one error issue."""
    bad_xml = (
        b'<?xml version="1.0"?>'
        b'<mxfile compressed="false" version="24.0.0">'
        b'<diagram name="Page-1" id="page1">'
        b'<mxGraphModel><root>'
        b'<mxCell id="0"/>'
        b'<mxCell id="1" parent="0"/>'
        b'<mxCell id="bad1" value="X" style="freeform;unknown=1;" vertex="1" parent="1">'
        b'<mxGeometry x="10" y="10" width="80" height="40" as="geometry"/>'
        b'</mxCell>'
        b'</root></mxGraphModel>'
        b'</diagram></mxfile>'
    )
    issues = validate_drawio(tmp_domain, bad_xml)
    errors = [i for i in issues if i.get("severity") == "error"]
    assert len(errors) >= 1, f"Expected at least one error for unknown style, got: {issues}"


# ---------------------------------------------------------------------------
# MCP-07: sync_from_drawio tests
# ---------------------------------------------------------------------------

def test_sync_adds_state(tmp_domain, tmp_path):
    """MCP-07: Syncing XML that adds a 'Stopped' state cell updates Pump.yaml."""
    from schema.drawio_schema import STYLE_STATE, state_id
    new_state_id = state_id("hydraulics", "Pump", "Stopped")
    xml = (
        b'<?xml version="1.0"?>'
        b'<mxfile compressed="false" version="24.0.0">'
        b'<diagram name="Page-1" id="page1">'
        b'<mxGraphModel><root>'
        b'<mxCell id="0"/>'
        b'<mxCell id="1" parent="0"/>'
        + (
            f'<mxCell id="{new_state_id}" value="Stopped"'
            f' style="{STYLE_STATE}" vertex="1" parent="1">'
            f'<mxGeometry x="100" y="100" width="120" height="60" as="geometry"/>'
            f'</mxCell>'
        ).encode()
        + b'</root></mxGraphModel></diagram></mxfile>'
    )
    sync_from_drawio("hydraulics", "Pump", xml)
    pump_yaml_path = tmp_path / ".design" / "model" / "hydraulics" / "state-diagrams" / "Pump.yaml"
    contents = pump_yaml_path.read_text(encoding="utf-8")
    assert "Stopped" in contents, "Pump.yaml does not contain the new 'Stopped' state"


def test_sync_preserves_actions(tmp_domain, tmp_path):
    """MCP-07: Syncing does not strip entry_action from states already in YAML."""
    from schema.drawio_schema import STYLE_STATE, state_id

    # Add entry_action to Pump.yaml before syncing
    pump_yaml_path = tmp_path / ".design" / "model" / "hydraulics" / "state-diagrams" / "Pump.yaml"
    data = yaml.safe_load(pump_yaml_path.read_text(encoding="utf-8"))
    for state in data["states"]:
        if state["name"] == "Running":
            state["entry_action"] = "send Stop() to self;"
    pump_yaml_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    # Build XML from the existing states (Idle + Running)
    idle_id = state_id("hydraulics", "Pump", "Idle")
    running_id = state_id("hydraulics", "Pump", "Running")
    xml = (
        b'<?xml version="1.0"?>'
        b'<mxfile compressed="false" version="24.0.0">'
        b'<diagram name="Page-1" id="page1">'
        b'<mxGraphModel><root>'
        b'<mxCell id="0"/>'
        b'<mxCell id="1" parent="0"/>'
        + (
            f'<mxCell id="{idle_id}" value="Idle" style="{STYLE_STATE}" vertex="1" parent="1">'
            f'<mxGeometry x="50" y="50" width="120" height="60" as="geometry"/></mxCell>'
            f'<mxCell id="{running_id}" value="Running" style="{STYLE_STATE}" vertex="1" parent="1">'
            f'<mxGeometry x="250" y="50" width="120" height="60" as="geometry"/></mxCell>'
        ).encode()
        + b'</root></mxGraphModel></diagram></mxfile>'
    )
    sync_from_drawio("hydraulics", "Pump", xml)
    result_data = yaml.safe_load(pump_yaml_path.read_text(encoding="utf-8"))
    running_state = next(s for s in result_data["states"] if s["name"] == "Running")
    assert running_state.get("entry_action") == "send Stop() to self;", (
        "entry_action was lost during sync"
    )


def test_sync_runs_validate_model(tmp_domain, tmp_path):
    """MCP-07: Sync of valid XML returns no error-severity issues from validate_model."""
    from schema.drawio_schema import STYLE_STATE, state_id
    idle_id = state_id("hydraulics", "Pump", "Idle")
    running_id = state_id("hydraulics", "Pump", "Running")
    xml = (
        b'<?xml version="1.0"?>'
        b'<mxfile compressed="false" version="24.0.0">'
        b'<diagram name="Page-1" id="page1">'
        b'<mxGraphModel><root>'
        b'<mxCell id="0"/>'
        b'<mxCell id="1" parent="0"/>'
        + (
            f'<mxCell id="{idle_id}" value="Idle" style="{STYLE_STATE}" vertex="1" parent="1">'
            f'<mxGeometry x="50" y="50" width="120" height="60" as="geometry"/></mxCell>'
            f'<mxCell id="{running_id}" value="Running" style="{STYLE_STATE}" vertex="1" parent="1">'
            f'<mxGeometry x="250" y="50" width="120" height="60" as="geometry"/></mxCell>'
        ).encode()
        + b'</root></mxGraphModel></diagram></mxfile>'
    )
    issues = sync_from_drawio("hydraulics", "Pump", xml)
    if issues:
        errors = [i for i in issues if i.get("severity") == "error"]
        assert errors == [], f"sync_from_drawio produced error-severity issues: {errors}"


@pytest.fixture()
def tmp_domain_rich(tmp_path, monkeypatch):
    """Extends the hydraulics domain with a richer Pump state machine.

    Pump gets 3 states (Idle, Running, Fault) and 3 transitions so that
    multiple edges leave the same state (Idle → Running, Idle → Fault),
    exercising the anchor distribution logic.
    Running has a multi-line entry_action to exercise dynamic state height.
    """
    domain_root = tmp_path / ".design" / "model" / "hydraulics"
    domain_root.mkdir(parents=True)
    (domain_root / "state-diagrams").mkdir()

    class_diagram = {
        "schema_version": "1.0.0",
        "domain": "hydraulics",
        "classes": [
            {
                "name": "Valve",
                "stereotype": "entity",
                "attributes": [
                    {"name": "valve_id", "type": "ValveID", "visibility": "private", "scope": "instance"},
                    {"name": "position", "type": "Real", "visibility": "private", "scope": "instance"},
                ],
                "methods": [
                    {
                        "name": "open",
                        "visibility": "public",
                        "scope": "instance",
                        "params": [{"name": "target_position", "type": "Real"}],
                        "return": "null",
                    }
                ],
            },
            {
                "name": "Pump",
                "stereotype": "active",
                "attributes": [
                    {"name": "pump_id", "type": "UniqueID", "visibility": "private", "scope": "instance"},
                ],
                "methods": [],
            },
        ],
        "associations": [
            {
                "name": "R1",
                "point_1": "Valve",
                "point_2": "Pump",
                "1_mult_2": "1",
                "2_mult_1": "M",
                "1_phrase_2": "drives",
                "2_phrase_1": "is driven by",
            }
        ],
        "bridges": [],
    }

    pump_state_diagram = {
        "schema_version": "1.0.0",
        "domain": "hydraulics",
        "class": "Pump",
        "initial_state": "Idle",
        "states": [
            {"name": "Idle"},
            {
                "name": "Running",
                "entry_action": "self.rpm = rcvd_evt.target_rpm;\nPressure::start_monitor(self.pump_id);",
            },
            {"name": "Fault"},
        ],
        "events": [
            {"name": "Start"},
            {"name": "Stop"},
            {"name": "Error"},
        ],
        "transitions": [
            {"from": "Idle", "to": "Running", "event": "Start"},
            {"from": "Idle", "to": "Fault", "event": "Error"},
            {"from": "Running", "to": "Idle", "event": "Stop"},
        ],
    }

    (domain_root / "class-diagram.yaml").write_text(
        yaml.dump(class_diagram, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    (domain_root / "state-diagrams" / "Pump.yaml").write_text(
        yaml.dump(pump_state_diagram, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    return "hydraulics"


import re as _re

_CELL_PORT_RE = _re.compile(r'(exit|entry)(X|Y)=([^;]+)')


def _cells_by_id(xml_bytes: bytes) -> dict:
    """Parse mxfile XML and return {cell_id: mxCell_element} for all cells with ':'."""
    from lxml import etree
    root = etree.fromstring(xml_bytes)
    return {el.get("id"): el for el in root.iter("mxCell") if ":" in (el.get("id") or "")}


def _extract_ports(style: str) -> dict:
    return {m.group(1) + m.group(2): m.group(3) for m in _CELL_PORT_RE.finditer(style)}


# ---------------------------------------------------------------------------
# Rendering quality tests
# ---------------------------------------------------------------------------

def test_state_height_grows_with_entry_action(tmp_domain_rich, tmp_path):
    """Running state height is greater than STATE_H when it has a multi-line entry_action."""
    from tools.drawio import STATE_H
    result = render_to_drawio_state(tmp_domain_rich, "Pump")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain_rich}-Pump.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    running_cell = cells.get("hydraulics:state:Pump:Running")
    assert running_cell is not None, "Running state cell not found"
    geo = running_cell.find("mxGeometry")
    height = int(geo.get("height"))
    assert height > STATE_H, f"Running state height {height} should exceed STATE_H={STATE_H}"


def test_state_height_minimum_without_entry_action(tmp_domain_rich, tmp_path):
    """Idle state height equals STATE_H (no entry_action)."""
    from tools.drawio import STATE_H
    render_to_drawio_state(tmp_domain_rich, "Pump")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain_rich}-Pump.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    idle_cell = cells.get("hydraulics:state:Pump:Idle")
    assert idle_cell is not None, "Idle state cell not found"
    geo = idle_cell.find("mxGeometry")
    height = int(geo.get("height"))
    assert height == STATE_H, f"Idle state height {height} should equal STATE_H={STATE_H}"


def test_transition_label_has_xy_offset(tmp_domain, tmp_path):
    """Transition mxGeometry has non-zero x and y attributes for label offset."""
    render_to_drawio_state(tmp_domain, "Pump")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-Pump.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    trans_cells = {k: v for k, v in cells.items() if ":trans:" in k and "__initial__" not in k}
    assert trans_cells, "No transition cells found"
    for tid, cell in trans_cells.items():
        geo = cell.find("mxGeometry")
        assert geo is not None, f"No mxGeometry on {tid}"
        x = geo.get("x")
        y = geo.get("y")
        assert x is not None and x != "0", f"Transition {tid} label x={x!r} not offset"
        assert y is not None and y != "0", f"Transition {tid} label y={y!r} not offset"


def test_no_duplicate_exit_anchors(tmp_domain_rich, tmp_path):
    """For each source state, all outgoing edges have unique (exitX, exitY) pairs."""
    render_to_drawio_state(tmp_domain_rich, "Pump")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain_rich}-Pump.drawio"
    from lxml import etree
    root = etree.fromstring(drawio_path.read_bytes())
    # Group edges by source attribute
    source_to_exits = {}
    for el in root.iter("mxCell"):
        if el.get("edge") != "1":
            continue
        source = el.get("source")
        if not source or ":state:" not in source or "__initial__" in source:
            continue
        style = el.get("style", "")
        ports = _extract_ports(style)
        if "exitX" not in ports or "exitY" not in ports:
            continue
        key = (ports["exitX"], ports["exitY"])
        source_to_exits.setdefault(source, []).append(key)
    for source, keys in source_to_exits.items():
        assert len(keys) == len(set(keys)), (
            f"Source {source} has duplicate exit anchors: {keys}"
        )


def test_no_duplicate_entry_anchors(tmp_domain_rich, tmp_path):
    """For each target state, all incoming edges have unique (entryX, entryY) pairs."""
    render_to_drawio_state(tmp_domain_rich, "Pump")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain_rich}-Pump.drawio"
    from lxml import etree
    root = etree.fromstring(drawio_path.read_bytes())
    target_to_entries = {}
    for el in root.iter("mxCell"):
        if el.get("edge") != "1":
            continue
        target = el.get("target")
        if not target or ":state:" not in target or "__initial__" in target:
            continue
        style = el.get("style", "")
        ports = _extract_ports(style)
        if "entryX" not in ports or "entryY" not in ports:
            continue
        key = (ports["entryX"], ports["entryY"])
        target_to_entries.setdefault(target, []).append(key)
    for target, keys in target_to_entries.items():
        assert len(keys) == len(set(keys)), (
            f"Target {target} has duplicate entry anchors: {keys}"
        )


def test_all_transitions_have_edge_cells(tmp_domain_rich, tmp_path):
    """Count of domain:trans:* cells matches len(sd.transitions)."""
    import yaml as _yaml
    render_to_drawio_state(tmp_domain_rich, "Pump")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain_rich}-Pump.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    trans_cells = [k for k in cells if ":trans:" in k and "__initial__" not in k]
    yaml_path = tmp_path / ".design" / "model" / tmp_domain_rich / "state-diagrams" / "Pump.yaml"
    sd_data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert len(trans_cells) == len(sd_data["transitions"]), (
        f"Expected {len(sd_data['transitions'])} transition cells, got {len(trans_cells)}"
    )


def test_self_referential_association_has_corner_anchors(tmp_path, monkeypatch):
    """A self-referential association (point_1 == point_2) gets exit/entry on adjacent sides."""
    domain_root = tmp_path / ".design" / "model" / "testcd"
    domain_root.mkdir(parents=True)
    import yaml as _yaml
    cd = {
        "schema_version": "1.0.0",
        "domain": "testcd",
        "classes": [
            {
                "name": "Node",
                "stereotype": "entity",
                "attributes": [],
                "methods": [],
            }
        ],
        "associations": [
            {
                "name": "R1",
                "point_1": "Node",
                "point_2": "Node",
                "1_mult_2": "1",
                "2_mult_1": "M",
                "1_phrase_2": "contains",
                "2_phrase_1": "is contained by",
            }
        ],
        "bridges": [],
    }
    (domain_root / "class-diagram.yaml").write_text(
        _yaml.dump(cd), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    render_to_drawio_class("testcd")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / "testcd-class-diagram.drawio"
    from lxml import etree
    root = etree.fromstring(drawio_path.read_bytes())
    self_assoc = [
        el for el in root.iter("mxCell")
        if el.get("edge") == "1"
        and el.get("source") == el.get("target")
        and el.get("source") is not None
    ]
    assert self_assoc, "No self-referential association edge found"
    for el in self_assoc:
        style = el.get("style", "")
        ports = _extract_ports(style)
        assert "exitX" in ports and "exitY" in ports, f"Self-assoc missing exit ports: {style}"
        assert "entryX" in ports and "entryY" in ports, f"Self-assoc missing entry ports: {style}"
        assert (ports["exitX"], ports["exitY"]) != (ports["entryX"], ports["entryY"]), \
            f"Self-assoc exit == entry: {ports}"
        # Must have an exterior waypoint to force routing outside the box
        geo = el.find("mxGeometry")
        assert geo is not None
        arr = geo.find("Array")
        assert arr is not None, "Self-assoc missing mxGeometry/Array waypoints"
        pts = arr.findall("mxPoint")
        assert len(pts) == 3, "Self-assoc Array has no mxPoint waypoints"


def test_association_edges_have_no_arrows(tmp_domain, tmp_path):
    """Association edge styles must not render arrowheads (endArrow=none, startArrow=none)."""
    render_to_drawio_class(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-class-diagram.drawio"
    from lxml import etree
    root = etree.fromstring(drawio_path.read_bytes())
    assoc_cells = [
        el for el in root.iter("mxCell")
        if el.get("edge") == "1" and ":assoc:" in (el.get("id") or "")
        and ":assoc_mult:" not in (el.get("id") or "")
    ]
    assert assoc_cells, "No association edge cells found"
    for el in assoc_cells:
        style = el.get("style", "")
        assert "endArrow=none" in style, f"Association {el.get('id')} missing endArrow=none: {style}"
        assert "startArrow=none" in style, f"Association {el.get('id')} missing startArrow=none: {style}"


def test_self_loop_has_orthogonal_anchors(tmp_path, monkeypatch):
    """A self-loop transition has exit and entry on two different sides (not the same point)."""
    domain_root = tmp_path / ".design" / "model" / "testdomain"
    domain_root.mkdir(parents=True)
    (domain_root / "state-diagrams").mkdir()
    import yaml as _yaml
    sd = {
        "schema_version": "1.0.0",
        "domain": "testdomain",
        "class": "Widget",
        "initial_state": "Active",
        "states": [{"name": "Active"}],
        "events": [{"name": "Refresh"}],
        "transitions": [{"from": "Active", "to": "Active", "event": "Refresh"}],
    }
    (domain_root / "state-diagrams" / "Widget.yaml").write_text(
        _yaml.dump(sd), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    render_to_drawio_state("testdomain", "Widget")
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / "testdomain-Widget.drawio"
    from lxml import etree
    root = etree.fromstring(drawio_path.read_bytes())
    self_loops = [
        el for el in root.iter("mxCell")
        if el.get("source") == el.get("target") and el.get("source") is not None
        and el.get("edge") == "1" and "__init__" not in (el.get("id") or "")
    ]
    assert self_loops, "No self-loop edge found"
    for el in self_loops:
        style = el.get("style", "")
        ports = _extract_ports(style)
        assert "exitX" in ports and "exitY" in ports, f"Self-loop missing exit ports: {style}"
        assert "entryX" in ports and "entryY" in ports, f"Self-loop missing entry ports: {style}"
        # Exit and entry must differ (not the same attachment point)
        assert (ports["exitX"], ports["exitY"]) != (ports["entryX"], ports["entryY"]), \
            f"Self-loop exit == entry: {ports}"
        # Must have an exterior waypoint to force routing outside the box
        geo = el.find("mxGeometry")
        assert geo is not None
        arr = geo.find("Array")
        assert arr is not None, "Self-loop missing mxGeometry/Array waypoints"
        pts = arr.findall("mxPoint")
        assert len(pts) == 3, "Self-loop Array has no mxPoint waypoints"


def test_association_multiplicity_labels(tmp_domain, tmp_path):
    """Multiplicity label cells exist with correct values for R1."""
    render_to_drawio_class(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-class-diagram.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    src_cell = cells.get("hydraulics:assoc_mult:R1:src_mult")
    tgt_cell = cells.get("hydraulics:assoc_mult:R1:tgt_mult")
    assert src_cell is not None, "hydraulics:assoc_mult:R1:src_mult cell not found"
    assert tgt_cell is not None, "hydraulics:assoc_mult:R1:tgt_mult cell not found"
    assert src_cell.get("value") == "M", f"src_mult value={src_cell.get('value')!r}, expected 'M'"
    assert tgt_cell.get("value") == "1", f"tgt_mult value={tgt_cell.get('value')!r}, expected '1'"


def test_association_edge_has_verb_phrases(tmp_domain, tmp_path):
    """R1 verb phrases appear in the endpoint phrase cells, not the center edge label."""
    render_to_drawio_class(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / "diagrams" / f"{tmp_domain}-class-diagram.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    # Center edge label should be just the R-number
    r1_cell = cells.get("hydraulics:assoc:R1")
    assert r1_cell is not None, "R1 association cell not found"
    assert r1_cell.get("value") == "R1", f"Center label should be 'R1', got {r1_cell.get('value')!r}"
    # Verb phrases live in the phrase cells
    src_phrase = cells.get("hydraulics:assoc_mult:R1:src_phrase")
    tgt_phrase = cells.get("hydraulics:assoc_mult:R1:tgt_phrase")
    assert src_phrase is not None, "hydraulics:assoc_mult:R1:src_phrase cell not found"
    assert "is driven by" in src_phrase.get("value", "").replace("\n", " "), \
        f"src_phrase {src_phrase.get('value')!r} missing 'is driven by'"
    assert tgt_phrase is not None, "hydraulics:assoc_mult:R1:tgt_phrase cell not found"
    assert "drives" in tgt_phrase.get("value", "").replace("\n", " "), \
        f"tgt_phrase {tgt_phrase.get('value')!r} missing 'drives'"


def test_sync_unrecognized_cell(tmp_domain, tmp_path):
    """MCP-07: Sync with an unrecognized style returns an 'unrecognized' issue without aborting."""
    xml = (
        b'<?xml version="1.0"?>'
        b'<mxfile compressed="false" version="24.0.0">'
        b'<diagram name="Page-1" id="page1">'
        b'<mxGraphModel><root>'
        b'<mxCell id="0"/>'
        b'<mxCell id="1" parent="0"/>'
        b'<mxCell id="unknown1" value="?" style="unknownStyle;" vertex="1" parent="1">'
        b'<mxGeometry x="0" y="0" width="60" height="40" as="geometry"/></mxCell>'
        b'</root></mxGraphModel></diagram></mxfile>'
    )
    issues = sync_from_drawio("hydraulics", "Pump", xml)
    pump_yaml_path = tmp_path / ".design" / "model" / "hydraulics" / "state-diagrams" / "Pump.yaml"
    assert pump_yaml_path.exists(), "Pump.yaml was deleted — sync should not abort"
    unrecognized = [
        i for i in (issues or [])
        if "unrecognized" in str(i.get("issue", "")).lower()
    ]
    assert len(unrecognized) >= 1, (
        f"Expected at least one 'unrecognized' issue, got: {issues}"
    )


# ---------------------------------------------------------------------------
# Unit tests for _remove_overlaps and _route_edges_around_boxes
# ---------------------------------------------------------------------------

def _boxes_overlap(pos, widths, heights, gap=0):
    """Return True if any pair of boxes overlaps (with optional gap)."""
    n = len(pos)
    for i in range(n):
        for j in range(i + 1, n):
            cx_i = pos[i][0] + widths[i] / 2
            cy_i = pos[i][1] + heights[i] / 2
            cx_j = pos[j][0] + widths[j] / 2
            cy_j = pos[j][1] + heights[j] / 2
            half_w = (widths[i] + widths[j]) / 2 + gap
            half_h = (heights[i] + heights[j]) / 2 + gap
            if abs(cx_j - cx_i) < half_w and abs(cy_j - cy_i) < half_h:
                return True
    return False


@pytest.mark.skipif(_remove_overlaps is None, reason="tools.drawio not importable")
def test_remove_overlaps_clears_all_pairs():
    """Two overlapping boxes are pushed apart so no overlap remains."""
    positions = [(0.0, 0.0), (10.0, 0.0)]   # heavily overlapping
    widths  = [100, 100]
    heights = [50,  50]
    result = _remove_overlaps(positions, widths, heights, gap=10)
    assert not _boxes_overlap(result, widths, heights, gap=10), (
        f"Boxes still overlap after _remove_overlaps: {result}"
    )


@pytest.mark.skipif(_remove_overlaps is None, reason="tools.drawio not importable")
def test_remove_overlaps_single_node_noop():
    """Single node is translated to (MARGIN, MARGIN) with no error."""
    result = _remove_overlaps([(500.0, 300.0)], [100], [50])
    assert len(result) == 1
    assert result[0] == (float(MARGIN), float(MARGIN))


@pytest.mark.skipif(_remove_overlaps is None, reason="tools.drawio not importable")
def test_remove_overlaps_coincident_nodes():
    """Two nodes at the exact same position are pushed apart (no overlap)."""
    positions = [(200.0, 200.0), (200.0, 200.0)]
    widths  = [80, 80]
    heights = [40, 40]
    result = _remove_overlaps(positions, widths, heights, gap=10)
    assert not _boxes_overlap(result, widths, heights, gap=10), (
        f"Coincident boxes still overlap after _remove_overlaps: {result}"
    )


@pytest.mark.skipif(_route_edges_around_boxes is None, reason="tools.drawio not importable")
def test_route_edges_no_blocker():
    """Triangle layout: edge between two outer nodes with no blocker → empty waypoints."""
    # Three nodes: A at (0,0), B at (300,0), C at (0,300) — well separated
    positions = [(120.0, 120.0), (500.0, 120.0), (120.0, 500.0)]
    widths    = [100, 100, 100]
    heights   = [50,  50,  50]
    edges = [(0, 1)]   # A→B; C is not on the straight path
    port_suffixes = ["exitX=1.0;exitY=0.5;exitDx=0;exitDy=0;entryX=0.0;entryY=0.5;entryDx=0;entryDy=0;"]
    result = _route_edges_around_boxes(edges, positions, widths, heights, port_suffixes, gap=10)
    assert len(result) == 1
    assert result[0] == [], f"Expected no waypoints for unblocked edge, got: {result[0]}"


@pytest.mark.skipif(_route_edges_around_boxes is None, reason="tools.drawio not importable")
def test_route_edges_blocked():
    """Node B sits directly between A and C: edge A→C gets one waypoint not inside B's AABB."""
    # A at x=120, C at x=700, B halfway at x=410 — all on same y-row
    W, H = 100, 50
    gap = 10
    positions = [(120.0, 200.0), (410.0, 200.0), (700.0, 200.0)]
    widths    = [W, W, W]
    heights   = [H, H, H]
    edges = [(0, 2)]   # A→C, B is in between
    port_suffixes = ["exitX=1.0;exitY=0.5;exitDx=0;exitDy=0;entryX=0.0;entryY=0.5;entryDx=0;entryDy=0;"]
    result = _route_edges_around_boxes(edges, positions, widths, heights, port_suffixes, gap=gap)
    assert len(result) == 1
    wps = result[0]
    assert len(wps) == 1, f"Expected exactly one waypoint for blocked edge, got: {wps}"
    wx, wy = wps[0]
    # Waypoint must NOT be inside B's expanded AABB
    bx0, by0 = positions[1][0] - gap, positions[1][1] - gap
    bx1, by1 = positions[1][0] + W + gap, positions[1][1] + H + gap
    inside_b = bx0 <= wx <= bx1 and by0 <= wy <= by1
    assert not inside_b, f"Waypoint {wps[0]} is still inside blocker B's expanded AABB"


# ---------------------------------------------------------------------------
# Unit tests for routing geometry helpers
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_anchor_point is None, reason="tools.drawio not importable")
def test_anchor_point_all_sides():
    """_anchor_point returns the correct pixel coordinate for each side at t=0.5."""
    positions = [(100.0, 200.0)]
    widths  = [80]
    heights = [60]
    assert _anchor_point(0, "top",    0.5, positions, widths, heights) == (140.0, 200.0)
    assert _anchor_point(0, "bottom", 0.5, positions, widths, heights) == (140.0, 260.0)
    assert _anchor_point(0, "left",   0.5, positions, widths, heights) == (100.0, 230.0)
    assert _anchor_point(0, "right",  0.5, positions, widths, heights) == (180.0, 230.0)


@pytest.mark.skipif(_segments_intersect is None, reason="tools.drawio not importable")
def test_segments_intersect_crossing():
    """Two segments that form a classic X shape are detected as crossing."""
    assert _segments_intersect((0.0, 0.0), (2.0, 2.0), (2.0, 0.0), (0.0, 2.0))


@pytest.mark.skipif(_segments_intersect is None, reason="tools.drawio not importable")
def test_segments_intersect_parallel_no_crossing():
    """Two parallel horizontal segments do not intersect."""
    assert not _segments_intersect((0.0, 0.0), (2.0, 0.0), (0.0, 1.0), (2.0, 1.0))


@pytest.mark.skipif(_segments_intersect is None, reason="tools.drawio not importable")
def test_segments_intersect_shared_endpoint_no_crossing():
    """Two segments that meet at a shared endpoint are not counted as a proper crossing.

    This matters for edge-crossing scoring: a shared endpoint (T-junction or elbow)
    should not inflate the crossing count and bias the optimizer toward longer routes.
    """
    # p1→p2 and p3→p4 share the point (1, 1)
    assert not _segments_intersect((0.0, 0.0), (1.0, 1.0), (1.0, 1.0), (2.0, 0.0))


@pytest.mark.skipif(_route_path is None, reason="tools.drawio not importable")
def test_route_path_clear_no_waypoints():
    """Path between two nodes with no blocker in the corridor → 0 crossings, no waypoints."""
    # A at (0,0) w=40 h=40, B at (300,0) w=40 h=40, C at (0,300) — well off to the side
    positions = [(0.0, 0.0), (300.0, 0.0), (0.0, 300.0)]
    widths  = [40, 40, 40]
    heights = [40, 40, 40]
    # Path runs right across the top; C is far below
    wps, crossings = _route_path(40.0, 20.0, 300.0, 20.0, 0, 1, positions, widths, heights, gap=10)
    assert crossings == 0, f"Expected 0 box crossings, got {crossings}"
    assert wps == [], f"Expected no waypoints, got {wps}"


@pytest.mark.skipif(_route_path is None, reason="tools.drawio not importable")
def test_route_path_blocker_returns_waypoint_and_crossing_count():
    """Path crossing a third box: 1 crossing reported and one avoidance waypoint placed."""
    # A at (0,0), B at (400,0), blocker at (160,−5) spanning x=[160,240] y=[−5,45]
    # Direct horizontal path at y=20 passes through the blocker
    positions = [(0.0, 0.0), (400.0, 0.0), (160.0, -5.0)]
    widths  = [40, 40, 80]
    heights = [40, 40, 50]
    ax, ay = 40.0, 20.0    # right edge of A at its vertical centre
    bx, by = 400.0, 20.0   # left edge of B at its vertical centre
    wps, crossings = _route_path(ax, ay, bx, by, 0, 1, positions, widths, heights, gap=10)
    assert crossings == 1, f"Expected 1 box crossing, got {crossings}"
    assert len(wps) == 1, f"Expected 1 avoidance waypoint, got {wps}"
    wx, wy = wps[0]
    # Waypoint must not be inside the blocker's bounding box (with gap)
    bx0 = positions[2][0] - 10
    bx1 = positions[2][0] + widths[2] + 10
    by0 = positions[2][1] - 10
    by1 = positions[2][1] + heights[2] + 10
    assert not (bx0 <= wx <= bx1 and by0 <= wy <= by1), (
        f"Avoidance waypoint {wps[0]} is still inside the blocker AABB"
    )


# ---------------------------------------------------------------------------
# Unit tests for _optimize_edge_routing
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_optimize_edge_routing is None, reason="tools.drawio not importable")
def test_optimize_routing_avoids_box_via_side_selection():
    """Optimizer picks top/top over right/left when the horizontal corridor is blocked.

    Layout (y increases downward):

        src (0,100) 40×40 ·········· [blocker (90,110) 80×40] ·········· tgt (200,100) 40×40

    The direct horizontal path (right-exit at y=120, left-entry at y=120) passes
    through the blocker [y=110..150].  The top path (exit top of src at y=100,
    enter top of tgt at y=100) clears the blocker which starts at y=110.

    The old direction heuristic would have chosen right/left unconditionally
    (dx=200 > dy=0).  The optimizer must score box_crossings × W_BOX and
    prefer the clear top/top path.
    """
    edges = [(0, 1)]
    positions = [(0.0, 100.0), (200.0, 100.0), (90.0, 110.0)]  # vertex 2 = blocker
    widths  = [40, 40, 80]
    heights = [40, 40, 40]
    suffixes, waypoints = _optimize_edge_routing(edges, positions, widths, heights, gap=5)
    ports = {k: float(v) for k, v in _extract_ports(suffixes[0]).items()}
    assert ports.get("exitY") == pytest.approx(0.0), (
        f"Expected top exit (exitY=0.0) to avoid blocker, got exitY={ports.get('exitY')}"
    )
    assert ports.get("entryY") == pytest.approx(0.0), (
        f"Expected top entry (entryY=0.0) to avoid blocker, got entryY={ports.get('entryY')}"
    )
    assert waypoints[0] == [], (
        f"Top path is clear — expected no waypoints, got {waypoints[0]}"
    )
