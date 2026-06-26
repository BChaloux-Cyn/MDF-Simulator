# tests/test_drawio_impl_boxes.py
import pytest
import yaml
from pathlib import Path
from lxml import etree

# ── helpers ──────────────────────────────────────────────────────────────────

def _write_domains(tmp_path: Path, ops: list[dict]) -> None:
    content = {
        "schema_version": "1.0.0",
        "domains": [
            {"name": "Test", "type": "application", "description": "d"},
            {"name": "Foo",  "type": "realized",    "description": "d"},
        ],
        "bridges": [{
            "from": "Foo",
            "to": "Test",
            "operations": ops,
        }],
    }
    (tmp_path / "DOMAINS.yaml").write_text(yaml.dump(content), encoding="utf-8")


def _write_class_diagram(tmp_path: Path, impls: list[dict]) -> None:
    (tmp_path / "Test").mkdir(exist_ok=True)
    content = {
        "schema_version": "1.0.0",
        "domain": "Test",
        "classes": [{"name": "Widget", "stereotype": "entity",
                      "attributes": [{"name": "id", "type": "UniqueID", "identifier": True}]}],
        "associations": [],
        "bridges": [{
            "to_domain": "Foo",
            "direction": "provided",
            "implementations": impls,
        }],
    }
    (tmp_path / "Test" / "class-diagram.yaml").write_text(yaml.dump(content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)


def _render_class(tmp_path: Path, domain: str = "Test") -> list[dict]:
    import importlib
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        return dw.render_to_drawio_class(domain, force=True)
    finally:
        dw.MODEL_ROOT = orig


# ── class diagram bridge impl tests ──────────────────────────────────────────

def test_bridge_impl_box_appears_in_xml(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": [{"name": "x", "type": "Integer"}], "return": "Boolean"}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "return x > 0;"}])
    results = _render_class(tmp_path)
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id") for el in tree.iter("mxCell")]
    assert "test:bridge_impl:Foo:DoThing" in ids

def test_bridge_impl_box_header_contains_signature(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": [{"name": "x", "type": "Integer"}], "return": "Boolean"}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "return x > 0;"}])
    _render_class(tmp_path)
    xml = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    tree = etree.fromstring(xml)
    for el in tree.iter("mxCell"):
        if el.get("id") == "test:bridge_impl:Foo:DoThing":
            value = el.get("value", "")
            assert "DoThing" in value
            assert "x: Integer" in value
            assert "Boolean" in value
            assert "return x &gt; 0;" in value
            break
    else:
        pytest.fail("bridge_impl cell not found")

def test_missing_domains_yaml_returns_error(tmp_path):
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    # No DOMAINS.yaml written
    results = _render_class(tmp_path)
    assert any(r.get("severity") == "error" for r in results)
    assert not (tmp_path / "diagrams" / "Test-class-diagram.drawio").exists()

def test_missing_operation_in_domains_returns_error(tmp_path):
    _write_domains(tmp_path, [{"name": "OtherOp", "params": []}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    results = _render_class(tmp_path)
    assert any(r.get("severity") == "error" for r in results)

def test_class_diagram_skip_when_unchanged(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": []}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    r1 = _render_class(tmp_path)
    assert r1[0]["status"] == "written"
    r2 = _render_class(tmp_path)  # second render without force
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        r2 = dw.render_to_drawio_class("Test")
    finally:
        dw.MODEL_ROOT = orig
    assert r2[0]["status"] == "skipped"

def test_class_diagram_rerenders_when_action_changes(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": []}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    _render_class(tmp_path)
    xml_v1 = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 2;"}])
    _render_class(tmp_path)
    xml_v2 = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    assert xml_v1 != xml_v2

def test_class_diagram_no_impl_box_when_no_provided_bridges(tmp_path):
    # Domain with no bridges at all — DOMAINS.yaml not required
    (tmp_path / "Test").mkdir(exist_ok=True)
    content = {
        "schema_version": "1.0.0", "domain": "Test",
        "classes": [{"name": "Widget", "stereotype": "entity",
                      "attributes": [{"name": "id", "type": "UniqueID", "identifier": True}]}],
        "associations": [], "bridges": [],
    }
    (tmp_path / "Test" / "class-diagram.yaml").write_text(yaml.dump(content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)
    results = _render_class(tmp_path)
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert not any("bridge_impl" in i for i in ids)


# ── state diagram method tests ────────────────────────────────────────────────

def _write_state_diagram(tmp_path: Path, class_name: str, methods: list[dict]) -> None:
    sd_dir = tmp_path / "Test" / "state-diagrams"
    sd_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "schema_version": "1.0.0",
        "domain": "Test",
        "class": class_name,
        "initial_state": "Idle",
        "states": [{"name": "Idle"}],
        "transitions": [],
    }
    (sd_dir / f"{class_name}.yaml").write_text(yaml.dump(content), encoding="utf-8")
    # Write class-diagram.yaml so methods can be loaded
    (tmp_path / "Test").mkdir(exist_ok=True)
    cd_content = {
        "schema_version": "1.0.0", "domain": "Test",
        "classes": [{"name": class_name, "stereotype": "active",
                      "attributes": [], "methods": methods}],
        "associations": [], "bridges": [],
    }
    (tmp_path / "Test" / "class-diagram.yaml").write_text(yaml.dump(cd_content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)


def _render_state(tmp_path: Path, class_name: str = "Widget") -> list[dict]:
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        return dw.render_to_drawio_state("Test", class_name, force=True)
    finally:
        dw.MODEL_ROOT = orig


def test_method_box_appears_in_state_diagram(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [{"name": "n", "type": "Integer"}], "return": "Boolean",
        "action": "return n > 0;",
    }])
    results = _render_state(tmp_path, "Widget")
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Widget:doWork" in ids

def test_method_box_header_and_body(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [{"name": "n", "type": "Integer"}], "return": "Boolean",
        "action": "return n > 0;",
    }])
    _render_state(tmp_path, "Widget")
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    for el in tree.iter("mxCell"):
        if el.get("id") == "test:method:Widget:doWork":
            value = el.get("value", "")
            assert "+ doWork" in value
            assert "n: Integer" in value
            assert "Boolean" in value
            assert "return n &gt; 0;" in value
            break
    else:
        pytest.fail("method cell not found")

def test_method_with_null_action_omitted(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 1;",
    }, {
        "name": "noAction", "visibility": "private", "scope": "instance",
    }])
    _render_state(tmp_path, "Widget")
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Widget:doWork" in ids
    assert "test:method:Widget:noAction" not in ids

def test_method_boxes_absent_when_no_class_diagram(tmp_path):
    # State diagram exists but no class-diagram.yaml
    sd_dir = tmp_path / "Test" / "state-diagrams"
    sd_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "schema_version": "1.0.0", "domain": "Test", "class": "Widget",
        "initial_state": "Idle", "states": [{"name": "Idle"}], "transitions": [],
    }
    (sd_dir / "Widget.yaml").write_text(yaml.dump(content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)
    results = _render_state(tmp_path, "Widget")
    # Should succeed — no error
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert not any("method" in i for i in ids)

def test_state_diagram_skip_when_unchanged(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 1;",
    }])
    _render_state(tmp_path, "Widget")
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        r2 = dw.render_to_drawio_state("Test", "Widget")
    finally:
        dw.MODEL_ROOT = orig
    assert r2[0]["status"] == "skipped"

def test_state_diagram_rerenders_when_method_action_changes(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 1;",
    }])
    _render_state(tmp_path, "Widget")
    xml_v1 = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 2;",
    }])
    _render_state(tmp_path, "Widget")
    xml_v2 = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    assert xml_v1 != xml_v2
