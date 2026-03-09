"""Tests for yaml_schema.py — SCHEMA-01 (valid YAML accepted) and SCHEMA-02 (schema_version required)."""
import pytest
from pydantic import ValidationError

from schema.yaml_schema import (  # noqa: F401 — import smoke test
    ClassDiagramFile,
    DomainsFile,
    StateDiagramFile,
    TypesFile,
)

# ---------------------------------------------------------------------------
# Fixture data — inline dicts, no file I/O
# ---------------------------------------------------------------------------

VALID_DOMAINS = {
    "schema_version": "1.0.0",
    "domains": [
        {"name": "Hydraulics", "type": "application", "description": "Controls valves"},
        {"name": "Timer", "type": "realized", "description": "Wraps OS timers"},
    ],
    "bridges": [
        {
            "from": "Hydraulics",
            "to": "Timer",
            "operations": [
                {
                    "name": "start_timer",
                    "params": [{"name": "duration", "type": "Integer"}],
                    "return": "UniqueID",
                },
                {
                    "name": "cancel_timer",
                    "params": [{"name": "timer_id", "type": "UniqueID"}],
                    "return": None,
                },
            ],
        }
    ],
}

VALID_CLASS_DIAGRAM = {
    "schema_version": "1.0.0",
    "domain": "Hydraulics",
    "classes": [
        {
            "name": "Valve",
            "stereotype": "entity",
            "attributes": [
                {"name": "valve_id", "type": "UniqueID", "identifier": True},
                {"name": "position", "type": "Real"},
                {"name": "r1_timer_id", "type": "UniqueID", "referential": "R1"},
            ],
        },
        {
            "name": "ValveCommand",
            "stereotype": "associative",
            "formalizes": "R2",
            "attributes": [
                {"name": "command_id", "type": "UniqueID", "identifier": True},
            ],
        },
    ],
    "associations": [
        {
            "name": "R1",
            "point_1": "Valve",
            "point_2": "Timer",
            "1_mult_2": "1",
            "2_mult_1": "0..1",
            "1_phrase_2": "uses",
            "2_phrase_1": "is used by",
        }
    ],
    "bridges": [
        {
            "to_domain": "Timer",
            "direction": "required",
            "operations": ["start_timer", "cancel_timer"],
        }
    ],
}

VALID_STATE_DIAGRAM = {
    "schema_version": "1.0.0",
    "domain": "Hydraulics",
    "class": "Valve",
    "initial_state": "Idle",
    "events": [
        {"name": "open", "params": [{"name": "target_pos", "type": "Real"}]},
        {"name": "close"},
    ],
    "states": [
        {"name": "Idle", "entry_action": None},
        {"name": "Opening", "entry_action": "start_actuator()"},
        {"name": "Open"},
    ],
    "transitions": [
        {"from": "Idle", "to": "Opening", "event": "open"},
        {"from": "Opening", "to": "Open", "event": "position_reached"},
        # Two guarded transitions on same (from, event) — valid, both have guard
        {
            "from": "Open",
            "to": "Opening",
            "event": "open",
            "guard": "target_pos != current_pos",
        },
        {
            "from": "Open",
            "to": "Open",
            "event": "open",
            "guard": "target_pos == current_pos",
        },
    ],
}

