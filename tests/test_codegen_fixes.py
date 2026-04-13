"""tests/test_codegen_fixes.py — Unit tests for the five compiler fixes in 05.3.1-01.

Covers:
  Test 1: Action assignment direction — entry action maps to incoming transitions
  Test 2: Enum emitted for all domain types (not just attribute-referenced)
  Test 3: None enum member escapes Python keyword
  Test 4: Guard sibling transitions both preserved in transition table
  Test 5: Scheduler guard chain selects correct branch
  Test 6: Compile failure emits warning instead of silently swallowing
  Test 7: Elevator full recompile after fixes (integration)
"""
from __future__ import annotations

import os
import shutil
import sys
import warnings
from pathlib import Path

import pytest

from compiler.codegen import _render_enum, generate_class_module
from compiler.manifest_builder import _build_transition_table
from pycca.grammar import STATEMENT_PARSER
from schema.drawio_canonical import CanonicalState, CanonicalStateDiagram, CanonicalTransition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_manifest(
    name: str = "TestClass",
    transition_table: dict | None = None,
    entry_actions: dict | None = None,
) -> dict:
    """Build a minimal ClassManifest dict for codegen tests."""
    return {
        "name": name,
        "is_abstract": False,
        "identifier_attrs": ["id"],
        "attributes": {"id": {"type": "int", "visibility": "public",
                               "scope": "instance", "identifier": [1], "referential": None}},
        "entry_actions": entry_actions or {},
        "initial_state": None,
        "final_states": [],
        "senescent_states": [],
        "transition_table": transition_table or {},
        "supertype": None,
        "subtypes": [],
    }


def _make_sd(states, transitions, initial_state="A") -> CanonicalStateDiagram:
    return CanonicalStateDiagram(
        schema_version="1.0.0",
        type="state_diagram",
        domain="Test",
        **{"class": "Test"},
        initial_state=initial_state,
        events=[],
        states=states,
        transitions=transitions,
    )


# ---------------------------------------------------------------------------
# Test 1: Action assignment direction
# ---------------------------------------------------------------------------

def test_action_assignment_direction_incoming():
    """Entry action for state S maps to transitions incoming to S, not outgoing from S."""
    transition_table = {
        ("Idle", "Go"): [{"next_state": "Moving", "action_fn": None, "guard_fn": None}],
        ("Moving", "Stop"): [{"next_state": "Idle", "action_fn": None, "guard_fn": None}],
    }
    entry_actions = {
        "Moving": "self.x = 1;",
        "Idle": "self.y = 2;",
    }
    manifest = _minimal_manifest(
        transition_table=transition_table,
        entry_actions=entry_actions,
    )
    src = generate_class_module(manifest, {}, STATEMENT_PARSER)

    # Parse the TRANSITION_TABLE by executing the generated module in a sandbox
    # and inspecting the actual dict values directly.
    ns: dict = {}
    exec(src, ns)  # noqa: S102 — generated code in test isolation
    table: dict = ns["TRANSITION_TABLE"]

    idle_go = table[("Idle", "Go")]
    assert len(idle_go) == 1
    assert idle_go[0]["action_fn"] is not None, (
        "('Idle', 'Go') action_fn should be action_Moving_entry callable"
    )
    assert idle_go[0]["action_fn"].__name__ == "action_Moving_entry", (
        f"('Idle', 'Go') action_fn name: {idle_go[0]['action_fn'].__name__!r}"
    )

    moving_stop = table[("Moving", "Stop")]
    assert len(moving_stop) == 1
    assert moving_stop[0]["action_fn"] is not None, (
        "('Moving', 'Stop') action_fn should be action_Idle_entry callable"
    )
    assert moving_stop[0]["action_fn"].__name__ == "action_Idle_entry", (
        f"('Moving', 'Stop') action_fn name: {moving_stop[0]['action_fn'].__name__!r}"
    )

    # action_Moving_entry must NOT be in the ("Moving", "Stop") row
    assert moving_stop[0]["action_fn"].__name__ != "action_Moving_entry", (
        "action_Moving_entry incorrectly assigned to ('Moving', 'Stop') outgoing row"
    )


# ---------------------------------------------------------------------------
# Test 2: Enum emitted for all domain types
# ---------------------------------------------------------------------------

def test_enum_emitted_for_all_domain_types():
    """generate_class_module emits all enums from type_registry, not just attribute-referenced ones."""
    # Class has no attribute referencing Direction
    manifest = _minimal_manifest(
        transition_table={},
        entry_actions={},
    )
    type_registry = {
        "Direction": {"kind": "enum", "members": ["Up", "Down"]},
    }
    src = generate_class_module(manifest, type_registry, STATEMENT_PARSER)
    assert "class Direction(enum.Enum):" in src, (
        "Direction enum not emitted even though it is in type_registry"
    )


# ---------------------------------------------------------------------------
# Test 3: None enum member escapes keyword
# ---------------------------------------------------------------------------

