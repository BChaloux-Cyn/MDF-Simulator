"""Wave 0 test scaffold for simulation runner (Phase 05.3).

Stub tests for bundle loader, ctx API, scenario schema, preflight, MCP tool
unit tests, and trigger evaluator. Each stub is marked xfail until the
implementing plan completes.
"""
import pytest

from engine.registry import InstanceRegistry
from engine.ctx import SimulationContext
from engine.manifest import AssociationManifest, ClassManifest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_MINIMAL_CLASS_DEFS: dict[str, ClassManifest] = {
    "Elevator": {
        "name": "Elevator",
        "is_abstract": False,
        "identifier_attrs": ["elevator_id"],
        "attributes": {"elevator_id": 0, "current_floor": 1},
        "entry_actions": {},
        "initial_state": "Idle",
        "final_states": [],
        "senescent_states": [],
        "transition_table": {},
        "supertype": None,
        "subtypes": [],
    },
    "Door": {
        "name": "Door",
        "is_abstract": False,
        "identifier_attrs": ["door_id"],
        "attributes": {"door_id": 0},
        "entry_actions": {},
        "initial_state": "Closed",
        "final_states": [],
        "senescent_states": [],
        "transition_table": {},
        "supertype": None,
        "subtypes": [],
    },
    "Shaft": {
        "name": "Shaft",
        "is_abstract": False,
        "identifier_attrs": ["shaft_id"],
        "attributes": {"shaft_id": 0},
        "entry_actions": {},
        "initial_state": "Idle",
        "final_states": [],
        "senescent_states": [],
        "transition_table": {},
        "supertype": None,
        "subtypes": [],
    },
}

_MINIMAL_ASSOCIATIONS: dict[str, AssociationManifest] = {
    "R1": {
        "rel_id": "R1",
        "class_a": "Elevator",
        "class_b": "Shaft",
        "mult_a_to_b": "1",
        "mult_b_to_a": "1",
    },
}

_MINIMAL_MANIFEST = {
    "class_defs": _MINIMAL_CLASS_DEFS,
    "associations": _MINIMAL_ASSOCIATIONS,
    "generalizations": {},
}


# Bundle loader tests (Plan 03)
def test_bundle_loader_extracts_and_verifies_version():
    pytest.xfail("Plan 03 not implemented")

def test_bundle_loader_hard_fails_on_version_mismatch():
    pytest.xfail("Plan 03 not implemented")

def test_bundle_loader_rebinds_transition_table_callables():
    pytest.xfail("Plan 03 not implemented")

def test_bundle_loader_reverses_state_event_keys():
    pytest.xfail("Plan 03 not implemented")

# ctx API tests (Plan 02)
def test_ctx_instance_key_populated_on_create_sync():
    reg = InstanceRegistry(_MINIMAL_CLASS_DEFS)
    reg.create_sync("Elevator", {"elevator_id": 1}, initial_state="Idle", attrs={"current_floor": 1})
    inst = reg.lookup("Elevator", {"elevator_id": 1})
    assert inst is not None
    assert inst["__instance_key__"] == frozenset({("elevator_id", 1)})
    assert inst["__class_name__"] == "Elevator"
    assert inst["current_floor"] == 1  # existing attrs still present


def test_ctx_instance_key_populated_on_create_async():
    reg = InstanceRegistry(_MINIMAL_CLASS_DEFS)
    reg.create_async("Elevator", {"elevator_id": 2}, initial_state="Idle")
    inst = reg.lookup("Elevator", {"elevator_id": 2})
    assert inst is not None
    assert inst["__instance_key__"] == frozenset({("elevator_id", 2)})
    assert inst["__class_name__"] == "Elevator"


def test_ctx_instance_key_composite_identifier():
    """Composite identifier produces frozenset of all (name, value) pairs."""
    class_defs = {
        "Floor": {
            "name": "Floor",
            "is_abstract": False,
            "identifier_attrs": ["floor_id", "side"],
            "attributes": {"floor_id": 0, "side": ""},
            "entry_actions": {},
            "initial_state": "Idle",
            "final_states": [],
            "senescent_states": [],
            "transition_table": {},
            "supertype": None,
            "subtypes": [],
        }
    }
    reg = InstanceRegistry(class_defs)
    reg.create_sync("Floor", {"floor_id": 1, "side": "north"}, initial_state="Idle")
    inst = reg.lookup("Floor", {"floor_id": 1, "side": "north"})
    assert inst is not None
    assert inst["__instance_key__"] == frozenset({("floor_id", 1), ("side", "north")})
    assert inst["__class_name__"] == "Floor"


