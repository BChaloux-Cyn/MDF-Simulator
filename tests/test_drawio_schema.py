"""Tests for drawio_schema.py — SCHEMA-03 (bijection table complete and correct)."""
from schema.drawio_schema import (
    BIJECTION_TABLE,
    STYLE_CLASS, STYLE_ATTRIBUTE, STYLE_SEPARATOR, STYLE_ASSOCIATION, STYLE_ASSOC_LABEL,
    STYLE_STATE, STYLE_INITIAL_PSEUDO, STYLE_TRANSITION, STYLE_BRIDGE,
    class_id, attribute_id, separator_id, association_id, state_id, transition_id,
)

REQUIRED_ELEMENT_TYPES = {
    "class", "class_active", "attribute", "separator", "association", "assoc_label",
    "generalization", "state", "initial_pseudo", "transition", "bridge",
}


def test_all_yaml_elements_have_style_constant():
    """SCHEMA-03: BIJECTION_TABLE covers every YAML element type."""
    assert BIJECTION_TABLE.keys() == REQUIRED_ELEMENT_TYPES


def test_style_constants_are_nonempty_strings():
    """SCHEMA-03: Every style constant is a non-empty string."""
    for element_type, style in BIJECTION_TABLE.items():
        assert isinstance(style, str), f"{element_type} style is not a string"
        assert len(style) > 0, f"{element_type} style is empty"


def test_class_id_is_deterministic():
    assert class_id("Hydraulics", "Valve") == "hydraulics:class:Valve"
    assert class_id("HYDRAULICS", "Valve") == "hydraulics:class:Valve"  # domain always lowercase


def test_attribute_id_is_deterministic():
    assert attribute_id("Hydraulics", "Valve", "valve_id") == "hydraulics:attr:Valve:valve_id"


def test_association_id_is_deterministic():
    assert association_id("Hydraulics", "R1") == "hydraulics:assoc:R1"


def test_state_id_is_deterministic():
    assert state_id("Hydraulics", "Valve", "Idle") == "hydraulics:state:Valve:Idle"


def test_transition_id_is_deterministic():
    result = transition_id("Hydraulics", "Valve", "Idle", "Open", 0)
    assert result == "hydraulics:trans:Valve:Idle:Open:0"
    # Index distinguishes multiple transitions on the same (from, event) pair
    result2 = transition_id("Hydraulics", "Valve", "Idle", "Open", 1)
    assert result2 == "hydraulics:trans:Valve:Idle:Open:1"
    assert result != result2
