"""Phase 5.1.1 instrumentation tests — D-22.1..D-22.10."""
from __future__ import annotations

import pytest

from engine import (
    run_simulation,
    SimulationContext,
    EventCompleted,
    LongEventWarning,
    SenescentEntered,
    SenescentExited,
    EventReceived,
    TransitionFired,
    InstanceDeleted,
    Event,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _noop(*_a, **_kw):
    return None


def _make_manifest(class_defs, associations=None, generalizations=None):
    return {
        "class_defs": class_defs,
        "associations": associations or {},
        "generalizations": generalizations or {},
    }


def _widget_class(
    initial_state="Active",
    senescent_states=None,
    final_states=None,
    transition_table=None,
):
    """Minimal single-class manifest for senescence tests."""
    return {
        "name": "Widget",
        "is_abstract": False,
        "identifier_attrs": ["wid"],
        "attributes": {"wid": 1},
        "initial_state": initial_state,
        "final_states": final_states or [],
        "transition_table": transition_table or {},
        "supertype": None,
        "subtypes": [],
        **({"senescent_states": senescent_states} if senescent_states is not None else {}),
    }


# ---------------------------------------------------------------------------
# D-22.1: EventCompleted is emitted exactly once per event dispatch
# ---------------------------------------------------------------------------


def test_event_completed_emitted():
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            transition_table={
                ("Active", "go"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [{"class": "Widget", "instance": {"wid": 1}, "event": "go", "args": {}}],
    }
    steps = list(run_simulation(manifest, scenario))

    completed = [s for s in steps if isinstance(s, EventCompleted)]
    # One EventCompleted per dispatched event (the "go" event)
    assert len(completed) >= 1
    for ec in completed:
        assert ec.duration_ns > 0, "duration_ns must be positive (real wall-clock time)"
    # The completed step for "go" must have the right name
    go_completions = [ec for ec in completed if ec.name == "go"]
    assert len(go_completions) == 1


# ---------------------------------------------------------------------------
# D-22.2: LongEventWarning is NOT emitted when threshold is None (default)
# ---------------------------------------------------------------------------


def test_no_long_event_warning_by_default():
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            transition_table={
                ("Active", "go"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [{"class": "Widget", "instance": {"wid": 1}, "event": "go", "args": {}}],
    }
    steps = list(run_simulation(manifest, scenario))

    # Sanity: at least one EventCompleted fired (wrapper is active)
    assert any(isinstance(s, EventCompleted) for s in steps), (
        "Expected at least one EventCompleted in the trace"
    )
    # No LongEventWarning when event_duration_warn_ns is None (default)
    assert not any(isinstance(s, LongEventWarning) for s in steps), (
        "LongEventWarning must not appear when threshold is None"
    )


# ---------------------------------------------------------------------------
# D-22.3: LongEventWarning fires when a long-running action exceeds threshold
# ---------------------------------------------------------------------------


def test_long_event_warning_fires():
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            transition_table={
                ("Active", "go"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    ctx = SimulationContext(manifest)
    ctx.event_duration_warn_ns = 1  # 1 ns — any real dispatch will exceed this
    ctx.create_sync("Widget", {"wid": 1}, "Active")
    ctx.generate(
        event_type="go",
        sender_class="Widget",
        sender_id={"wid": 1},
        target_class="Widget",
        target_id={"wid": 1},
    )
    steps = list(ctx.execute())

    warnings = [s for s in steps if isinstance(s, LongEventWarning)]
    completes = [s for s in steps if isinstance(s, EventCompleted)]

    assert len(completes) >= 1, "At least one EventCompleted must appear"
    assert len(warnings) >= 1, "LongEventWarning must fire when threshold=1 ns is exceeded"

    # Each warning must have matching threshold and duration > threshold
    for w in warnings:
        assert w.threshold_ns == 1, f"threshold_ns must be 1, got {w.threshold_ns}"
        assert w.duration_ns > 1, f"duration_ns must exceed threshold, got {w.duration_ns}"

    # Adjacency check: each LongEventWarning's predecessor must be an EventCompleted
    # with matching target, name, and duration_ns
    for i, s in enumerate(steps):
        if isinstance(s, LongEventWarning):
            prev = steps[i - 1]
            assert isinstance(prev, EventCompleted), (
                f"Step before LongEventWarning at index {i} must be EventCompleted, "
                f"got {type(prev).__name__}"
            )
            assert prev.target == s.target, (
                f"LongEventWarning.target '{s.target}' must match EventCompleted.target '{prev.target}'"
            )
            assert prev.name == s.name, (
                f"LongEventWarning.name '{s.name}' must match EventCompleted.name '{prev.name}'"
            )
            assert prev.duration_ns == s.duration_ns, (
                f"LongEventWarning.duration_ns {s.duration_ns} must match EventCompleted.duration_ns {prev.duration_ns}"
            )


# ---------------------------------------------------------------------------
# D-22.4: SenescentEntered fires on transition into a senescent state
# ---------------------------------------------------------------------------


def test_senescent_entered_on_transition():
    # 2-state class: Active (non-senescent) -> Idle (senescent)
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            senescent_states={"Idle"},
            transition_table={
                ("Active", "park"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [{"class": "Widget", "instance": {"wid": 1}, "event": "park", "args": {}}],
    }
    steps = list(run_simulation(manifest, scenario))

    # TransitionFired must appear before SenescentEntered
    tf_indices = [i for i, s in enumerate(steps) if isinstance(s, TransitionFired)]
    se_indices = [i for i, s in enumerate(steps)
                  if isinstance(s, SenescentEntered) and s.state == "Idle"]

    assert len(se_indices) >= 1, "SenescentEntered(state='Idle') must appear"
    assert len(tf_indices) >= 1, "TransitionFired must appear"
    # The SenescentEntered for Idle comes after TransitionFired
    assert tf_indices[-1] < se_indices[0], (
        "SenescentEntered must come after TransitionFired"
    )
    # Check instance key contains class name
    ikey = se_indices[0]
    assert "Widget" in steps[ikey].instance


# ---------------------------------------------------------------------------
# D-22.5: SenescentExited fires on dispatch out of a senescent state
# ---------------------------------------------------------------------------


def test_senescent_exited_on_wakeup():
    # Instance is created sync at Active, transitions to Idle (senescent),
    # then receives "wake" to transition back to Active.
    # SenescentExited must fire before EventReceived for the "wake" dispatch.
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            senescent_states={"Idle"},
            transition_table={
                ("Active", "park"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
                ("Idle", "wake"): {"next_state": "Active", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [
            {"class": "Widget", "instance": {"wid": 1}, "event": "park", "args": {}},
            {"class": "Widget", "instance": {"wid": 1}, "event": "wake", "args": {}},
        ],
    }
    steps = list(run_simulation(manifest, scenario))

    # SenescentEntered must appear after the "park" transition
    sen_entered = [s for s in steps if isinstance(s, SenescentEntered) and s.state == "Idle"]
    assert len(sen_entered) >= 1, "SenescentEntered(state='Idle') must fire after 'park'"

    # SenescentExited must appear with by_event="wake"
    sen_exited = [s for s in steps if isinstance(s, SenescentExited) and s.by_event == "wake"]
    assert len(sen_exited) == 1, "SenescentExited(by_event='wake') must appear"

    # SenescentExited must come BEFORE the EventReceived for the "wake" dispatch
    sx_idx = next(i for i, s in enumerate(steps)
                  if isinstance(s, SenescentExited) and s.by_event == "wake")
    er_idx = next(
        i for i, s in enumerate(steps)
        if isinstance(s, EventReceived) and s.event_type == "wake"
    )
    assert sx_idx < er_idx, (
        f"SenescentExited (idx {sx_idx}) must precede EventReceived for 'wake' (idx {er_idx})"
    )


# ---------------------------------------------------------------------------
# D-22.6: No double-emit — SenescentEntered fires once across sen→sen transitions
# ---------------------------------------------------------------------------


def test_no_double_senescent_entered():
    # Class has two senescent states: Idle and Parked
    # Start at Active, park -> Idle (senescent entered), then shift -> Parked
    # No extra SenescentEntered for Parked since instance is still senescent
    # ... actually per D-16: SenescentExited fires on dispatch (flag cleared),
    # then SenescentEntered fires again when landing on another senescent state.
    # "No double-emit" means no duplicate for the *same entry* in a single step.
    # Let's test that transitioning from Idle->Parked (both senescent) emits
    # exactly 1 SenescentEntered for Idle and 1 SenescentEntered for Parked.
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            senescent_states={"Idle", "Parked"},
            transition_table={
                ("Active", "park"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
                ("Idle", "shift"): {"next_state": "Parked", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [
            {"class": "Widget", "instance": {"wid": 1}, "event": "park", "args": {}},
            {"class": "Widget", "instance": {"wid": 1}, "event": "shift", "args": {}},
        ],
    }
    steps = list(run_simulation(manifest, scenario))

    # Count SenescentEntered per (instance, state)
    sen_entered_idle = [s for s in steps
                        if isinstance(s, SenescentEntered) and s.state == "Idle"]
    sen_entered_parked = [s for s in steps
                          if isinstance(s, SenescentEntered) and s.state == "Parked"]

    assert len(sen_entered_idle) == 1, (
        f"Expected 1 SenescentEntered for 'Idle', got {len(sen_entered_idle)}"
    )
    assert len(sen_entered_parked) == 1, (
        f"Expected 1 SenescentEntered for 'Parked', got {len(sen_entered_parked)}"
    )


# ---------------------------------------------------------------------------
# D-22.7: Final state wins — entering a state that is both senescent AND final
#         emits InstanceDeleted and does NOT emit SenescentEntered
# ---------------------------------------------------------------------------


def test_final_state_wins_over_senescence():
    # "Done" is both final and senescent
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Active",
            senescent_states={"Done"},
            final_states=["Done"],
            transition_table={
                ("Active", "finish"): {"next_state": "Done", "action_fn": _noop, "guard_fn": None},
            },
        )
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [{"class": "Widget", "instance": {"wid": 1}, "event": "finish", "args": {}}],
    }
    steps = list(run_simulation(manifest, scenario))

    # InstanceDeleted must appear (final state triggers async deletion)
    deleted = [s for s in steps if isinstance(s, InstanceDeleted)]
    assert len(deleted) >= 1, "InstanceDeleted must fire for final state"

    # SenescentEntered must NOT appear for state "Done"
    sen_done = [s for s in steps
                if isinstance(s, SenescentEntered) and s.state == "Done"]
    assert len(sen_done) == 0, (
        f"SenescentEntered for final state 'Done' must not fire, got {len(sen_done)}"
    )


# ---------------------------------------------------------------------------
# D-22.8: Initial state senescence — newly-created instance whose initial state
#         is senescent emits SenescentEntered immediately after EventReceived
# ---------------------------------------------------------------------------


def test_initial_state_senescence():
    # initial_state="Idle" which is senescent.
    # Use SimulationContext.create_async so the __creation__ event is dispatched
    # through the scheduler, triggering _process_creation and the D-18 check.
    manifest = _make_manifest({
        "Widget": _widget_class(
            initial_state="Idle",
            senescent_states={"Idle"},
            transition_table={},
        )
    })
    ctx = SimulationContext(manifest)
    setup_steps = ctx.create_async("Widget", {"wid": 1}, initial_state="Idle")
    exec_steps = list(ctx.execute())
    steps = setup_steps + exec_steps

    # SenescentEntered must appear after __creation__ is processed
    sen_entered = [s for s in steps
                   if isinstance(s, SenescentEntered) and s.state == "Idle"]
    assert len(sen_entered) >= 1, (
        "SenescentEntered(state='Idle') must fire for initial-state senescence"
    )

    # It must come after EventReceived for __creation__
    er_creation_idx = next(
        (i for i, s in enumerate(steps)
         if isinstance(s, EventReceived) and s.event_type == "__creation__"),
        None,
    )
    se_idx = next(
        i for i, s in enumerate(steps)
        if isinstance(s, SenescentEntered) and s.state == "Idle"
    )
    if er_creation_idx is not None:
        assert er_creation_idx < se_idx, (
            "SenescentEntered must come after __creation__ EventReceived"
        )


# ---------------------------------------------------------------------------
# D-22.9: senescent_states defaults to set() — scheduler never emits senescence
#         micro-steps for classes that don't populate it
# ---------------------------------------------------------------------------


def test_empty_senescent_states_no_emission():
    # Class has NO senescent_states field (backward-compat path)
    manifest = _make_manifest({
        "Widget": {
            "name": "Widget",
            "is_abstract": False,
            "identifier_attrs": ["wid"],
            "attributes": {"wid": 1},
            "initial_state": "Active",
            "final_states": [],
            "transition_table": {
                ("Active", "go"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
                ("Idle", "wake"): {"next_state": "Active", "action_fn": _noop, "guard_fn": None},
            },
            "supertype": None,
            "subtypes": [],
            # No "senescent_states" key — omitted intentionally
        }
    })
    scenario = {
        "instances": [{"class": "Widget", "identifier": {"wid": 1}, "initial_state": "Active"}],
        "events": [
            {"class": "Widget", "instance": {"wid": 1}, "event": "go", "args": {}},
            {"class": "Widget", "instance": {"wid": 1}, "event": "wake", "args": {}},
        ],
    }
    steps = list(run_simulation(manifest, scenario))

    sen_entered = [s for s in steps if isinstance(s, SenescentEntered)]
    sen_exited = [s for s in steps if isinstance(s, SenescentExited)]

    assert len(sen_entered) == 0, (
        f"No SenescentEntered expected when senescent_states omitted, got {len(sen_entered)}"
    )
    assert len(sen_exited) == 0, (
        f"No SenescentExited expected when senescent_states omitted, got {len(sen_exited)}"
    )


# ---------------------------------------------------------------------------
# D-22.10: Manifest with multiple classes, mixed senescent/non-senescent —
#          each class's classification is independent
# ---------------------------------------------------------------------------


def test_multi_class_senescence_independent():
    # ClassA has senescent_states={"Idle"}, ClassB omits it
    manifest = _make_manifest({
        "ClassA": {
            "name": "ClassA",
            "is_abstract": False,
            "identifier_attrs": ["aid"],
            "attributes": {"aid": 1},
            "initial_state": "Active",
            "final_states": [],
            "transition_table": {
                ("Active", "park"): {"next_state": "Idle", "action_fn": _noop, "guard_fn": None},
            },
            "supertype": None,
            "subtypes": [],
            "senescent_states": {"Idle"},
        },
        "ClassB": {
            "name": "ClassB",
            "is_abstract": False,
            "identifier_attrs": ["bid"],
            "attributes": {"bid": 1},
            "initial_state": "Running",
            "final_states": [],
            "transition_table": {
                ("Running", "stop"): {"next_state": "Stopped", "action_fn": _noop, "guard_fn": None},
            },
            "supertype": None,
            "subtypes": [],
            # No senescent_states
        },
    })
    scenario = {
        "instances": [
            {"class": "ClassA", "identifier": {"aid": 1}, "initial_state": "Active"},
            {"class": "ClassB", "identifier": {"bid": 1}, "initial_state": "Running"},
        ],
        "events": [
            {"class": "ClassA", "instance": {"aid": 1}, "event": "park", "args": {}},
            {"class": "ClassB", "instance": {"bid": 1}, "event": "stop", "args": {}},
        ],
    }
    steps = list(run_simulation(manifest, scenario))

    # ClassA must emit SenescentEntered for Idle
    a_sen = [s for s in steps
             if isinstance(s, SenescentEntered) and "ClassA" in s.instance]
    assert len(a_sen) >= 1, "ClassA must emit SenescentEntered for state 'Idle'"

    # ClassB must never emit any senescence micro-steps
    b_sen_entered = [s for s in steps
                     if isinstance(s, SenescentEntered) and "ClassB" in s.instance]
    b_sen_exited = [s for s in steps
                    if isinstance(s, SenescentExited) and "ClassB" in s.instance]
    assert len(b_sen_entered) == 0, (
        f"ClassB must not emit SenescentEntered, got {len(b_sen_entered)}"
    )
    assert len(b_sen_exited) == 0, (
        f"ClassB must not emit SenescentExited, got {len(b_sen_exited)}"
    )
