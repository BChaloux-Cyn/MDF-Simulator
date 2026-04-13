"""Elevator scenario integration tests (Phase 05.3.1-02).

Verifies that all 5 elevator scenarios execute end-to-end without errors
and produce the expected state transitions. Uses the compile-once module
fixture pattern from test_simulation_e2e.py.

Coverage:
  - Scenario 1: Door open/close cycle (CarDoor + ShaftDoor)
  - Scenario 2: Direct floor travel (Floor_assigned -> Idle)
  - Scenario 3: Button-triggered travel (FloorCallButton Lit -> Floor_assigned)
  - Scenario 4: Full end-to-end (button press + travel + door cycle)
  - Scenario 5: Passenger round-trip (single travel + door cycle)
  - All scenarios: no ErrorMicroStep in any trace
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared fixture: compile elevator model once per test module
# ---------------------------------------------------------------------------

_ELEVATOR_SRC = Path("examples/elevator/.design/model/Elevator")
_MOCKS = str(Path("tests/fixtures/elevator_scenarios.mocks.yaml").resolve())


@pytest.fixture(scope="module")
def elevator_runtime(tmp_path_factory):
    """Compile elevator model into an isolated temp dir; chdir into it.

    Yields the root Path. Restores cwd after the module finishes.
    """
    if not _ELEVATOR_SRC.exists():
        pytest.skip("Elevator example not available")

    root = tmp_path_factory.mktemp("scenario_runtime")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_scenario(scenario_filename: str) -> dict:
    """Run a scenario by filename (looked up relative to original cwd)."""
    from tools.simulation import simulate_domain
    path = str(Path(__file__).parent / "fixtures" / scenario_filename)
    return simulate_domain("Elevator", path, mocks=_MOCKS)


def _get_transitions(result: dict) -> list[dict]:
    """Extract transition_fired records from the trace file."""
    trace = json.loads(Path(result["trace_file"]).read_text())
    return [s for s in trace if s.get("type") == "transition_fired"]


def _get_errors(result: dict) -> list[dict]:
    """Extract ErrorMicroStep records from the trace file (type field is 'error')."""
    trace = json.loads(Path(result["trace_file"]).read_text())
    return [s for s in trace if s.get("type") == "error"]


# ---------------------------------------------------------------------------
# Scenario 1: Door Open/Close Cycle
# ---------------------------------------------------------------------------

def test_scenario_1_door_cycle(elevator_runtime):
    """Door cycle: CarDoor and ShaftDoor both complete Open->Close sequence."""
    result = _run_scenario("elevator_scenario_1_door_cycle.scenario.yaml")
    assert result["errors"] == [], f"Tool-level errors: {result['errors']}"

    trace_errors = _get_errors(result)
    assert trace_errors == [], f"ErrorMicroSteps in trace: {trace_errors}"

    transitions = _get_transitions(result)
    to_states = [t["to_state"] for t in transitions]

    # CarDoor must cycle through all states
    car_door_transitions = [t for t in transitions if t.get("class_name") == "CarDoor"]
    car_states = [t["to_state"] for t in car_door_transitions]
    for state in ["Opening", "Open", "Closing", "Closed"]:
        assert state in car_states, f"CarDoor missing state {state!r} in {car_states}"

    # Final CarDoor state must be Closed
    assert car_door_transitions[-1]["to_state"] == "Closed", (
        f"CarDoor did not return to Closed; last state: {car_door_transitions[-1]['to_state']}"
    )

    # ShaftDoor must also cycle
    shaft_door_transitions = [t for t in transitions if t.get("class_name") == "ShaftDoor"]
    shaft_states = [t["to_state"] for t in shaft_door_transitions]
    for state in ["Opening", "Open", "Closing", "Closed"]:
        assert state in shaft_states, f"ShaftDoor missing state {state!r} in {shaft_states}"


# ---------------------------------------------------------------------------
# Scenario 2: Direct Floor Travel
# ---------------------------------------------------------------------------

def test_scenario_2_direct_travel(elevator_runtime):
    """Direct travel: Floor_assigned -> full Elevator travel cycle -> Idle."""
    result = _run_scenario("elevator_scenario_2_direct_travel.scenario.yaml")
    assert result["errors"] == [], f"Tool-level errors: {result['errors']}"

    trace_errors = _get_errors(result)
    assert trace_errors == [], f"ErrorMicroSteps in trace: {trace_errors}"

    transitions = _get_transitions(result)
    elev_transitions = [t for t in transitions if t.get("class_name") == "Elevator"]
    elev_states = [t["to_state"] for t in elev_transitions]

    # Full travel path must be present
    for state in ["Departing", "Moving", "Floor_Updating", "Arriving", "Exchanging", "Idle"]:
        assert state in elev_states, (
            f"Elevator missing state {state!r} in path: {elev_states}"
        )

    # Elevator must end at Idle
    assert elev_transitions[-1]["to_state"] == "Idle", (
        f"Elevator did not end at Idle; last state: {elev_transitions[-1]['to_state']}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: Button-Triggered Travel
# ---------------------------------------------------------------------------

def test_scenario_3_button_travel(elevator_runtime):
    """Button travel: FloorCallButton Activated -> Lit entry -> Elevator travel."""
    result = _run_scenario("elevator_scenario_3_button_travel.scenario.yaml")
    assert result["errors"] == [], f"Tool-level errors: {result['errors']}"

    trace_errors = _get_errors(result)
    assert trace_errors == [], f"ErrorMicroSteps in trace: {trace_errors}"

    transitions = _get_transitions(result)

    # FloorCallButton must reach Lit
    fcb_transitions = [t for t in transitions if t.get("class_name") == "FloorCallButton"]
    fcb_states = [t["to_state"] for t in fcb_transitions]
    assert "Lit" in fcb_states, f"FloorCallButton never reached Lit; states: {fcb_states}"

    # Elevator must complete travel
    elev_transitions = [t for t in transitions if t.get("class_name") == "Elevator"]
    elev_states = [t["to_state"] for t in elev_transitions]
    assert "Departing" in elev_states, f"Elevator never departed; states: {elev_states}"
    assert "Idle" in elev_states, f"Elevator never reached Idle; states: {elev_states}"


# ---------------------------------------------------------------------------
# Scenario 4: Full End-to-End
# ---------------------------------------------------------------------------

def test_scenario_4_full_e2e(elevator_runtime):
    """Full E2E: button press + travel + door cycle all complete without errors."""
    result = _run_scenario("elevator_scenario_4_full_e2e.scenario.yaml")
    assert result["errors"] == [], f"Tool-level errors: {result['errors']}"

    trace_errors = _get_errors(result)
    assert trace_errors == [], f"ErrorMicroSteps in trace: {trace_errors}"

    transitions = _get_transitions(result)
    to_states = {t["to_state"] for t in transitions}

    # Must see travel states
    assert "Departing" in to_states, "Missing travel state: Departing"
    assert "Moving" in to_states, "Missing travel state: Moving"
    # Must see door cycle states
    assert "Opening" in to_states, "Missing door state: Opening"
    assert "Open" in to_states, "Missing door state: Open"
    assert "Closing" in to_states, "Missing door state: Closing"
    # Must end at Idle
    assert "Idle" in to_states, "Missing final state: Idle"


# ---------------------------------------------------------------------------
# Scenario 5: Passenger Round-Trip
# ---------------------------------------------------------------------------

def test_scenario_5_round_trip(elevator_runtime):
    """Round-trip: button at floor 3 -> travel to floor 3 -> door cycle -> Idle."""
    result = _run_scenario("elevator_scenario_5_round_trip.scenario.yaml")
    assert result["errors"] == [], f"Tool-level errors: {result['errors']}"

    trace_errors = _get_errors(result)
    assert trace_errors == [], f"ErrorMicroSteps in trace: {trace_errors}"

    transitions = _get_transitions(result)
    elev_transitions = [t for t in transitions if t.get("class_name") == "Elevator"]
    elev_states = [t["to_state"] for t in elev_transitions]

    # Must travel (Departing at least once)
    assert "Departing" in elev_states, f"Elevator never departed; states: {elev_states}"
    # Must arrive and exchange
    assert "Exchanging" in elev_states, f"Elevator never reached Exchanging; states: {elev_states}"
    # Must end at Idle
    assert elev_transitions[-1]["to_state"] == "Idle", (
        f"Elevator did not end at Idle; last state: {elev_transitions[-1]['to_state']}"
    )


# ---------------------------------------------------------------------------
# All scenarios: no ErrorMicroStep
# ---------------------------------------------------------------------------

def test_all_scenarios_no_error_microsteps(elevator_runtime):
    """None of the 5 scenarios produce ErrorMicroStep entries in the trace."""
    scenarios = [
        "elevator_scenario_1_door_cycle.scenario.yaml",
        "elevator_scenario_2_direct_travel.scenario.yaml",
        "elevator_scenario_3_button_travel.scenario.yaml",
        "elevator_scenario_4_full_e2e.scenario.yaml",
        "elevator_scenario_5_round_trip.scenario.yaml",
    ]
    for i, name in enumerate(scenarios, 1):
        result = _run_scenario(name)
        assert result["errors"] == [], (
            f"Scenario {i} ({name}) has tool-level errors: {result['errors']}"
        )
        trace_errors = _get_errors(result)
        assert trace_errors == [], (
            f"Scenario {i} ({name}) has ErrorMicroStep entries: {trace_errors}"
        )