VALID_TYPES = {
    "schema_version": "1.0.0",
    "domain": "Hydraulics",
    "types": [
        {"name": "Percentage", "base": "Real", "units": "%", "range": [0.0, 100.0]},
        {
            "name": "ValveMode",
            "base": "enum",
            "values": ["Manual", "Auto", "Locked"],
        },
        {
            "name": "ValveConfig",
            "base": "struct",
            "fields": [
                {"name": "max_flow", "type": "Real"},
                {"name": "mode", "type": "ValveMode"},
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Test 1: SCHEMA-01 — valid DOMAINS.yaml accepted
# ---------------------------------------------------------------------------

def test_valid_domains_yaml_accepted():
    """SCHEMA-01: A valid DOMAINS.yaml dict is accepted by DomainsFile without error."""
    result = DomainsFile.model_validate(VALID_DOMAINS)
    assert result.schema_version == "1.0.0"
    assert len(result.domains) == 2
    assert result.domains[0].name == "Hydraulics"
    assert result.domains[1].type == "realized"
    assert len(result.bridges) == 1
    bridge = result.bridges[0]
    assert bridge.from_domain == "Hydraulics"
    assert bridge.to == "Timer"
    assert len(bridge.operations) == 2
    assert bridge.operations[0].return_type == "UniqueID"
    assert bridge.operations[1].return_type is None


# ---------------------------------------------------------------------------
# Test 2: SCHEMA-01 — valid class-diagram.yaml accepted
# ---------------------------------------------------------------------------

def test_valid_class_diagram_accepted():
    """SCHEMA-01: A valid class-diagram.yaml dict is accepted by ClassDiagramFile without error."""
    result = ClassDiagramFile.model_validate(VALID_CLASS_DIAGRAM)
    assert result.schema_version == "1.0.0"
    assert result.domain == "Hydraulics"
    assert len(result.classes) == 2
    valve = result.classes[0]
    assert valve.name == "Valve"
    assert valve.stereotype == "entity"
    id_attr = next(a for a in valve.attributes if a.identifier)
    assert id_attr.name == "valve_id"
    assoc_class = result.classes[1]
    assert assoc_class.stereotype == "associative"
    assert assoc_class.formalizes == "R2"
    assert len(result.associations) == 1
    assoc = result.associations[0]
    assert assoc.name == "R1"
    assert assoc.mult_1_to_2 == "1"
    assert assoc.mult_2_to_1 == "0..1"
    assert len(result.bridges) == 1
    bridge = result.bridges[0]
    assert bridge.direction == "required"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 3: SCHEMA-01 — valid state-diagram.yaml accepted
# ---------------------------------------------------------------------------

def test_valid_state_diagram_accepted():
    """SCHEMA-01: A valid state-diagrams/<Class>.yaml dict is accepted by StateDiagramFile without error."""
    result = StateDiagramFile.model_validate(VALID_STATE_DIAGRAM)
    assert result.schema_version == "1.0.0"
    assert result.domain == "Hydraulics"
    assert result.class_name == "Valve"
    assert len(result.events) == 2
    assert len(result.states) == 3
    assert len(result.transitions) == 4
    # Verify alias field mapping
    first = result.transitions[0]
    assert first.from_state == "Idle"
    assert first.to == "Opening"
    assert first.guard is None


# ---------------------------------------------------------------------------
# Test 4: SCHEMA-01 — valid types.yaml accepted
# ---------------------------------------------------------------------------

def test_valid_types_yaml_accepted():
    """SCHEMA-01: A valid types.yaml dict is accepted by TypesFile without error."""
    result = TypesFile.model_validate(VALID_TYPES)
    assert result.schema_version == "1.0.0"
    assert result.domain == "Hydraulics"
    assert len(result.types) == 3
    scalar, enum, struct = result.types
    assert scalar.base == "Real"  # type: ignore[union-attr]
    assert enum.base == "enum"    # type: ignore[union-attr]
    assert struct.base == "struct"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 5: SCHEMA-02 — missing schema_version rejected
# ---------------------------------------------------------------------------

def test_missing_schema_version_rejected():
    """SCHEMA-02: Any model file dict missing schema_version raises ValidationError."""
    bad = {k: v for k, v in VALID_DOMAINS.items() if k != "schema_version"}
    with pytest.raises(ValidationError) as exc_info:
        DomainsFile.model_validate(bad)
    assert "schema_version" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 6: SCHEMA-02 — invalid semver rejected
# ---------------------------------------------------------------------------

def test_invalid_semver_rejected():
    """SCHEMA-02: schema_version not matching semver pattern raises ValidationError."""
    bad = {**VALID_CLASS_DIAGRAM, "schema_version": "bad"}
    with pytest.raises(ValidationError):
        ClassDiagramFile.model_validate(bad)

    # Also test two-part version (missing patch)
    bad2 = {**VALID_DOMAINS, "schema_version": "1.0"}
    with pytest.raises(ValidationError):
        DomainsFile.model_validate(bad2)


# ---------------------------------------------------------------------------
# Test 7: SCHEMA-01 — associative without formalizes rejected
# ---------------------------------------------------------------------------

def test_associative_missing_formalizes_rejected():
    """SCHEMA-01: ClassDef with stereotype=associative and no formalizes raises ValidationError."""
    bad = {
        "schema_version": "1.0.0",
        "domain": "Hydraulics",
        "classes": [
            {
                "name": "ValveCommand",
                "stereotype": "associative",
                # formalizes intentionally omitted
                "attributes": [],
            }
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        ClassDiagramFile.model_validate(bad)
    assert "formalizes" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 8: SCHEMA-01 — guard all-or-none violation rejected
# ---------------------------------------------------------------------------

def test_guard_all_or_none_violation_rejected():
    """SCHEMA-01: StateDiagramFile with mixed guarded/unguarded transitions on same (from, event) raises ValidationError."""
    bad = {
        "schema_version": "1.0.0",
        "domain": "Hydraulics",
        "class": "Valve",
        "initial_state": "Idle",
        "states": [
            {"name": "Idle"},
            {"name": "Opening"},
            {"name": "Bypassed"},
        ],
        "transitions": [
            # Both share (Idle, open) — one guarded, one not → violation
            {"from": "Idle", "to": "Opening", "event": "open"},
            {
                "from": "Idle",
                "to": "Bypassed",
                "event": "open",
                "guard": "bypass_mode == True",
            },
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        StateDiagramFile.model_validate(bad)
    assert "guard" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 9: SCHEMA-01 — Attribute and Method visibility/scope defaults and values
# ---------------------------------------------------------------------------

def test_attribute_visibility_scope_defaults():
    """SCHEMA-01: Attribute defaults visibility=private, scope=instance when not specified."""
    data = {
        "schema_version": "1.0.0",
        "domain": "Hydraulics",
        "classes": [
            {
                "name": "Valve",
                "stereotype": "entity",
                "attributes": [
                    {"name": "valve_id", "type": "UniqueID"},
                ],
                "methods": [
                    {"name": "open", "scope": "instance"},
                ],
            }
        ],
    }
    result = ClassDiagramFile.model_validate(data)
    attr = result.classes[0].attributes[0]
    assert attr.visibility == "private"
    assert attr.scope == "instance"
    method = result.classes[0].methods[0]
    assert method.visibility == "private"


# ---------------------------------------------------------------------------
# Test 10: MCP-04 — initial_state field required on StateDiagramFile
# ---------------------------------------------------------------------------

def test_initial_state_missing_rejected():
    """MCP-04: StateDiagramFile without initial_state raises ValidationError."""
    bad = {
        "schema_version": "1.0.0",
        "domain": "Hydraulics",
        "class": "Valve",
        "states": [{"name": "Idle"}],
    }
    with pytest.raises(ValidationError) as exc_info:
        StateDiagramFile.model_validate(bad)
    assert "initial_state" in str(exc_info.value)


def test_initial_state_accepted():
    """MCP-04: StateDiagramFile with initial_state is accepted and field is accessible."""
    data = {
        "schema_version": "1.0.0",
        "domain": "Hydraulics",
        "class": "Valve",
        "initial_state": "Idle",
        "states": [{"name": "Idle"}],
    }
    result = StateDiagramFile.model_validate(data)
    assert result.initial_state == "Idle"


def test_import_networkx_and_lark():
    """MCP-04: networkx and lark packages are importable after install."""
    import networkx  # noqa: F401
    import lark  # noqa: F401


def test_attribute_visibility_scope_explicit():
    """SCHEMA-01: Attribute accepts explicit visibility and scope values."""
    data = {
        "schema_version": "1.0.0",
        "domain": "Hydraulics",
        "classes": [
            {
                "name": "Valve",
                "stereotype": "entity",
                "attributes": [
                    {
                        "name": "instance_count",
                        "type": "Integer",
                        "visibility": "public",
                        "scope": "class",
                    },
                    {
                        "name": "pressure",
                        "type": "Real",
                        "visibility": "protected",
                        "scope": "instance",
                    },
                ],
                "methods": [
                    {
                        "name": "create",
                        "visibility": "public",
                        "scope": "class",
                    },
                ],
            }
        ],
    }
    result = ClassDiagramFile.model_validate(data)
    attrs = result.classes[0].attributes
    assert attrs[0].visibility == "public"
    assert attrs[0].scope == "class"
    assert attrs[1].visibility == "protected"
    assert attrs[1].scope == "instance"
    method = result.classes[0].methods[0]
    assert method.visibility == "public"
    assert method.scope == "class"