def test_ctx_create_returns_instance_dict_with_keys():
    """ctx.create(class, attrs) returns instance dict with __instance_key__ and __class_name__."""
    ctx = SimulationContext(_MINIMAL_MANIFEST)
    inst = ctx.create("Door", {"door_id": 1})
    assert inst["__instance_key__"] == frozenset({("door_id", 1)})
    assert inst["__class_name__"] == "Door"


def test_ctx_delete_by_instance_dict():
    """ctx.delete(inst_dict) removes instance using __class_name__ and __instance_key__."""
    ctx = SimulationContext(_MINIMAL_MANIFEST)
    inst = ctx.create("Door", {"door_id": 1})
    ctx.delete(inst)
    assert ctx.registry.lookup("Door", {"door_id": 1}) is None


def test_ctx_relate_by_instance_dicts():
    """ctx.relate(a_dict, b_dict, 'R1') creates a navigable link."""
    ctx = SimulationContext(_MINIMAL_MANIFEST)
    elev = ctx.create("Elevator", {"elevator_id": 1})
    shaft = ctx.create("Shaft", {"shaft_id": 1})
    ctx.relate(elev, shaft, "R1")
    result = ctx.select_any_related(elev, ["R1"])
    assert result is not None
    assert result["shaft_id"] == 1


def test_ctx_select_any_related_navigation():
    """ctx.select_any_related traverses a relationship chain and returns the target instance."""
    ctx = SimulationContext(_MINIMAL_MANIFEST)
    elev = ctx.create("Elevator", {"elevator_id": 10})
    shaft = ctx.create("Shaft", {"shaft_id": 10})
    ctx.relate(elev, shaft, "R1")
    found = ctx.select_any_related(elev, ["R1"])
    assert found is not None
    assert found["__class_name__"] == "Shaft"
    assert found["shaft_id"] == 10


def test_ctx_generate_accepts_target_instance_key():
    """ctx.generate accepts target=<frozenset instance_key> form."""
    ctx = SimulationContext({
        "class_defs": {
            "Door": {
                "name": "Door",
                "is_abstract": False,
                "identifier_attrs": ["door_id"],
                "attributes": {"door_id": 0},
                "entry_actions": {},
                "initial_state": "Closed",
                "final_states": [],
                "senescent_states": [],
                "transition_table": {
                    ("Closed", "DoorOpen"): {"next_state": "Open", "action_fn": None, "guard_fn": None},
                },
                "supertype": None,
                "subtypes": [],
            },
        },
        "associations": {},
        "generalizations": {},
    })
    door = ctx.create("Door", {"door_id": 1})
    elev_dict = {"__class_name__": "Door", "__instance_key__": frozenset({("door_id", 1)}), "door_id": 1}
    steps = ctx.generate("DoorOpen", target=door["__instance_key__"], args={}, sender=elev_dict)
    assert len(steps) >= 1

# Scenario schema tests (Plan 03)
def test_scenario_schema_valid_yaml_parses():
    pytest.xfail("Plan 03 not implemented")

def test_scenario_schema_missing_sender_rejected():
    pytest.xfail("Plan 03 not implemented")

def test_scenario_schema_at_ms_after_ms_mutually_exclusive():
    pytest.xfail("Plan 03 not implemented")

def test_scenario_schema_event_or_call_required():
    pytest.xfail("Plan 03 not implemented")

# Preflight multiplicity check tests (Plan 03)
def test_preflight_passes_valid_population():
    pytest.xfail("Plan 03 not implemented")

def test_preflight_rejects_missing_required_multiplicity():
    pytest.xfail("Plan 03 not implemented")

# MCP tool wrapper tests (Plan 04)
def test_simulate_domain_returns_result_dict():
    pytest.xfail("Plan 04 not implemented")

def test_simulate_domain_writes_trace_file():
    pytest.xfail("Plan 04 not implemented")

def test_simulate_class_isolated_single_class():
    pytest.xfail("Plan 04 not implemented")

def test_simulate_domain_hard_fails_on_engine_version_mismatch():
    pytest.xfail("Plan 04 not implemented")

# Trigger evaluator tests (Plan 04)
def test_trigger_fires_on_state_match():
    pytest.xfail("Plan 04 not implemented")

def test_trigger_fires_on_attr_eq_match():
    pytest.xfail("Plan 04 not implemented")

def test_trigger_disarms_after_first_fire_when_repeat_false():
    pytest.xfail("Plan 04 not implemented")

def test_trigger_rearms_when_repeat_true():
    pytest.xfail("Plan 04 not implemented")
