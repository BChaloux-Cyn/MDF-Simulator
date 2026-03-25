"""Tests for schema/drawio_canonical.py — canonical JSON Pydantic models."""
import json
import os
import textwrap
from pathlib import Path

import pytest

from schema.drawio_canonical import (
    CanonicalState,
    CanonicalTransition,
    CanonicalStateDiagram,
    CanonicalClassEntry,
    CanonicalAssociation,
    CanonicalGeneralization,
    CanonicalClassDiagram,
)


# ---------------------------------------------------------------------------
# CanonicalStateDiagram serialization
# ---------------------------------------------------------------------------

def _make_state_diagram() -> CanonicalStateDiagram:
    return CanonicalStateDiagram(
        type="state_diagram",
        domain="Elevator",
        class_name="Car",
        initial_state="Idle",
        states=[
            CanonicalState(name="Idle", entry_action=None),
            CanonicalState(name="Moving", entry_action="move_car"),
        ],
        transitions=[
            CanonicalTransition(
                from_state="Idle",
                to="Moving",
                event="GoTo",
                params="floor: int",
                guard=None,
            ),
        ],
    )


def test_state_diagram_alias_from():
    """'from_state' field serializes as 'from' in JSON (by_alias=True)."""
    diagram = _make_state_diagram()
    data = diagram.model_dump(by_alias=True)
    trans = data["transitions"][0]
    assert "from" in trans
    assert "from_state" not in trans
    assert trans["from"] == "Idle"


def test_state_diagram_alias_class():
    """'class_name' field serializes as 'class' in JSON (by_alias=True)."""
    diagram = _make_state_diagram()
    data = diagram.model_dump(by_alias=True)
    assert "class" in data
    assert "class_name" not in data
    assert data["class"] == "Car"


def test_state_diagram_populate_by_name():
    """CanonicalStateDiagram and CanonicalTransition accept Python field names."""
    # Already constructed via Python names in _make_state_diagram; just confirm roundtrip.
    diagram = _make_state_diagram()
    assert diagram.class_name == "Car"
    assert diagram.transitions[0].from_state == "Idle"


def test_state_diagram_type_literal():
    data = _make_state_diagram().model_dump(by_alias=True)
    assert data["type"] == "state_diagram"


def test_state_diagram_none_fields_preserved():
    """None values for optional fields are included in the dump."""
    diagram = _make_state_diagram()
    data = diagram.model_dump(by_alias=True)
    assert data["transitions"][0]["guard"] is None
    assert data["states"][0]["entry_action"] is None


# ---------------------------------------------------------------------------
# CanonicalClassDiagram serialization
# ---------------------------------------------------------------------------

def _make_class_diagram() -> CanonicalClassDiagram:
    return CanonicalClassDiagram(
        type="class_diagram",
        domain="Elevator",
        classes=[
            CanonicalClassEntry(
                name="Car",
                stereotype="active",
                specializes=None,
                attributes=["car_id: int"],
                methods=["move_car"],
            ),
        ],
        associations=[
            CanonicalAssociation(
                name="R1",
                point_1="Car",
                point_2="Floor",
                mult_1_2="1",
                mult_2_1="1..*",
                phrase_1_2="visits",
                phrase_2_1="is visited by",
            ),
        ],
        generalizations=[
            CanonicalGeneralization(
                name="G1",
                supertype="Vehicle",
                subtypes=["Car", "Truck"],
            ),
        ],
    )


def test_class_diagram_alias_mult_1_2():
    """'mult_1_2' field serializes as '1_mult_2' in JSON (by_alias=True)."""
    diagram = _make_class_diagram()
    data = diagram.model_dump(by_alias=True)
    assoc = data["associations"][0]
    assert "1_mult_2" in assoc
    assert "mult_1_2" not in assoc
    assert assoc["1_mult_2"] == "1"


def test_class_diagram_alias_mult_2_1():
    """'mult_2_1' field serializes as '2_mult_1' in JSON (by_alias=True)."""
    diagram = _make_class_diagram()
    data = diagram.model_dump(by_alias=True)
    assoc = data["associations"][0]
    assert "2_mult_1" in assoc
    assert "mult_2_1" not in assoc
    assert assoc["2_mult_1"] == "1..*"


def test_class_diagram_alias_phrases():
    """Phrase fields serialize with numeric-prefixed aliases."""
    diagram = _make_class_diagram()
    data = diagram.model_dump(by_alias=True)
    assoc = data["associations"][0]
    assert "1_phrase_2" in assoc
    assert "2_phrase_1" in assoc
    assert "phrase_1_2" not in assoc
    assert "phrase_2_1" not in assoc


def test_class_diagram_populate_by_name():
    """CanonicalAssociation accepts Python field names (populate_by_name=True)."""
    diagram = _make_class_diagram()
    assert diagram.associations[0].mult_1_2 == "1"
    assert diagram.associations[0].mult_2_1 == "1..*"
    assert diagram.associations[0].phrase_1_2 == "visits"
    assert diagram.associations[0].phrase_2_1 == "is visited by"


