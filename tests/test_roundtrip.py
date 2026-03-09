"""Tests for Draw.io round-trip — SCHEMA-04."""
import defusedxml.ElementTree as DET
from schema.drawio_schema import (
    render_sample_xml, class_id, state_id, transition_id
)

DOMAIN = "Hydraulics"


def test_generated_xml_is_valid_xml():
    """SCHEMA-04: Generated XML is well-formed and parseable by defusedxml."""
    xml_bytes = render_sample_xml()
    assert isinstance(xml_bytes, bytes)
    assert len(xml_bytes) > 0
    root = DET.fromstring(xml_bytes)  # Raises if not well-formed
    assert root.tag == "mxfile"


def test_roundtrip_structural_equality():
    """SCHEMA-04: Parsed XML contains the expected class, state, and transition elements by ID."""
    xml_bytes = render_sample_xml()
    root = DET.fromstring(xml_bytes)
    all_ids = {
        cell.get("id")
        for cell in root.iter("mxCell")
        if cell.get("id") is not None
    }
    # Check class cells present
    assert class_id(DOMAIN, "Valve") in all_ids
    assert class_id(DOMAIN, "ActuatorPosition") in all_ids
    # Check state cells present
    assert state_id(DOMAIN, "Valve", "Idle") in all_ids
    assert state_id(DOMAIN, "Valve", "Opening") in all_ids
    # Check transition present
    assert transition_id(DOMAIN, "Valve", "Idle", "Open", 0) in all_ids
