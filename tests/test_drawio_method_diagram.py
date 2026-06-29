# tests/test_drawio_method_diagram.py
"""Tests for render_to_drawio_methods and the method-only diagram edge case.

Covers:
- Entity class with action-bearing methods → method diagram generated
- Method diagram contains correct cell IDs and content
- Change detection (skipped when unchanged, rewritten when action changes)
- Method diagram included in render_to_drawio orchestrator output
- Active class with a state diagram does NOT get a redundant method diagram
- Classes with no action-bearing methods do NOT get a method diagram
"""
import pytest
import yaml
from pathlib import Path
from lxml import etree

import tools.drawio as dw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_domain(tmp_path: Path, classes: list[dict]) -> Path:
    """Write a minimal domain under tmp_path and return domain root."""
    domain_root = tmp_path / "Test"
    domain_root.mkdir(parents=True, exist_ok=True)
    (domain_root / "state-diagrams").mkdir(exist_ok=True)
    (tmp_path / "diagrams").mkdir(exist_ok=True)
    content = {
        "schema_version": "1.0.0",
        "domain": "Test",
        "classes": classes,
        "associations": [],
        "bridges": [],
    }
    (domain_root / "class-diagram.yaml").write_text(
        yaml.dump(content, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return domain_root


def _write_state_diagram(domain_root: Path, class_name: str) -> None:
    content = {
        "schema_version": "1.0.0",
        "domain": "Test",
        "class": class_name,
        "initial_state": "Idle",
        "states": [{"name": "Idle"}],
        "transitions": [],
    }
    (domain_root / "state-diagrams" / f"{class_name}.yaml").write_text(
        yaml.dump(content, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def _render_methods(tmp_path: Path, class_name: str = "Widget", *, force: bool = True) -> list[dict]:
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        return dw.render_to_drawio_methods("Test", class_name, force=force)
    finally:
        dw.MODEL_ROOT = orig


def _render_all(tmp_path: Path, *, force: bool = True) -> list[dict]:
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        return dw.render_to_drawio("Test", force=force)
    finally:
        dw.MODEL_ROOT = orig


def _method_diagram_path(tmp_path: Path, class_name: str) -> Path:
    return tmp_path / "diagrams" / f"Test-{class_name}-methods.drawio"


# ---------------------------------------------------------------------------
# render_to_drawio_methods — direct invocation
# ---------------------------------------------------------------------------

def test_method_diagram_written_for_entity_with_action(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [{"name": "n", "type": "Integer"}], "return": "Integer",
                 "action": "return n * 2;"},
            ],
        },
    ])
    results = _render_methods(tmp_path)
    assert results[0]["status"] == "written"
    assert _method_diagram_path(tmp_path, "Widget").exists()


def test_method_diagram_cell_ids_correct(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 42;"},
            ],
        },
    ])
    _render_methods(tmp_path)
    xml = _method_diagram_path(tmp_path, "Widget").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Widget:compute" in ids


def test_method_diagram_cell_contains_signature_and_body(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "add", "visibility": "public", "scope": "instance",
                 "params": [{"name": "x", "type": "Integer"}, {"name": "y", "type": "Integer"}],
                 "return": "Integer",
                 "action": "return x + y;"},
            ],
        },
    ])
    _render_methods(tmp_path)
    xml = _method_diagram_path(tmp_path, "Widget").read_bytes()
    tree = etree.fromstring(xml)
    for el in tree.iter("mxCell"):
        if el.get("id") == "test:method:Widget:add":
            value = el.get("value", "")
            assert "add" in value
            assert "x: Integer" in value
            assert "y: Integer" in value
            assert "Integer" in value
            assert "return x + y;" in value
            break
    else:
        pytest.fail("method cell not found in method diagram")


def test_method_diagram_multiple_methods_all_appear(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Calculator",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "add", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 1;"},
                {"name": "subtract", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 2;"},
            ],
        },
    ])
    _render_methods(tmp_path, "Calculator")
    xml = _method_diagram_path(tmp_path, "Calculator").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Calculator:add" in ids
    assert "test:method:Calculator:subtract" in ids