def test_class_diagram_type_literal():
    data = _make_class_diagram().model_dump(by_alias=True)
    assert data["type"] == "class_diagram"


def test_class_entry_none_specializes():
    """specializes=None is preserved in the dump."""
    diagram = _make_class_diagram()
    data = diagram.model_dump(by_alias=True)
    assert data["classes"][0]["specializes"] is None


# ---------------------------------------------------------------------------
# _yaml_to_canonical_state and _drawio_to_canonical_state builder functions
# ---------------------------------------------------------------------------

def _make_state_diagram_file():
    """Return a StateDiagramFile with entry actions, params, and guards."""
    from schema.yaml_schema import StateDiagramFile, EventDef, EventParam, StateDef, Transition
    return StateDiagramFile(
        schema_version="1.0.0",
        domain="Elevator",
        class_name="Car",
        initial_state="Idle",
        events=[
            EventDef(name="GoTo", params=[EventParam(name="floor", type="int")]),
            EventDef(name="Arrive", params=[]),
        ],
        states=[
            StateDef(name="Moving", entry_action="move_car(floor)\nlog()"),
            StateDef(name="Idle", entry_action=None),
        ],
        transitions=[
            Transition(from_state="Moving", to="Idle", event="Arrive", guard=None),
            Transition(from_state="Idle", to="Moving", event="GoTo", guard="floor != current"),
        ],
    )


def test_yaml_to_canonical_state_basic():
    """_yaml_to_canonical_state builds correct canonical JSON from a StateDiagramFile."""
    from tools.drawio import _yaml_to_canonical_state
    sd = _make_state_diagram_file()
    result = _yaml_to_canonical_state("Elevator", sd)
    data = json.loads(result)

    # Top-level fields
    assert data["type"] == "state_diagram"
    assert data["domain"] == "Elevator"
    assert data["class"] == "Car"
    assert data["initial_state"] == "Idle"

    # States sorted by name: Idle < Moving
    assert [s["name"] for s in data["states"]] == ["Idle", "Moving"]
    assert data["states"][0]["entry_action"] is None
    assert data["states"][1]["entry_action"] == "move_car(floor)\nlog()"

    # Transitions sorted by (from_state, event, to)
    # (Idle, GoTo, Moving) < (Moving, Arrive, Idle)
    assert len(data["transitions"]) == 2
    t0 = data["transitions"][0]
    assert t0["from"] == "Idle"
    assert t0["to"] == "Moving"
    assert t0["event"] == "GoTo"
    assert t0["params"] == "floor: int"
    assert t0["guard"] == "floor != current"

    t1 = data["transitions"][1]
    assert t1["from"] == "Moving"
    assert t1["to"] == "Idle"
    assert t1["event"] == "Arrive"
    assert t1["params"] is None
    assert t1["guard"] is None

    # Deterministic: second call yields identical string
    assert _yaml_to_canonical_state("Elevator", sd) == result


def test_state_diagram_round_trip(tmp_path, monkeypatch):
    """Round-trip: render state diagram XML, parse it back, compare canonical JSON."""
    from tools.drawio import _yaml_to_canonical_state, _build_state_diagram_xml, _drawio_to_canonical_state

    sd = _make_state_diagram_file()
    xml_bytes = _build_state_diagram_xml("Elevator", sd)

    drawio_path = tmp_path / "elevator-Car.drawio"
    drawio_path.write_bytes(xml_bytes)

    yaml_canonical = _yaml_to_canonical_state("Elevator", sd)
    drawio_canonical = _drawio_to_canonical_state(drawio_path)

    assert drawio_canonical is not None, "Parser returned None for a valid drawio file"
    assert drawio_canonical == yaml_canonical, (
        f"Canonical mismatch.\nYAML side:\n{yaml_canonical}\nDrawio side:\n{drawio_canonical}"
    )


# ---------------------------------------------------------------------------
# _yaml_to_canonical_class and _drawio_to_canonical_class builder functions
# ---------------------------------------------------------------------------

from schema.yaml_schema import ClassDiagramFile


def _make_class_diagram_file() -> ClassDiagramFile:
    """Build a ClassDiagramFile with 4 classes, 1 regular association, 1 generalization."""
    data = {
        "schema_version": "1.0.0",
        "domain": "testdomain",
        "classes": [
            {
                "name": "Vehicle",
                "stereotype": "entity",
                "attributes": [
                    {"name": "vehicle_id", "type": "VehicleID", "visibility": "public", "scope": "instance", "identifier": True},
                ],
                "methods": [],
            },
            {
                "name": "Car",
                "stereotype": "entity",
                "specializes": "R10",
                "attributes": [
                    {"name": "doors", "type": "int", "visibility": "private", "scope": "instance"},
                ],
                "methods": [
                    {"name": "drive", "visibility": "public", "scope": "instance", "params": [], "return": None},
                ],
            },
            {
                "name": "Truck",
                "stereotype": "active",
                "specializes": "R10",
                "attributes": [],
                "methods": [],
            },
            {
                "name": "Fleet",
                "stereotype": "entity",
                "attributes": [
                    {"name": "fleet_id", "type": "FleetID", "visibility": "private", "scope": "instance"},
                ],
                "methods": [],
                "partitions": [
                    {"name": "R10", "subtypes": ["Truck", "Car"]},
                ],
            },
        ],
        "associations": [
            {
                "name": "R1",
                "point_1": "Fleet",
                "point_2": "Vehicle",
                "1_mult_2": "1",
                "2_mult_1": "1..*",
                "1_phrase_2": "contains",
                "2_phrase_1": "owns",
            },
            {
                "name": "R10",
                "point_1": "Vehicle",
                "point_2": "Car",
                "1_mult_2": "1",
                "2_mult_1": "1",
                "1_phrase_2": "",
                "2_phrase_1": "",
            },
        ],
        "bridges": [],
    }
    return ClassDiagramFile.model_validate(data)


