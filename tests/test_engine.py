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


from engine.relationship import RelationshipStore


def test_relationships_relate_unrelate_navigate():
    store = RelationshipStore(DOMAIN_MANIFEST["associations"])
    ctrl = {"ctrl_id": 1}
    light = {"light_id": "main"}

    err = store.relate("R1", "Controller", ctrl, "TrafficLight", light)
    assert err == []

    # Navigate from Controller (M side) -> TrafficLight
    targets = store.navigate("R1", "Controller", ctrl)
    assert len(targets) == 1
    assert targets[0]["class"] == "TrafficLight"
    assert targets[0]["id"] == light

    # Navigate from TrafficLight (1 side) -> Controller
    back = store.navigate("R1", "TrafficLight", light)
    assert len(back) == 1
    assert back[0]["class"] == "Controller"
    assert back[0]["id"] == ctrl

    # Unrelate removes the link
    err = store.unrelate("R1", "Controller", ctrl, "TrafficLight", light)
    assert err == []
    assert store.navigate("R1", "Controller", ctrl) == []

    # Unrelate-not-found surfaces ErrorMicroStep
    err2 = store.unrelate("R1", "Controller", ctrl, "TrafficLight", light)
    assert len(err2) == 1
    assert isinstance(err2[0], ErrorMicroStep)
    assert err2[0].error_kind == "unrelate_not_found"


def test_relationships_multiplicity_enforcement():
    # R1: Controller (M) -- (1) TrafficLight
    # mult_a_to_b="M", mult_b_to_a="1"
    # => each TrafficLight links to at most 1 Controller
    # => each Controller may link to many TrafficLights
    store = RelationshipStore(DOMAIN_MANIFEST["associations"])
    c1 = {"ctrl_id": 1}
    c2 = {"ctrl_id": 2}
    light = {"light_id": "main"}
    light2 = {"light_id": "second"}

    assert store.relate("R1", "Controller", c1, "TrafficLight", light) == []
    # Second controller linking to same light violates the "1" side
    err = store.relate("R1", "Controller", c2, "TrafficLight", light)
    assert len(err) == 1
    assert isinstance(err[0], ErrorMicroStep)
    assert err[0].error_kind == "multiplicity_violation"

    # But the same controller can link multiple TrafficLights (M side)
    assert store.relate("R1", "Controller", c1, "TrafficLight", light2) == []
    targets = store.navigate("R1", "Controller", c1)
    assert len(targets) == 2


def test_relationships_chained_navigation():
    associations = {
        "R1": {
            "rel_id": "R1",
            "class_a": "A",
            "class_b": "B",
            "mult_a_to_b": "1",
            "mult_b_to_a": "1",
        },
        "R2": {
            "rel_id": "R2",
            "class_a": "B",
            "class_b": "C",
            "mult_a_to_b": "1",
            "mult_b_to_a": "1",
        },
    }
    store = RelationshipStore(associations)
    a = {"id": "a"}
    b = {"id": "b"}
    c = {"id": "c"}
    assert store.relate("R1", "A", a, "B", b) == []
    assert store.relate("R2", "B", b, "C", c) == []

    result = store.navigate_chain([("R1", "B"), ("R2", "C")], "A", a)
    assert len(result) == 1
    assert result[0]["class"] == "C"
    assert result[0]["id"] == c


# ---------------------------------------------------------------------------
# Plan 05.1-04: ThreeQueueScheduler tests
# ---------------------------------------------------------------------------


from engine.clock import SimulationClock
from engine.scheduler import ThreeQueueScheduler


def _make_scheduler(class_defs=None, generalizations=None):
    defs = class_defs if class_defs is not None else DOMAIN_MANIFEST["class_defs"]
    gens = generalizations if generalizations is not None else DOMAIN_MANIFEST["generalizations"]
    reg = InstanceRegistry(defs)
    clock = SimulationClock()
    sched = ThreeQueueScheduler(reg, clock, defs, gens)
    return sched, reg, clock


