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

@pytest.mark.skip(reason="Implemented in plan 04-03")
def test_validate_drawio_valid(tmp_domain):
    """MCP-06: Canonical XML from render_sample_xml() produces no validation issues."""
    from schema.drawio_schema import render_sample_xml
    xml_bytes = render_sample_xml()
    issues = validate_drawio(tmp_domain, xml_bytes)
    errors = [i for i in issues if i.get("severity") == "error"]
    assert errors == [], f"Expected no errors on canonical XML, got: {errors}"


@pytest.mark.skip(reason="Implemented in plan 04-03")
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

@pytest.mark.skip(reason="Implemented in plan 04-03")
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


@pytest.mark.skip(reason="Implemented in plan 04-03")
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


@pytest.mark.skip(reason="Implemented in plan 04-03")
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


@pytest.mark.skip(reason="Implemented in plan 04-03")
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
