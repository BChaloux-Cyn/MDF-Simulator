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
    )
except ImportError:
    render_to_drawio = None
    render_to_drawio_class = None
    render_to_drawio_state = None
    validate_drawio = None
    sync_from_drawio = None


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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "class-diagram.drawio"
    assert drawio_path.exists(), "class-diagram.drawio was not created"
    xml_bytes = drawio_path.read_bytes()
    assert b"Valve" in xml_bytes
    assert b"Pump" in xml_bytes


def test_render_idempotent(tmp_domain, tmp_path):
    """MCP-05: Calling render twice produces byte-identical XML."""
    render_to_drawio(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "class-diagram.drawio"
    first_bytes = drawio_path.read_bytes()
    render_to_drawio(tmp_domain)
    second_bytes = drawio_path.read_bytes()
    assert first_bytes == second_bytes, "Render output differs between calls (not idempotent)"


def test_render_skip_unchanged(tmp_domain, tmp_path):
    """MCP-05: Second render does not modify mtime (or reports status 'skipped')."""
    result1 = render_to_drawio(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "class-diagram.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain_rich / "state-diagrams" / "Pump.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain_rich / "state-diagrams" / "Pump.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    idle_cell = cells.get("hydraulics:state:Pump:Idle")
    assert idle_cell is not None, "Idle state cell not found"
    geo = idle_cell.find("mxGeometry")
    height = int(geo.get("height"))
    assert height == STATE_H, f"Idle state height {height} should equal STATE_H={STATE_H}"


def test_transition_label_has_xy_offset(tmp_domain, tmp_path):
    """Transition mxGeometry has non-zero x and y attributes for label offset."""
    render_to_drawio_state(tmp_domain, "Pump")
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "state-diagrams" / "Pump.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain_rich / "state-diagrams" / "Pump.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain_rich / "state-diagrams" / "Pump.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain_rich / "state-diagrams" / "Pump.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / "testcd" / "class-diagram.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "class-diagram.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / "testdomain" / "state-diagrams" / "Widget.drawio"
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
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "class-diagram.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    src_cell = cells.get("hydraulics:assoc_mult:R1:src")
    tgt_cell = cells.get("hydraulics:assoc_mult:R1:tgt")
    assert src_cell is not None, "hydraulics:assoc_mult:R1:src cell not found"
    assert tgt_cell is not None, "hydraulics:assoc_mult:R1:tgt cell not found"
    assert src_cell.get("value", "").startswith("M"), f"src label value={src_cell.get('value')!r}, expected to start with 'M'"
    assert tgt_cell.get("value", "").startswith("1"), f"tgt label value={tgt_cell.get('value')!r}, expected to start with '1'"


def test_association_edge_has_verb_phrases(tmp_domain, tmp_path):
    """R1 verb phrases appear in the endpoint label cells, not the center edge label."""
    render_to_drawio_class(tmp_domain)
    drawio_path = tmp_path / ".design" / "model" / tmp_domain / "class-diagram.drawio"
    cells = _cells_by_id(drawio_path.read_bytes())
    # Center edge label should be just the R-number
    r1_cell = cells.get("hydraulics:assoc:R1")
    assert r1_cell is not None, "R1 association cell not found"
    assert r1_cell.get("value") == "R1", f"Center label should be 'R1', got {r1_cell.get('value')!r}"
    # Verb phrases live in the endpoint labels
    src_cell = cells.get("hydraulics:assoc_mult:R1:src")
    tgt_cell = cells.get("hydraulics:assoc_mult:R1:tgt")
    assert src_cell is not None and "is driven by" in src_cell.get("value", ""), \
        f"src label {src_cell.get('value') if src_cell else 'missing'!r} missing 'is driven by'"
    assert tgt_cell is not None and "drives" in tgt_cell.get("value", ""), \
        f"tgt label {tgt_cell.get('value') if tgt_cell else 'missing'!r} missing 'drives'"


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