def test_scheduler_priority_before_standard():
    """SC-03: priority queue is dequeued before standard queue."""
    sched, reg, _ = _make_scheduler()
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    reg.create_sync("TrafficLight", {"light_id": 2}, initial_state="Green")

    # Cross-instance event -> standard
    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 2},
        target_class="TrafficLight", target_id={"light_id": 1},
    ))
    # Self-event -> priority
    sched.enqueue(Event(
        event_type="Timer",
        sender_class="TrafficLight", sender_id={"light_id": 2},
        target_class="TrafficLight", target_id={"light_id": 2},
    ))

    selected = [s for s in sched.execute() if isinstance(s, SchedulerSelected)]
    assert len(selected) == 2
    assert selected[0].queue == "priority"
    assert selected[0].target_instance_id == {"light_id": 2}
    assert selected[1].queue == "standard"
    assert selected[1].target_instance_id == {"light_id": 1}


def test_scheduler_fifo_within_queue():
    """SC-03 / D-16: FIFO ordering within a queue."""
    sched, reg, _ = _make_scheduler()
    for i in (1, 2, 3):
        reg.create_sync("TrafficLight", {"light_id": i}, initial_state="Idle")
    sender = {"light_id": 99}
    reg.create_sync("TrafficLight", sender, initial_state="Idle")
    for i in (1, 2, 3):
        sched.enqueue(Event(
            event_type="TurnOn",
            sender_class="TrafficLight", sender_id=sender,
            target_class="TrafficLight", target_id={"light_id": i},
        ))
    selected = [s for s in sched.execute() if isinstance(s, SchedulerSelected)]
    assert [s.target_instance_id["light_id"] for s in selected] == [1, 2, 3]


def test_scheduler_delay_feeds_standard():
    """SC-03 / rule 8: delayed event expires into standard queue on clock tick."""
    sched, reg, clock = _make_scheduler()
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    reg.create_sync("TrafficLight", {"light_id": 2}, initial_state="Idle")

    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 2},
        target_class="TrafficLight", target_id={"light_id": 1},
        delay_ms=100.0,
    ))

    # Before clock advance: nothing fires
    steps_before = list(sched.execute())
    assert not [s for s in steps_before if isinstance(s, SchedulerSelected)]

    # Advance past expiry; tick during execute() should release it
    clock.advance(150)
    steps_after = list(sched.execute())
    expired = [s for s in steps_after if isinstance(s, EventDelayExpired)]
    selected = [s for s in steps_after if isinstance(s, SchedulerSelected)]
    assert len(expired) == 1
    assert len(selected) == 1
    assert selected[0].queue == "standard"


def test_run_to_completion():
    """SC-04 / D-18-19: events generated in an action don't fire mid-event."""
    sched, reg, _ = _make_scheduler()
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    reg.create_sync("TrafficLight", {"light_id": 2}, initial_state="Green")

    def gen_action(instance, args, scheduler):
        # Generate cross-instance event during action execution
        scheduler.enqueue(Event(
            event_type="Timer",
            sender_class="TrafficLight", sender_id={"light_id": 1},
            target_class="TrafficLight", target_id={"light_id": 2},
        ))
        return {}

    custom_defs = {
        "TrafficLight": {
            **DOMAIN_MANIFEST["class_defs"]["TrafficLight"],
            "transition_table": {
                ("Idle", "TurnOn"): {"next_state": "Green", "action_fn": gen_action, "guard_fn": None},
                ("Green", "Timer"): {"next_state": "Yellow", "action_fn": _noop_action, "guard_fn": None},
            },
        }
    }
    sched, reg, _ = _make_scheduler(class_defs=custom_defs)
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    reg.create_sync("TrafficLight", {"light_id": 2}, initial_state="Green")

    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 1},
        target_class="TrafficLight", target_id={"light_id": 1},
    ))

    steps = list(sched.execute())
    # Find ActionExecuted and the subsequent TransitionFired for instance 2
    types = [type(s).__name__ for s in steps]
    # The first transition (light 1) must complete before the second event fires
    first_action = types.index("ActionExecuted")
    first_transition = types.index("TransitionFired")
    # Light 2's transition must come after light 1's transition
    light2_transitions = [
        i for i, s in enumerate(steps)
        if isinstance(s, TransitionFired) and s.instance_id == {"light_id": 2}
    ]
    assert light2_transitions
    assert light2_transitions[0] > first_transition
    assert first_action < first_transition