def test_yaml_to_canonical_class_basic():
    """_yaml_to_canonical_class builds correct canonical JSON from ClassDiagramFile."""
    from tools.drawio import _yaml_to_canonical_class
    cd = _make_class_diagram_file()
    result = _yaml_to_canonical_class("testdomain", cd)
    data = json.loads(result)

    assert data["type"] == "class_diagram"
    assert data["domain"] == "testdomain"  # stored lowercase

    # Classes sorted by name: Car, Fleet, Truck, Vehicle
    class_names = [c["name"] for c in data["classes"]]
    assert class_names == sorted(class_names), "classes must be sorted by name"
    assert set(class_names) == {"Vehicle", "Car", "Truck", "Fleet"}

    # Verify attributes are label strings, not raw dicts
    vehicle_entry = next(c for c in data["classes"] if c["name"] == "Vehicle")
    assert len(vehicle_entry["attributes"]) == 1
    attr_label = vehicle_entry["attributes"][0]
    assert isinstance(attr_label, str)
    assert "vehicle_id" in attr_label
    assert "VehicleID" in attr_label
    # identifier tag should appear
    assert "I1" in attr_label

    # Verify methods are label strings
    car_entry = next(c for c in data["classes"] if c["name"] == "Car")
    assert len(car_entry["methods"]) == 1
    method_label = car_entry["methods"][0]
    assert isinstance(method_label, str)
    assert "drive" in method_label

    # specializes: Car and Truck have specializes, Vehicle/Fleet do not
    assert car_entry["specializes"] == "R10"
    truck_entry = next(c for c in data["classes"] if c["name"] == "Truck")
    assert truck_entry["specializes"] == "R10"
    fleet_entry = next(c for c in data["classes"] if c["name"] == "Fleet")
    assert fleet_entry["specializes"] is None

    # Associations: R10 is a generalization → must be excluded
    assoc_names = [a["name"] for a in data["associations"]]
    assert "R10" not in assoc_names
    assert "R1" in assoc_names
    assert assoc_names == sorted(assoc_names), "associations must be sorted by name"

    # Check association fields serialized with aliases
    r1 = data["associations"][0]
    assert r1["1_mult_2"] == "1"
    assert r1["2_mult_1"] == "1..*"
    assert r1["1_phrase_2"] == "contains"
    assert r1["2_phrase_1"] == "owns"

    # Generalizations: R10 extracted from Fleet's partitions
    gen_names = [g["name"] for g in data["generalizations"]]
    assert "R10" in gen_names
    assert gen_names == sorted(gen_names), "generalizations must be sorted by name"

    r10 = next(g for g in data["generalizations"] if g["name"] == "R10")
    assert r10["supertype"] == "Fleet"
    assert r10["subtypes"] == sorted(r10["subtypes"]), "subtypes must be sorted"
    assert set(r10["subtypes"]) == {"Car", "Truck"}

    # Deterministic: second call yields identical string
    assert _yaml_to_canonical_class("testdomain", cd) == result


def test_class_diagram_round_trip(tmp_path, monkeypatch):
    """Round-trip: render class diagram XML, parse it back, compare canonical JSON."""
    from tools.drawio import _yaml_to_canonical_class, _build_class_diagram_xml, _drawio_to_canonical_class

    diagrams_dir = tmp_path / ".design" / "model" / "diagrams"
    diagrams_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    cd = _make_class_diagram_file()

    # Render diagram to XML
    xml_bytes = _build_class_diagram_xml("testdomain", cd)
    drawio_path = diagrams_dir / "testdomain-class-diagram.drawio"
    drawio_path.write_bytes(xml_bytes)

    # Both sides must produce identical canonical JSON
    yaml_canonical = _yaml_to_canonical_class("testdomain", cd)
    drawio_canonical = _drawio_to_canonical_class(drawio_path)

    assert drawio_canonical is not None, "_drawio_to_canonical_class returned None"
    assert yaml_canonical == drawio_canonical, (
        f"Canonical mismatch.\n"
        f"YAML side:\n{json.dumps(json.loads(yaml_canonical), indent=2)}\n"
        f"Draw.io side:\n{json.dumps(json.loads(drawio_canonical), indent=2)}"
    )
