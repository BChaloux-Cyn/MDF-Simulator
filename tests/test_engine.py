"""Wave 0 test scaffold for engine/ runtime framework (Phase 05.1).

Three implemented tests verify the data type contracts established in plan
05.1-01. The remaining stubs are placeholders for tests implemented by later
plans in Phase 05.1.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from engine.event import Event, make_instance_key
from engine.manifest import (
    AssociationManifest,
    ClassManifest,
    DomainManifest,
    TransitionEntry,
)
from engine.microstep import (
    ActionExecuted,
    BridgeCalled,
    ErrorMicroStep,
    EventCancelled,
    EventDelayed,
    EventDelayExpired,
    EventReceived,
    GenerateDispatched,
    GuardEvaluated,
    InstanceCreated,
    InstanceDeleted,
    SchedulerSelected,
    TransitionFired,
)


# ---------------------------------------------------------------------------
# Hand-written domain manifest fixture (minimal two-class model)
# ---------------------------------------------------------------------------


def _noop_action(*_a, **_kw):
    return None


DOMAIN_MANIFEST: DomainManifest = {
    "class_defs": {
        "TrafficLight": {
            "name": "TrafficLight",
            "is_abstract": False,
            "identifier_attrs": ["light_id"],
            "attributes": {"light_id": "int", "current_color": "str"},
            "initial_state": "Idle",
            "final_states": [],
            "transition_table": {
                ("Idle", "TurnOn"): {"next_state": "Green", "action_fn": _noop_action, "guard_fn": None},
                ("Green", "Timer"): {"next_state": "Yellow", "action_fn": _noop_action, "guard_fn": None},
                ("Yellow", "Timer"): {"next_state": "Red", "action_fn": _noop_action, "guard_fn": None},
                ("Red", "Timer"): {"next_state": "Green", "action_fn": _noop_action, "guard_fn": None},
            },
            "supertype": None,
            "subtypes": [],
        },
        "Controller": {
            "name": "Controller",
            "is_abstract": False,
            "identifier_attrs": ["ctrl_id"],
            "attributes": {"ctrl_id": "int"},
            "initial_state": "Off",
            "final_states": ["Shutdown"],
            "transition_table": {
                ("Off", "Start"): {"next_state": "Running", "action_fn": _noop_action, "guard_fn": None},
                ("Running", "Stop"): {"next_state": "Shutdown", "action_fn": _noop_action, "guard_fn": None},
            },
            "supertype": None,
            "subtypes": [],
        },
    },
    "associations": {
        "R1": {
            "rel_id": "R1",
            "class_a": "Controller",
            "class_b": "TrafficLight",
            "mult_a_to_b": "M",
            "mult_b_to_a": "1",
        },
    },
    "generalizations": {},
}


BRIDGE_MOCKS = {"LogEvent": "ok", "GetTimeOfDay": "12:00"}


# ---------------------------------------------------------------------------
# Implemented tests (run now)
# ---------------------------------------------------------------------------


def test_microstep_types():
    """SC-08 partial: every micro-step class has the correct Literal `type`."""
    cases = [
        (SchedulerSelected(queue="priority", event_type="E", target_class="C", target_instance_id={}), "scheduler_selected"),
        (EventReceived(class_name="C", instance_id={}, event_type="E", args={}, queue="priority"), "event_received"),
        (GuardEvaluated(expression="x>0", result=True, variable_values={}), "guard_evaluated"),
        (TransitionFired(from_state="A", to_state="B", class_name="C", instance_id={}), "transition_fired"),
        (ActionExecuted(pycca_line="x:=1", assignments_made={}), "action_executed"),
        (GenerateDispatched(event_type="E", sending_class="C", sending_instance_id={}, target_class="D", target_instance_id={}, args={}, queue="standard"), "generate_dispatched"),
        (EventDelayed(event_type="E", sending_class="C", sending_instance_id={}, target_class="D", target_instance_id={}, args={}, delay_ms=100.0), "event_delayed"),
        (EventDelayExpired(event_type="E", target_class="C", target_instance_id={}), "event_delay_expired"),
        (EventCancelled(cancelled_event_type="E", sender_id={}, target_id={}), "event_cancelled"),
        (InstanceCreated(class_name="C", instance_id={}, initial_attrs={}, mode="sync"), "instance_created"),
        (InstanceDeleted(class_name="C", instance_id={}, mode="async"), "instance_deleted"),
        (BridgeCalled(operation="op", args={}, mock_return=None), "bridge_called"),
    ]
    for ms, expected_type in cases:
        assert ms.type == expected_type
    assert len(cases) == 12

    err = ErrorMicroStep(error_kind="cant_happen", message="bad", context={})
    assert err.type == "error"
    assert err.error_kind == "cant_happen"
    assert err.message == "bad"


def test_event_and_instance_key():
    e = Event(
        event_type="Start",
        sender_class="Controller",
        sender_id={"ctrl_id": 1},
        target_class="TrafficLight",
        target_id={"light_id": 7},
        args={"x": 1},
    )
    assert e.event_type == "Start"
    assert e.sender_class == "Controller"
    assert e.sender_id == {"ctrl_id": 1}
    assert e.target_class == "TrafficLight"
    assert e.target_id == {"light_id": 7}
    assert e.args == {"x": 1}
    assert e.delay_ms is None

    k1 = make_instance_key({"a": 1, "b": 2})
    k2 = make_instance_key({"b": 2, "a": 1})
    assert k1 == k2
    assert isinstance(k1, frozenset)
    assert hash(k1) == hash(k2)
    assert make_instance_key({"floor_num": 3}) == frozenset({("floor_num", 3)})


def test_engine_isolation_no_schema_imports():
    """SC-11: engine/ must not import from schema/, tools/, or pycca/."""
    engine_dir = pathlib.Path(__file__).parent.parent / "engine"
    forbidden = re.compile(r"^\s*(from|import)\s+(schema|tools|pycca)(\b|\.)", re.MULTILINE)
    offenders = []
    for py_file in engine_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if forbidden.search(text):
            offenders.append(str(py_file))
    assert offenders == [], f"engine/ files import forbidden modules: {offenders}"


# ---------------------------------------------------------------------------
# Skipped stubs — implemented by later plans in Phase 05.1
# ---------------------------------------------------------------------------


from engine.registry import InstanceRegistry


def _make_registry() -> InstanceRegistry:
    return InstanceRegistry(DOMAIN_MANIFEST["class_defs"])


def test_registry_create_sync_delete_lookup():
    reg = _make_registry()
    steps = reg.create_sync("TrafficLight", {"light_id": "main"}, initial_state="Idle")
    assert len(steps) == 1
    assert isinstance(steps[0], InstanceCreated)
    assert steps[0].mode == "sync"
    assert steps[0].class_name == "TrafficLight"
    assert steps[0].instance_id == {"light_id": "main"}

    inst = reg.lookup("TrafficLight", {"light_id": "main"})
    assert inst is not None
    assert inst["light_id"] == "main"
    assert inst["curr_state"] == "Idle"

    assert reg.lookup("TrafficLight", {"light_id": "nonexistent"}) is None

    del_steps = reg.delete_sync("TrafficLight", {"light_id": "main"})
    assert len(del_steps) == 1
    assert isinstance(del_steps[0], InstanceDeleted)
    assert del_steps[0].mode == "sync"
    assert reg.lookup("TrafficLight", {"light_id": "main"}) is None

    # Double-deletion is an ErrorMicroStep, not an exception
    err = reg.delete_sync("TrafficLight", {"light_id": "main"})
    assert len(err) == 1
    assert isinstance(err[0], ErrorMicroStep)
    assert err[0].error_kind == "double_deletion"


def test_registry_create_async():
    reg = _make_registry()
    steps, evt = reg.create_async(
        "TrafficLight", {"light_id": "async1"}, initial_state="Idle"
    )
    assert len(steps) == 1
    assert isinstance(steps[0], InstanceCreated)
    assert steps[0].mode == "async"
    assert evt is not None
    assert evt.event_type == "__creation__"
    assert evt.target_class == "TrafficLight"
    assert evt.target_id == {"light_id": "async1"}
    # Instance is stored even before creation event processed
    assert reg.lookup("TrafficLight", {"light_id": "async1"}) is not None


def test_registry_composite_identifier():
    composite_defs = {
        "Sensor": {
            "name": "Sensor",
            "is_abstract": False,
            "identifier_attrs": ["zone", "node"],
            "attributes": {"zone": "str", "node": "int", "value": "float"},
            "initial_state": "Off",
            "final_states": [],
            "transition_table": {},
            "supertype": None,
            "subtypes": [],
        }
    }
    reg = InstanceRegistry(composite_defs)
    reg.create_sync("Sensor", {"zone": "north", "node": 1}, initial_state="Off")
    # Order-independent lookup
    inst = reg.lookup("Sensor", {"node": 1, "zone": "north"})
    assert inst is not None
    assert inst["zone"] == "north"
    assert inst["node"] == 1
    # Different composite key — different instance
    assert reg.lookup("Sensor", {"zone": "north", "node": 2}) is None


def test_registry_delete_async():
    reg = _make_registry()
    reg.create_sync("TrafficLight", {"light_id": "x"}, initial_state="Idle")
    evt = reg.delete_async("TrafficLight", {"light_id": "x"})
    assert evt is not None
    assert evt.event_type == "__deletion__"
    # Instance still present until process_deletion
    assert reg.lookup("TrafficLight", {"light_id": "x"}) is not None
    steps = reg.process_deletion("TrafficLight", {"light_id": "x"})
    assert len(steps) == 1
    assert isinstance(steps[0], InstanceDeleted)
    assert steps[0].mode == "async"
    assert reg.lookup("TrafficLight", {"light_id": "x"}) is None


def test_registry_lookup_all():
    reg = _make_registry()
    assert reg.lookup_all("TrafficLight") == []
    reg.create_sync("TrafficLight", {"light_id": "a"}, initial_state="Idle")
    assert len(reg.lookup_all("TrafficLight")) == 1
    reg.create_sync("TrafficLight", {"light_id": "b"}, initial_state="Idle")
    reg.create_sync("TrafficLight", {"light_id": "c"}, initial_state="Idle")
    assert len(reg.lookup_all("TrafficLight")) == 3
    # Other classes unaffected
    assert reg.lookup_all("Controller") == []


def test_registry_get_set_state():
    reg = _make_registry()
    reg.create_sync("TrafficLight", {"light_id": "s1"}, initial_state="Idle")
    assert reg.get_state("TrafficLight", {"light_id": "s1"}) == "Idle"
    reg.set_state("TrafficLight", {"light_id": "s1"}, "Green")
    assert reg.get_state("TrafficLight", {"light_id": "s1"}) == "Green"


def test_registry_get_set_attr():
    reg = _make_registry()
    reg.create_sync("TrafficLight", {"light_id": "a1"}, initial_state="Idle")
    reg.set_attr("TrafficLight", {"light_id": "a1"}, "current_color", "red")
    assert reg.get_attr("TrafficLight", {"light_id": "a1"}, "current_color") == "red"


def test_registry_supertype_inheritance():
    """D-04: supertype attributes are merged into subtype instances at creation."""
    class_defs = {
        "Vehicle": {
            "name": "Vehicle",
            "is_abstract": True,
            "identifier_attrs": ["vid"],
            "attributes": {"vid": "int", "wheels": 4},
            "initial_state": None,
            "final_states": [],
            "transition_table": {},
            "supertype": None,
            "subtypes": ["Car"],
        },
        "Car": {
            "name": "Car",
            "is_abstract": False,
            "identifier_attrs": ["vid"],
            "attributes": {"vid": "int", "trunk_size": 200},
            "initial_state": "Parked",
            "final_states": [],
            "transition_table": {},
            "supertype": "Vehicle",
            "subtypes": [],
        },
    }
    reg = InstanceRegistry(class_defs)
    # Abstract instantiation rejected
    err = reg.create_sync("Vehicle", {"vid": 1}, initial_state="X")
    assert isinstance(err[0], ErrorMicroStep)
    assert err[0].error_kind == "abstract_instantiation"

    # Concrete subtype creation merges supertype attrs
    reg.create_sync("Car", {"vid": 7}, initial_state="Parked")
    inst = reg.lookup("Car", {"vid": 7})
    assert inst is not None
    assert inst["wheels"] == 4  # inherited from Vehicle
    assert inst["trunk_size"] == 200  # own attribute


@pytest.mark.skip(reason="Implemented in plan 05.1-02")
def test_relationships_relate_unrelate_navigate():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-02")
def test_relationships_multiplicity_enforcement():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-02")
def test_relationships_chained_navigation():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_scheduler_priority_before_standard():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_scheduler_fifo_within_queue():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_scheduler_delay_feeds_standard():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_run_to_completion():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_polymorphic_dispatch():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_cant_happen_error_microstep():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_event_ignored_silent():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_final_state_async_deletion():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_cancel_delayed_event():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_at_most_one_delayed_per_triple():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_creation_event_processing():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_guard_false_skips_transition():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-04")
def test_event_to_nonexistent_instance():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_all_microstep_types():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-03")
def test_bridge_mock_hit():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-03")
def test_bridge_mock_miss_returns_none():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_determinism_identical_streams():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_full_lifecycle():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_error_propagation():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_action_callback_wiring():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_delay_clock():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_select_any_many():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_load_scenario():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_multi_class_interaction():
    pass


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_integration_paused_clock_blocks_delay():
    pass
