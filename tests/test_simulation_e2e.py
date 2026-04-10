"""
tests/test_simulation_e2e.py — simulate_domain / simulate_class MCP tool tests
and elevator end-to-end verification.

Phase 05.3-04, Task 2.

Coverage:
  - simulate_domain returns correct dict shape
  - Trace file written with JSON list content
  - simulate_class isolated single-class simulation
  - Engine version mismatch surfaced as structured error entry
  - Elevator multi-floor scenario compiles, loads, runs
  - Key transition milestones present in trace
  - Two sequential runs produce identical micro-step streams (determinism)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_ELEVATOR_SRC = Path("examples/elevator/.design/model/Elevator")


@pytest.fixture(scope="module")
def elevator_runtime(tmp_path_factory):
    """Compile elevator into an isolated temp dir; chdir into it for the module.

    Yields the root Path. Restores cwd after the module finishes.
    """
    if not _ELEVATOR_SRC.exists():
        pytest.skip("Elevator example not available")

    root = tmp_path_factory.mktemp("e2e_runtime")
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


_SCENARIO_PATH = str(Path("tests/fixtures/elevator_multi_floor.scenario.yaml").resolve())
_MOCKS_PATH = str(Path("tests/fixtures/elevator_multi_floor.mocks.yaml").resolve())


# ---------------------------------------------------------------------------
# Unit-level tests: simulate_domain result shape
# ---------------------------------------------------------------------------

def test_simulate_domain_returns_result_dict_shape(elevator_runtime):
    """simulate_domain returns a dict with total_steps, final_instance_states, errors, trace_file."""
    from tools.simulation import simulate_domain

    result = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert set(result.keys()) == {"total_steps", "final_instance_states", "errors", "trace_file"}, (
        f"Missing or extra keys: {result.keys()}"
    )
    assert isinstance(result["total_steps"], int)
    assert isinstance(result["final_instance_states"], dict)
    assert isinstance(result["errors"], list)
    assert isinstance(result["trace_file"], str)


def test_simulate_domain_writes_trace_file(elevator_runtime):
    """simulate_domain writes a trace file that exists and contains a JSON list."""
    from tools.simulation import simulate_domain

    result = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    trace_path = Path(result["trace_file"])
    assert trace_path.exists(), f"Trace file not found: {trace_path}"
    content = json.loads(trace_path.read_text())
    assert isinstance(content, list), "Trace file must contain a JSON list"


def test_simulate_class_returns_result_dict_shape(elevator_runtime):
    """simulate_class returns the same dict shape as simulate_domain."""
    from tools.simulation import simulate_class

    result = simulate_class("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"total_steps", "final_instance_states", "errors", "trace_file"}


def test_simulate_domain_version_mismatch_is_structured_error(elevator_runtime, monkeypatch):
    """Engine version mismatch surfaces as error entry, not uncaught exception."""
    import engine.bundle_loader as bl
    from tools.simulation import simulate_domain

    monkeypatch.setattr(bl, "ENGINE_VERSION", "9.9.9")
    result = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    assert isinstance(result, dict), "Must return dict even on version mismatch"
    assert len(result["errors"]) >= 1
    error_types = [e["type"] for e in result["errors"]]
    assert "BundleVersionError" in error_types, f"Expected BundleVersionError in {error_types}"


# ---------------------------------------------------------------------------
# E2E tests: elevator multi-floor scenario
# ---------------------------------------------------------------------------

def test_elevator_compiles_and_runs_multi_floor_scenario(elevator_runtime):
    """Elevator multi-floor scenario runs to completion without errors."""
    from tools.simulation import simulate_domain

    result = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    assert result["errors"] == [], f"Unexpected errors: {result['errors']}"
    assert result["total_steps"] > 0, "Expected at least one micro-step"


def test_elevator_key_transition_milestones_present(elevator_runtime):
    """Trace contains expected key transition milestones (D-23: presence, not exact order)."""
    from tools.simulation import simulate_domain

    result = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    assert result["errors"] == [], f"Errors prevent milestone check: {result['errors']}"

    trace = json.loads(Path(result["trace_file"]).read_text())
    transitions = [s for s in trace if s.get("type") == "transition_fired"]
    to_states = {t.get("to_state") for t in transitions}

    # Elevator goes Arriving -> Exchanging (on Arrived) -> Idle (on Door_closed)
    expected = {"Exchanging", "Idle"}
    assert expected.issubset(to_states), (
        f"Missing key milestones: {expected - to_states}. "
        f"All to_states seen: {to_states}"
    )


def test_elevator_determinism_two_runs_identical(elevator_runtime):
    """Two sequential runs of the same scenario produce identical micro-step streams."""
    from tools.simulation import simulate_domain

    r1 = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)
    r2 = simulate_domain("Elevator", _SCENARIO_PATH, mocks=_MOCKS_PATH)

    assert r1["errors"] == [], f"Run 1 errors: {r1['errors']}"
    assert r2["errors"] == [], f"Run 2 errors: {r2['errors']}"

    def _strip_ts(records):
        """Remove timestamp field from records for comparison."""
        return [{k: v for k, v in r.items() if k != "timestamp"} for r in records]

    t1 = _strip_ts(json.loads(Path(r1["trace_file"]).read_text()))
    t2 = _strip_ts(json.loads(Path(r2["trace_file"]).read_text()))
    assert t1 == t2, f"Traces differ: run1 has {len(t1)} steps, run2 has {len(t2)} steps"
