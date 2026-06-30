"""tests/test_manifest_builder.py — Test event parameter collection in manifest builder."""
import pytest
from compiler.manifest_builder import build_class_manifest
from schema.drawio_canonical import CanonicalClassEntry, CanonicalStateDiagram, CanonicalState, CanonicalTransition
from unittest.mock import MagicMock


def _minimal_entry(name="Widget") -> CanonicalClassEntry:
    return CanonicalClassEntry(
        name=name,
        stereotype="active",
        specializes=None,
        attributes=[],
        methods=[],
    )


def _minimal_sd(class_name="Widget") -> CanonicalStateDiagram:
    return CanonicalStateDiagram(
        type="state_diagram",
        domain="test",
        **{"class": class_name},
        initial_state="Idle",
        states=[
            CanonicalState(name="Idle", entry_action=None),
            CanonicalState(name="Active", entry_action=None),
        ],
        transitions=[
            CanonicalTransition(
                **{"from": "Idle"},
                to="Active",
                event="Activate",
                params="level: Integer",
                guard=None,
            ),
            CanonicalTransition(
                **{"from": "Active"},
                to="Idle",
                event="Reset",
                params=None,
                guard=None,
            ),
        ],
    )


class TestClassManifestEvents:
    def test_events_field_present(self):
        parser = MagicMock()
        parser.parse.return_value = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), _minimal_sd(), None, parser
        )
        assert "events" in manifest

    def test_event_with_params_stored(self):
        parser = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), _minimal_sd(), None, parser
        )
        assert manifest["events"]["Activate"] == "level: Integer"

    def test_event_without_params_stored_as_none(self):
        parser = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), _minimal_sd(), None, parser
        )
        assert manifest["events"]["Reset"] is None

    def test_no_state_diagram_gives_empty_events(self):
        parser = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), None, None, parser
        )
        assert manifest["events"] == {}