def test_polymorphic_dispatch():
    """SC-05 / D-20: event to supertype routes to subtype state machine."""
    class_defs = {
        "Animal": {
            "name": "Animal", "is_abstract": True,
            "identifier_attrs": ["aid"],
            "attributes": {"aid": "int"},
            "initial_state": None, "final_states": [],
            "transition_table": {},
            "supertype": None, "subtypes": ["Dog"],
        },
        "Dog": {
            "name": "Dog", "is_abstract": False,
            "identifier_attrs": ["aid"],
            "attributes": {"aid": "int"},
            "initial_state": "Quiet", "final_states": [],
            "transition_table": {
                ("Quiet", "Poke"): {"next_state": "Barking", "action_fn": _noop_action, "guard_fn": None},
            },
            "supertype": "Animal", "subtypes": [],
        },
    }
    generalizations = {"Animal": ["Dog"]}
    sched, reg, _ = _make_scheduler(class_defs=class_defs, generalizations=generalizations)
    reg.create_sync("Dog", {"aid": 1}, initial_state="Quiet")

    # Send the event to the supertype
    sched.enqueue(Event(
        event_type="Poke",
        sender_class="Dog", sender_id={"aid": 99},
        target_class="Animal", target_id={"aid": 1},
    ))
    steps = list(sched.execute())
    transitions = [s for s in steps if isinstance(s, TransitionFired)]
    assert len(transitions) == 1
    assert transitions[0].class_name == "Dog"
    assert transitions[0].to_state == "Barking"


def test_cant_happen_error_microstep():
    """SC-06 / D-21: missing transition cell yields ErrorMicroStep."""
    sched, reg, _ = _make_scheduler()
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    sched.enqueue(Event(
        event_type="Timer",  # not in (Idle, Timer)
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 1},
    ))
    steps = list(sched.execute())
    errors = [s for s in steps if isinstance(s, ErrorMicroStep)]
    assert len(errors) == 1
    assert errors[0].error_kind == "cant_happen"
    assert not [s for s in steps if isinstance(s, TransitionFired)]


def test_event_ignored_silent():
    """D-21: event-ignored cell consumes the event without TransitionFired."""
    custom_defs = {
        "TrafficLight": {
            **DOMAIN_MANIFEST["class_defs"]["TrafficLight"],
            "transition_table": {
                ("Idle", "Ping"): {"next_state": None, "action_fn": None, "guard_fn": None},
            },
        }
    }
    sched, reg, _ = _make_scheduler(class_defs=custom_defs)
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    sched.enqueue(Event(
        event_type="Ping",
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 1},
    ))
    steps = list(sched.execute())
    assert not [s for s in steps if isinstance(s, TransitionFired)]
    assert not [s for s in steps if isinstance(s, ErrorMicroStep)]
    received = [s for s in steps if isinstance(s, EventReceived)]
    assert len(received) == 1


def test_final_state_async_deletion():
    """SC-07 / D-23-24: reaching a final state triggers async deletion."""
    sched, reg, _ = _make_scheduler()
    reg.create_sync("Controller", {"ctrl_id": 1}, initial_state="Running")
    sched.enqueue(Event(
        event_type="Stop",
        sender_class="Controller", sender_id={"ctrl_id": 1},
        target_class="Controller", target_id={"ctrl_id": 1},
    ))
    steps = list(sched.execute())
    deleted = [s for s in steps if isinstance(s, InstanceDeleted)]
    assert len(deleted) == 1
    assert deleted[0].mode == "async"
    assert deleted[0].instance_id == {"ctrl_id": 1}


def test_cancel_delayed_event():
    """SC-03 / D-25: cancel removes a matching delayed event."""
    sched, reg, clock = _make_scheduler()
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 1},
        delay_ms=100.0,
    ))
    cancelled_steps = sched.cancel(
        "TurnOn", "TrafficLight", {"light_id": 99},
        "TrafficLight", {"light_id": 1},
    )
    assert len(cancelled_steps) == 1
    assert isinstance(cancelled_steps[0], EventCancelled)

    clock.advance(500)
    steps = list(sched.execute())
    assert not [s for s in steps if isinstance(s, TransitionFired)]
    assert not [s for s in steps if isinstance(s, EventDelayExpired)]


