"""tests/test_codegen_fixes.py — Unit tests for 5 compiler fixes from plan 05.3.1-03.

Tests:
  1. test_enum_emitted_for_all_domain_types        — unconditional enum emission (D-06)
  2. test_none_enum_member_skipped_not_escaped      — Python keyword skip in _render_enum
  3. test_action_assignment_direction_incoming      — entry action on DESTINATION state
  4. test_guard_sibling_transitions_both_preserved  — list accumulation in manifest_builder
  5. test_scheduler_guard_chain_selects_correct_branch — guard chain dispatch in scheduler
  6. test_compile_failure_emits_warning             — warnings.warn on action/guard failure
"""
from __future__ import annotations

import pytest

from compiler.codegen import _render_enum, generate_class_module
from compiler.manifest_builder import _build_transition_table
from schema.drawio_canonical import (
    CanonicalState,
    CanonicalStateDiagram,
    CanonicalTransition,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _minimal_manifest(
    name: str = "TestClass",
    entry_actions: dict | None = None,
    transition_table: dict | None = None,
    attributes: dict | None = None,
) -> dict:
    return {
        "name": name,
        "is_abstract": False,
        "identifier_attrs": [],
        "attributes": attributes or {},
        "entry_actions": entry_actions or {},
        "initial_state": None,
        "final_states": [],
        "senescent_states": [],
        "transition_table": transition_table or {},
        "supertype": None,
        "subtypes": [],
    }


def _make_sd(
    class_name: str,
    states: list[CanonicalState],
    transitions: list[CanonicalTransition],
    initial_state: str = "Idle",
) -> CanonicalStateDiagram:
    return CanonicalStateDiagram(
        type="state_diagram",
        domain="Test",
        **{"class": class_name},
        initial_state=initial_state,
        states=states,
        transitions=transitions,
    )


# ---------------------------------------------------------------------------
# Test 1: Unconditional enum emission
# ---------------------------------------------------------------------------


def test_enum_emitted_for_all_domain_types():
    """Enum in type_registry is emitted even if no attribute references it (D-06)."""
    # manifest has no attributes referencing "Direction" at all
    manifest = _minimal_manifest(
        attributes={"id": {"type": "int", "visibility": "private", "scope": "instance",
                           "identifier": [1], "referential": None}},
    )
    type_registry = {"Direction": {"kind": "enum", "members": ["Up", "Down"]}}
    src = generate_class_module(manifest, type_registry, None)
    assert "class Direction(enum.Enum):" in src


# ---------------------------------------------------------------------------
# Test 2: None enum member is skipped (Python keyword — cannot be assignment target)
# ---------------------------------------------------------------------------


def test_none_enum_member_skipped_not_escaped():
    """_render_enum skips 'None' (Python keyword); Up and Down are emitted."""
    src = _render_enum("Direction", ["Up", "Down", "None"])
    # Python keyword must be absent as an enum member assignment
    assert "    None = 'None'" not in src
    # Valid members must be present
    assert "Up = 'Up'" in src
    assert "Down = 'Down'" in src


# ---------------------------------------------------------------------------
# Test 3: Entry action assigned to DESTINATION state (incoming transition)
# ---------------------------------------------------------------------------


def test_action_assignment_direction_incoming():
    """Entry action for Moving fires on (Idle, Go) — the transition INTO Moving."""
    transition_table = {
        ("Idle", "Go"): [{"next_state": "Moving", "action_fn": None, "guard_fn": None}],
        ("Moving", "Stop"): [{"next_state": "Idle", "action_fn": None, "guard_fn": None}],
    }
    entry_actions = {
        "Moving": "generate Arrived to self;",
        "Idle": "generate Done to self;",
    }
    manifest = _minimal_manifest(
        entry_actions=entry_actions,
        transition_table=transition_table,
    )
    src = generate_class_module(manifest, {}, None)

    # Locate TRANSITION_TABLE section
    table_pos = src.index("TRANSITION_TABLE")
    table_src = src[table_pos:]

    # ("Idle", "Go") → entry action for DESTINATION state Moving fires on this transition
    idle_go_pos = table_src.index("('Idle', 'Go')")
    idle_go_block_end = table_src.index("],", idle_go_pos)
    idle_go_block = table_src[idle_go_pos:idle_go_block_end]
    assert "action_Moving_entry" in idle_go_block, (
        f"Expected action_Moving_entry near ('Idle', 'Go') block:\n{idle_go_block}"
    )

    # ("Moving", "Stop") → entry action for DESTINATION state Idle fires on this transition
    moving_stop_pos = table_src.index("('Moving', 'Stop')")
    moving_stop_block_end = table_src.index("],", moving_stop_pos)
    moving_stop_block = table_src[moving_stop_pos:moving_stop_block_end]
    assert "action_Idle_entry" in moving_stop_block, (
        f"Expected action_Idle_entry near ('Moving', 'Stop') block:\n{moving_stop_block}"
    )


# ---------------------------------------------------------------------------
# Test 4: Guard sibling transitions both preserved in transition table
# ---------------------------------------------------------------------------


def test_guard_sibling_transitions_both_preserved():
    """Two transitions from same (state, event) are stored as a list of 2 entries."""
    sd = _make_sd(
        class_name="Elevator",
        states=[
            CanonicalState(name="Exchanging", entry_action=None),
            CanonicalState(name="Departing", entry_action=None),
            CanonicalState(name="Idle", entry_action=None),
        ],
        transitions=[
            CanonicalTransition(
                **{"from": "Exchanging"},
                to="Departing",
                event="Door_closed",
                params=None,
                guard="self_dict['next_stop_floor'] != self_dict['current_floor']",
            ),
            CanonicalTransition(
                **{"from": "Exchanging"},
                to="Idle",
                event="Door_closed",
                params=None,
                guard="self_dict['next_stop_floor'] == self_dict['current_floor']",
            ),
        ],
        initial_state="Exchanging",
    )
    table = _build_transition_table(sd)

    assert ("Exchanging", "Door_closed") in table, (
        "Key ('Exchanging', 'Door_closed') missing from transition table"
    )
    entries = table[("Exchanging", "Door_closed")]
    assert isinstance(entries, list), f"Expected list, got {type(entries)}"
    assert len(entries) == 2, f"Expected 2 sibling entries, got {len(entries)}"

    next_states = {e["next_state"] for e in entries}
    assert "Departing" in next_states
    assert "Idle" in next_states


# ---------------------------------------------------------------------------
# Test 5: Scheduler guard chain selects the correct branch
# ---------------------------------------------------------------------------


def test_scheduler_guard_chain_selects_correct_branch():
    """ThreeQueueScheduler picks the first entry whose guard returns True."""
    from engine.clock import SimulationClock
    from engine.event import Event
    from engine.microstep import TransitionFired
    from engine.registry import InstanceRegistry
    from engine.scheduler import ThreeQueueScheduler

    class_defs = {
        "Widget": {
            "name": "Widget",
            "is_abstract": False,
            "identifier_attrs": ["wid"],
            "attributes": {"wid": "int"},
            "initial_state": "S1",
            "final_states": [],
            "entry_actions": {},
            "senescent_states": [],
            "transition_table": {
                ("S1", "E1"): [
                    {
                        "next_state": "S2",
                        "action_fn": None,
                        "guard_fn": lambda sd, p: sd.get("x", 0) > 0,
                    },
                    {
                        "next_state": "S3",
                        "action_fn": None,
                        "guard_fn": lambda sd, p: sd.get("x", 0) <= 0,
                    },
                ]
            },
            "supertype": None,
            "subtypes": [],
        }
    }

    def _run(x_val: int) -> list:
        reg = InstanceRegistry(class_defs)
        clock = SimulationClock()
        sched = ThreeQueueScheduler(reg, clock, class_defs)
        reg.create_sync("Widget", {"wid": 1}, initial_state="S1", attrs={"x": x_val})
        sched.enqueue(Event(
            event_type="E1",
            sender_class="Widget", sender_id={"wid": 1},
            target_class="Widget", target_id={"wid": 1},
        ))
        return list(sched.execute())

    # x=5 → x > 0 is True → should go to S2
    steps_pos = _run(5)
    transitions_pos = [s for s in steps_pos if isinstance(s, TransitionFired)]
    assert len(transitions_pos) == 1, f"Expected 1 TransitionFired, got {transitions_pos}"
    assert transitions_pos[0].to_state == "S2", (
        f"Expected S2 for x=5, got {transitions_pos[0].to_state}"
    )

    # x=-1 → x > 0 is False, x <= 0 is True → should go to S3
    steps_neg = _run(-1)
    transitions_neg = [s for s in steps_neg if isinstance(s, TransitionFired)]
    assert len(transitions_neg) == 1, f"Expected 1 TransitionFired, got {transitions_neg}"
    assert transitions_neg[0].to_state == "S3", (
        f"Expected S3 for x=-1, got {transitions_neg[0].to_state}"
    )


# ---------------------------------------------------------------------------
# Test 6: Compile failure emits UserWarning (action and guard paths)
# ---------------------------------------------------------------------------


def test_compile_failure_emits_warning():
    """generate_class_module emits UserWarning on action or guard compile failure."""

    # Part A: action body that fails to parse
    manifest_action = _minimal_manifest(
        entry_actions={"Broken": "!!! invalid syntax !!!"},
        transition_table={
            ("Idle", "Go"): [{"next_state": "Broken", "action_fn": None, "guard_fn": None}],
        },
    )
    with pytest.warns(UserWarning, match="Failed to compile action"):
        src_action = generate_class_module(manifest_action, {}, None)
    # The function should still be emitted (with pass body)
    assert "def action_Broken_entry" in src_action

    # Part B: guard expression that fails to parse
    manifest_guard = _minimal_manifest(
        transition_table={
            ("Idle", "Go"): [{"next_state": "Active", "action_fn": None,
                              "guard_fn": "!!! invalid guard !!!"}],
        },
    )
    with pytest.warns(UserWarning, match="Failed to compile guard"):
        generate_class_module(manifest_guard, {}, None)