def test_none_enum_member_escapes_keyword():
    """_render_enum escapes Python keyword 'None' to 'None_'."""
    result = _render_enum("Direction", ["Up", "Down", "None"])
    assert "None_ = 'None'" in result, (
        f"Expected 'None_ = ...' in enum output but got:\n{result}"
    )
    # Bare 'None =' assignment would be a syntax error — must not appear
    lines = result.splitlines()
    for line in lines:
        stripped = line.strip()
        assert not (stripped.startswith("None =") or stripped == "None='None'"), (
            f"Bare 'None =' assignment found in enum output: {line!r}"
        )


# ---------------------------------------------------------------------------
# Test 4: Guard sibling transitions both preserved
# ---------------------------------------------------------------------------

def test_guard_sibling_transitions_both_preserved():
    """_build_transition_table preserves both guarded branches for same (state, event)."""
    sd = _make_sd(
        states=[
            CanonicalState(name="Exchanging", entry_action=None),
            CanonicalState(name="Departing", entry_action=None),
            CanonicalState(name="Idle", entry_action=None),
        ],
        transitions=[
            CanonicalTransition(
                from_state="Exchanging", to="Departing", event="Door_closed",
                params=None,
                guard="self.next_stop_floor != self.current_floor",
            ),
            CanonicalTransition(
                from_state="Exchanging", to="Idle", event="Door_closed",
                params=None,
                guard="self.next_stop_floor == self.current_floor",
            ),
        ],
        initial_state="Exchanging",
    )
    table = _build_transition_table(sd)

    key = ("Exchanging", "Door_closed")
    assert key in table, "Expected ('Exchanging', 'Door_closed') key in transition table"
    entries = table[key]
    assert isinstance(entries, list), f"Expected list, got {type(entries)}"
    assert len(entries) == 2, f"Expected 2 entries for guarded siblings, got {len(entries)}"

    next_states = {e["next_state"] for e in entries}
    assert "Departing" in next_states, "Expected 'Departing' entry missing"
    assert "Idle" in next_states, "Expected 'Idle' entry missing"


# ---------------------------------------------------------------------------
# Test 5: Scheduler guard chain selects correct branch
# ---------------------------------------------------------------------------

def test_scheduler_guard_chain_selects_correct_branch():
    """Scheduler picks first guard-passing entry from list-valued transition table."""
    from engine.clock import SimulationClock
    from engine.event import Event
    from engine.microstep import TransitionFired
    from engine.registry import InstanceRegistry
    from engine.scheduler import ThreeQueueScheduler

    def guard_positive(instance, params):
        return instance.get("x", 0) > 0

    def guard_non_positive(instance, params):
        return instance.get("x", 0) <= 0

    class_defs = {
        "Obj": {
            "name": "Obj",
            "is_abstract": False,
            "identifier_attrs": ["oid"],
            "attributes": {"oid": "int", "x": "int"},
            "initial_state": "S1",
            "final_states": [],
            "senescent_states": [],
            "transition_table": {
                ("S1", "E1"): [
                    {"next_state": "S2", "action_fn": None, "guard_fn": guard_positive},
                    {"next_state": "S3", "action_fn": None, "guard_fn": guard_non_positive},
                ],
            },
            "supertype": None,
            "subtypes": [],
        }
    }

    # Run with x=5 → should pick S2 (guard_positive passes first)
    reg = InstanceRegistry(class_defs)
    clock = SimulationClock()
    sched = ThreeQueueScheduler(reg, clock, class_defs)
    reg.create_sync("Obj", {"oid": 1}, initial_state="S1")
    reg.lookup("Obj", {"oid": 1})["x"] = 5
    sched.enqueue(Event(
        event_type="E1",
        sender_class="Obj", sender_id={"oid": 1},
        target_class="Obj", target_id={"oid": 1},
    ))
    steps = list(sched.execute())
    transitions = [s for s in steps if isinstance(s, TransitionFired)]
    assert len(transitions) == 1
    assert transitions[0].to_state == "S2", (
        f"Expected to_state='S2' (x=5 > 0), got {transitions[0].to_state!r}"
    )

    # Run with x=-1 → should pick S3 (guard_positive fails, guard_non_positive passes)
    reg2 = InstanceRegistry(class_defs)
    sched2 = ThreeQueueScheduler(reg2, SimulationClock(), class_defs)
    reg2.create_sync("Obj", {"oid": 2}, initial_state="S1")
    reg2.lookup("Obj", {"oid": 2})["x"] = -1
    sched2.enqueue(Event(
        event_type="E1",
        sender_class="Obj", sender_id={"oid": 2},
        target_class="Obj", target_id={"oid": 2},
    ))
    steps2 = list(sched2.execute())
    transitions2 = [s for s in steps2 if isinstance(s, TransitionFired)]
    assert len(transitions2) == 1
    assert transitions2[0].to_state == "S3", (
        f"Expected to_state='S3' (x=-1 <= 0), got {transitions2[0].to_state!r}"
    )


