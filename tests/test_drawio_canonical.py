"""Tests for schema/drawio_canonical.py — canonical JSON Pydantic models."""
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
