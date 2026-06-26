"""Tests for drawio_schema.py — SCHEMA-03 (bijection table complete and correct)."""
from schema.drawio_schema import (
    BIJECTION_TABLE,
    STYLE_CLASS, STYLE_ATTRIBUTE, STYLE_SEPARATOR, STYLE_ASSOCIATION, STYLE_ASSOC_LABEL,
    STYLE_STATE, STYLE_INITIAL_PSEUDO, STYLE_TRANSITION, STYLE_BRIDGE,
    STYLE_IMPL_BOX,
    class_id, attribute_id, separator_id, association_id, state_id, transition_id,
    bridge_impl_id, method_box_id,
)

REQUIRED_ELEMENT_TYPES = {
    "class", "class_active", "attribute", "separator", "association", "assoc_label",
    "generalization", "state", "initial_pseudo", "transition", "bridge", "bridge_impl", "method_box",
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



# Task 1: Implementation box and method box styles and IDs

def test_style_impl_box_nonempty():
    assert STYLE_IMPL_BOX
    assert "Courier New" in STYLE_IMPL_BOX
    assert "f5f5f5" in STYLE_IMPL_BOX

def test_bridge_impl_id():
    assert bridge_impl_id("Elevator", "Transport", "ElevatorDetected") == \
        "elevator:bridge_impl:Transport:ElevatorDetected"

def test_method_box_id():
    assert method_box_id("Elevator", "Elevator", "_get_lit_buttons") == \
        "elevator:method:Elevator:_get_lit_buttons"

def test_bijection_table_has_impl_keys():
    assert "bridge_impl" in BIJECTION_TABLE
    assert "method_box" in BIJECTION_TABLE