# ---------------------------------------------------------------------------
# Test 6: Compile failure emits warning
# ---------------------------------------------------------------------------

def test_compile_failure_emits_warning_not_silent():
    """generate_class_module emits UserWarning when action body fails to compile."""
    transition_table = {
        ("Idle", "Go"): [{"next_state": "Active", "action_fn": None, "guard_fn": None}],
    }
    entry_actions = {
        "Active": "!!! invalid pycca syntax !!!",
    }
    manifest = _minimal_manifest(
        transition_table=transition_table,
        entry_actions=entry_actions,
    )
    with pytest.warns(UserWarning, match="Failed to compile action"):
        src = generate_class_module(manifest, {}, STATEMENT_PARSER)

    # Despite compilation failure, action function stub is still generated
    assert "def action_Active_entry" in src


# ---------------------------------------------------------------------------
# Test 7: Elevator recompile integration
# ---------------------------------------------------------------------------

_ELEVATOR_SRC = Path("examples/elevator/.design/model/Elevator")


@pytest.fixture(scope="module")
def elevator_recompile_runtime(tmp_path_factory):
    """Compile the elevator model fresh (after fixes) into an isolated temp dir."""
    if not _ELEVATOR_SRC.exists():
        pytest.skip("Elevator example not available")

    root = tmp_path_factory.mktemp("codegen_fix_runtime")
    model_root = root / ".design" / "model"
    model_root.mkdir(parents=True)
    shutil.copytree(_ELEVATOR_SRC, model_root / "Elevator")

    from compiler import compile_model
    bundles_dir = root / ".design" / "bundles"
    bundles_dir.mkdir(parents=True)
    compile_model(model_root, bundles_dir)

    old_cwd = os.getcwd()
    os.chdir(root)
    try:
        yield root
    finally:
        os.chdir(old_cwd)
        to_remove = [k for k in sys.modules if k.startswith("mdf_generated_")]
        for k in to_remove:
            del sys.modules[k]


def test_elevator_recompile_after_fixes(elevator_recompile_runtime):
    """Verify all five fixes are observable in the compiled elevator output."""
    import zipfile

    root = elevator_recompile_runtime
    bundles_dir = root / ".design" / "bundles"
    bundle_path = next(bundles_dir.glob("elevator.mdfbundle"))

    with zipfile.ZipFile(bundle_path) as zf:
        elevator_src = zf.read("generated/Elevator.py").decode("utf-8")

    # Fix C (enum scoping): Direction enum present in Elevator.py
    assert "class Direction(enum.Enum):" in elevator_src, (
        "Direction enum not emitted in Elevator.py"
    )

    # Fix D (None keyword): Direction enum uses None_ not bare None.
    # black formats string values with double quotes.
    assert 'None_ = "None"' in elevator_src, (
        "None_ escape not found — Direction enum may contain invalid Python syntax"
    )

    # Fix B (action direction) and Fix A (guard siblings):
    # Execute the generated module and inspect TRANSITION_TABLE directly.
    ns: dict = {}
    exec(elevator_src, ns)  # noqa: S102 — generated code in test isolation
    table: dict = ns["TRANSITION_TABLE"]

    # Fix B: ("Idle", "Floor_assigned") → Departing, so action_Departing_entry is on this key
    idle_fa = table.get(("Idle", "Floor_assigned"))
    assert idle_fa is not None, "('Idle', 'Floor_assigned') key missing from TRANSITION_TABLE"
    assert idle_fa[0].get("action_fn") is not None, (
        "action_fn is None for ('Idle', 'Floor_assigned') — action direction fix failed"
    )
    assert idle_fa[0]["action_fn"].__name__ == "action_Departing_entry", (
        f"Expected action_Departing_entry, got {idle_fa[0]['action_fn'].__name__!r}"
    )

    # Fix A: ("Exchanging", "Door_closed") maps to a list with 2 entries
    exch_dc = table.get(("Exchanging", "Door_closed"))
    assert exch_dc is not None, "('Exchanging', 'Door_closed') key missing"
    assert len(exch_dc) == 2, (
        f"Expected 2 guard-sibling entries for ('Exchanging', 'Door_closed'), got {len(exch_dc)}"
    )
    next_states = {e["next_state"] for e in exch_dc}
    assert "Departing" in next_states and "Idle" in next_states, (
        f"Expected Departing and Idle in guard siblings, got {next_states}"
    )

    # Run the scenario to ensure no runtime errors from fix regressions.
    # Resolve fixture paths from the test file location (not from cwd, which is the temp dir).
    from tools.simulation import simulate_domain
    _FIXTURES = Path(__file__).parent / "fixtures"
    _SCENARIO_PATH = str(_FIXTURES / "elevator_multi_floor.scenario.yaml")
    _MOCKS_PATH = str(_FIXTURES / "elevator_multi_floor.mocks.yaml")
    result = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    assert result["errors"] == [], f"Elevator scenario errors after fixes: {result['errors']}"
