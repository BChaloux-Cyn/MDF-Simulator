"""Tests for __terminal__ pseudostate validation and rendering."""
import yaml
import pytest
from pathlib import Path
from schema.yaml_schema import StateDiagramFile
from tools import validation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sd(transitions_extra: list[dict]) -> StateDiagramFile:
    """Minimal state diagram with Active and Closing states, plus extra transitions."""
    data = {
        "schema_version": "1.0.0",
        "domain": "Terminal",
        "class": "Widget",
        "initial_state": "Active",
        "events": [
            {"name": "Shutdown"},
            {"name": "Done"},
            {"name": "Bad"},
        ],
        "states": [
            {"name": "Active"},
            {"name": "Closing"},
        ],
        "transitions": [
            {"from": "Active", "to": "Closing", "event": "Shutdown"},
        ] + transitions_extra,
    }
    return StateDiagramFile(**data)


def _issues(sd: StateDiagramFile) -> list[dict]:
    """Run full validation and return all issues."""
    import importlib, sys
    # Patch the model root so validate_domain can find our in-memory object
    # instead, call the internal checkers directly
    from tools.validation import (
        _check_referential_integrity_state_diagram,
        _check_reachability,
    )
    return (
        _check_referential_integrity_state_diagram(sd, "Terminal")
        + _check_reachability(sd, "Terminal")
    )


# ---------------------------------------------------------------------------
# Validation: pseudostate routing guards
# ---------------------------------------------------------------------------

def test_from_terminal_is_validation_error():
    sd = _make_sd([{"from": "__terminal__", "to": "Active", "event": "Bad"}])
    issues = _issues(sd)
    assert any("__terminal__" in i["issue"] and "source" in i["issue"] for i in issues), \
        f"Expected '__terminal__ as source' error, got: {issues}"


def test_to_initial_is_validation_error():
    sd = _make_sd([{"from": "Closing", "to": "__initial__", "event": "Bad"}])
    issues = _issues(sd)
    assert any("__initial__" in i["issue"] for i in issues), \
        f"Expected '__initial__ as target' error, got: {issues}"


def test_to_terminal_is_not_a_validation_error():
    sd = _make_sd([{"from": "Closing", "to": "__terminal__", "event": "Done"}])
    issues = _issues(sd)
    ref_issues = [i for i in issues if "__terminal__" in i.get("issue", "") and "unknown" in i.get("issue", "")]
    assert not ref_issues, f"__terminal__ should be a valid transition target, got: {ref_issues}"


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------

from lxml import etree as lxml_etree
from schema.drawio_schema import STYLE_TERMINATE_PSEUDO, STYLE_STATE
from tools.drawio import INIT_SIZE, _build_state_diagram_xml

FIXTURE_YAML = Path(__file__).parent / "fixtures" / "terminal-state-diagram.yaml"
DOMAIN = "Terminal"
CLASS_NAME = "Widget"
TERM_CELL_ID = "terminal:state:Widget:__terminal__"


def _load_sd_fixture() -> StateDiagramFile:
    return StateDiagramFile(**yaml.safe_load(FIXTURE_YAML.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def terminal_diagram_xml() -> bytes:
    sd = _load_sd_fixture()
    return _build_state_diagram_xml(DOMAIN, sd)


def _cells_by_id(xml_bytes: bytes) -> dict:
    root = lxml_etree.fromstring(xml_bytes)
    return {el.get("id"): el for el in root.iter("mxCell") if el.get("id")}


def test_terminate_pseudostate_cell_present(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    assert TERM_CELL_ID in cells, f"Expected cell '{TERM_CELL_ID}' not found"


def test_terminate_pseudostate_uses_correct_style(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    cell = cells[TERM_CELL_ID]
    assert cell.get("style") == STYLE_TERMINATE_PSEUDO, (
        f"Expected STYLE_TERMINATE_PSEUDO, got: {cell.get('style')!r}"
    )


def test_terminate_pseudostate_is_20x20(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    geo = cells[TERM_CELL_ID].find("mxGeometry")
    assert geo is not None
    assert int(geo.get("width")) == INIT_SIZE, f"Expected width={INIT_SIZE}"
    assert int(geo.get("height")) == INIT_SIZE, f"Expected height={INIT_SIZE}"


def test_terminate_pseudostate_has_empty_value(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    assert cells[TERM_CELL_ID].get("value") == ""


def test_regular_states_still_use_state_style(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    for state_name in ("Active", "Closing"):
        cid = f"{DOMAIN.lower()}:state:{CLASS_NAME}:{state_name}"
        cell = cells.get(cid)
        assert cell is not None, f"State cell '{cid}' missing"
        assert cell.get("style") == STYLE_STATE, (
            f"{state_name} should use STYLE_STATE, got {cell.get('style')!r}"
        )


def test_transition_to_terminal_targets_pseudostate_cell(terminal_diagram_xml):
    root = lxml_etree.fromstring(terminal_diagram_xml)
    # Find the Closing --Done--> __terminal__ transition edge
    done_edges = [
        el for el in root.iter("mxCell")
        if el.get("edge") == "1"
        and ":trans:Widget:Closing:Done:" in (el.get("id") or "")
    ]
    assert done_edges, "No edge found for Closing --Done--> __terminal__"
    for edge in done_edges:
        assert edge.get("target") == TERM_CELL_ID, (
            f"Edge target should be '{TERM_CELL_ID}', got {edge.get('target')!r}"
        )


def test_no_terminal_transitions_no_terminal_cell():
    data = {
        "schema_version": "1.0.0",
        "domain": "Terminal",
        "class": "Widget",
        "initial_state": "Active",
        "events": [{"name": "Shutdown"}],
        "states": [{"name": "Active"}, {"name": "Closing"}],
        "transitions": [{"from": "Active", "to": "Closing", "event": "Shutdown"}],
    }
    sd = StateDiagramFile(**data)
    xml = _build_state_diagram_xml("Terminal", sd)
    cells = _cells_by_id(xml)
    assert TERM_CELL_ID not in cells, "No __terminal__ cell expected when no transitions target it"


def test_canonical_parse_skips_terminal_cell(tmp_path):
    """Round-trip: rendered terminal diagram → canonical parse excludes __terminal__."""
    import json
    from tools.drawio import _build_state_diagram_xml, _drawio_to_canonical_state

    sd = _load_sd_fixture()
    xml_bytes = _build_state_diagram_xml(DOMAIN, sd)

    # Write to temp file and parse back
    out_file = tmp_path / "terminal.drawio"
    out_file.write_bytes(xml_bytes)

    result = _drawio_to_canonical_state(out_file)
    assert result is not None, "_drawio_to_canonical_state returned None unexpectedly"
    data = json.loads(result)
    state_names = [s["name"] for s in data["states"]]
    assert "__terminal__" not in state_names, (
        f"__terminal__ should be excluded from canonical states, got: {state_names}"
    )
    # Real states are still present
    assert "Active" in state_names
    assert "Closing" in state_names