def test_at_most_one_delayed_per_triple():
    """D-14: posting a duplicate delayed (type, sender, target) replaces the first."""
    sched, reg, clock = _make_scheduler()
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 1},
        delay_ms=100.0,
    ))
    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 1},
        delay_ms=200.0,
    ))
    assert len(sched._delay) == 1


def test_creation_event_processing():
    """SC-03: __creation__ event sets initial_state."""
    sched, reg, _ = _make_scheduler()
    steps_create, evt = reg.create_async(
        "TrafficLight", {"light_id": 5}, initial_state="Idle"
    )
    assert reg.get_state("TrafficLight", {"light_id": 5}) is None
    sched.enqueue(evt)
    list(sched.execute())
    assert reg.get_state("TrafficLight", {"light_id": 5}) == "Idle"


def test_guard_false_skips_transition():
    """SC-03: guard returning False blocks the transition."""
    def guard_false(instance, args):
        return False

    custom_defs = {
        "TrafficLight": {
            **DOMAIN_MANIFEST["class_defs"]["TrafficLight"],
            "transition_table": {
                ("Idle", "TurnOn"): {"next_state": "Green", "action_fn": _noop_action, "guard_fn": guard_false},
            },
        }
    }
    sched, reg, _ = _make_scheduler(class_defs=custom_defs)
    reg.create_sync("TrafficLight", {"light_id": 1}, initial_state="Idle")
    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 1},
    ))
    steps = list(sched.execute())
    guards = [s for s in steps if isinstance(s, GuardEvaluated)]
    assert len(guards) == 1
    assert guards[0].result is False
    assert not [s for s in steps if isinstance(s, TransitionFired)]


def test_event_to_nonexistent_instance():
    """D-28: event to a missing instance produces unknown_target ErrorMicroStep."""
    sched, _, _ = _make_scheduler()
    sched.enqueue(Event(
        event_type="TurnOn",
        sender_class="TrafficLight", sender_id={"light_id": 99},
        target_class="TrafficLight", target_id={"light_id": 404},
    ))
    steps = list(sched.execute())
    errors = [s for s in steps if isinstance(s, ErrorMicroStep)]
    assert len(errors) == 1
    assert errors[0].error_kind == "unknown_target"


@pytest.mark.skip(reason="Implemented in plan 05.1-05")
def test_all_microstep_types():
    pass


def test_clock_basic():
    from engine.clock import SimulationClock

    clock = SimulationClock()
    assert clock.now() == 0.0
    clock.advance(100)
    assert clock.now() == 100.0


def test_clock_speed_multiplier():
    from engine.clock import SimulationClock

    clock = SimulationClock(speed_multiplier=2.0)
    clock.advance(100)
    assert clock.now() == 200.0


def test_clock_pause_resume():
    from engine.clock import SimulationClock

    clock = SimulationClock()
    clock.advance(50)
    assert clock.now() == 50.0
    clock.pause()
    assert clock.paused is True
    clock.advance(100)
    assert clock.now() == 50.0
    clock.resume()
    assert clock.paused is False
    clock.advance(100)
    assert clock.now() == 150.0


def test_bridge_mock_hit():
    """SC-09: known bridge ops return mock value + BridgeCalled micro-step."""
    from engine.bridge import BridgeMockRegistry

    fixture = pathlib.Path(__file__).parent / "fixtures" / "bridge_mocks.yaml"
    registry = BridgeMockRegistry.from_yaml(fixture)

    value, step = registry.call("LogEvent", {})
    assert value == "ok"
    assert isinstance(step, BridgeCalled)
    assert step.operation == "LogEvent"
    assert step.args == {}
    assert step.mock_return == "ok"

    value2, step2 = registry.call("GetTimeOfDay", {"zone": "EST"})
    assert value2 == "12:00"
    assert step2.operation == "GetTimeOfDay"
    assert step2.args == {"zone": "EST"}
    assert step2.mock_return == "12:00"


def test_bridge_mock_miss_returns_none():
    """SC-09 / D-30: undefined bridge ops return None without error."""
    from engine.bridge import BridgeMockRegistry

    registry = BridgeMockRegistry(mocks={"LogEvent": "ok"})
    value, step = registry.call("UnknownOp", {"x": 1})
    assert value is None
    assert isinstance(step, BridgeCalled)
    assert step.operation == "UnknownOp"
    assert step.args == {"x": 1}
    assert step.mock_return is None


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