def test_method_diagram_only_methods_with_action_rendered(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "withAction", "visibility": "public", "scope": "instance",
                 "params": [], "action": "do_something();"},
                {"name": "noAction", "visibility": "public", "scope": "instance",
                 "params": []},
            ],
        },
    ])
    _render_methods(tmp_path)
    xml = _method_diagram_path(tmp_path, "Widget").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Widget:withAction" in ids
    assert "test:method:Widget:noAction" not in ids


def test_method_diagram_skipped_when_unchanged(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 1;"},
            ],
        },
    ])
    r1 = _render_methods(tmp_path)
    assert r1[0]["status"] == "written"
    r2 = _render_methods(tmp_path, force=False)
    assert r2[0]["status"] == "skipped"


def test_method_diagram_rewritten_when_action_changes(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 1;"},
            ],
        },
    ])
    _render_methods(tmp_path)
    xml_v1 = _method_diagram_path(tmp_path, "Widget").read_bytes()

    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 99;"},
            ],
        },
    ])
    _render_methods(tmp_path, force=False)
    xml_v2 = _method_diagram_path(tmp_path, "Widget").read_bytes()
    assert xml_v1 != xml_v2


def test_method_diagram_error_when_class_not_found(tmp_path):
    _setup_domain(tmp_path, [
        {"name": "Widget", "stereotype": "entity", "attributes": [], "methods": []},
    ])
    results = _render_methods(tmp_path, class_name="NonExistent")
    assert any(r.get("severity") == "error" for r in results)


def test_method_diagram_error_when_no_action_methods(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "sig_only", "visibility": "public", "scope": "instance", "params": []},
            ],
        },
    ])
    results = _render_methods(tmp_path)
    assert any(r.get("severity") == "error" for r in results)


# ---------------------------------------------------------------------------
# render_to_drawio orchestrator — method diagram integration
# ---------------------------------------------------------------------------

def test_orchestrator_emits_method_diagram_for_entity_with_action(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 1;"},
            ],
        },
    ])
    results = _render_all(tmp_path)
    files = [r.get("file", "") for r in results if isinstance(r, dict) and "file" in r]
    assert any("Widget-methods" in f for f in files)
    assert _method_diagram_path(tmp_path, "Widget").exists()


def test_orchestrator_no_method_diagram_for_active_class_with_state_diagram(tmp_path):
    domain_root = _setup_domain(tmp_path, [
        {
            "name": "Pump",
            "stereotype": "active",
            "attributes": [],
            "methods": [
                {"name": "compute", "visibility": "public", "scope": "instance",
                 "params": [], "action": "return 1;"},
            ],
        },
    ])
    _write_state_diagram(domain_root, "Pump")
    results = _render_all(tmp_path)
    files = [r.get("file", "") for r in results if isinstance(r, dict) and "file" in r]
    assert not any("Pump-methods" in f for f in files)


def test_orchestrator_no_method_diagram_when_no_action_methods(tmp_path):
    _setup_domain(tmp_path, [
        {
            "name": "Widget",
            "stereotype": "entity",
            "attributes": [],
            "methods": [
                {"name": "sig_only", "visibility": "public", "scope": "instance", "params": []},
            ],
        },
    ])
    results = _render_all(tmp_path)
    files = [r.get("file", "") for r in results if isinstance(r, dict) and "file" in r]
    assert not any("Widget-methods" in f for f in files)


def test_orchestrator_no_method_diagram_when_class_has_no_methods(tmp_path):
    _setup_domain(tmp_path, [
        {"name": "Widget", "stereotype": "entity", "attributes": [], "methods": []},
    ])
    results = _render_all(tmp_path)
    files = [r.get("file", "") for r in results if isinstance(r, dict) and "file" in r]
    assert not any("Widget-methods" in f for f in files)
