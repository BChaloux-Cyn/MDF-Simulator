"""
tests/test_simulation_runner.py — Bundle loader, scenario schema, preflight,
trigger evaluator, and scenario runner tests.

Phase 05.3-03: Bundle loader (Task 1) + scenario schema + preflight (Task 2).
Phase 05.3-04: TriggerEvaluator + run_scenario (Task 1).

Coverage:
  05.3-03 Task 1: ENGINE_VERSION, load_bundle, key reversal, callable rebinding, version
          mismatch rejection, path traversal rejection.
  05.3-03 Task 2: ScenarioDef schema validation, EventDef constraints, preflight multiplicity.
  05.3-04 Task 1: TriggerEvaluator fires/disarms, attr+state match, run_scenario alias resolution.
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Shared session-scoped elevator bundle fixture
# ---------------------------------------------------------------------------

_ELEVATOR_SRC = Path("examples/elevator/.design/model/Elevator")


@pytest.fixture(scope="session")
def elevator_model_root(tmp_path_factory):
    """Session-scoped single-domain model root for the Elevator domain."""
    if not _ELEVATOR_SRC.exists():
        pytest.skip("Elevator example not available")
    root = tmp_path_factory.mktemp("sim_runner_elevator_model")
    shutil.copytree(_ELEVATOR_SRC, root / "Elevator")
    return root


@pytest.fixture(scope="session")
def elevator_bundle_path(elevator_model_root, tmp_path_factory):
    """Compile the elevator model once for the whole session."""
    from compiler import compile_model

    out = tmp_path_factory.mktemp("sim_runner_elevator_bundle")
    return compile_model(elevator_model_root, out)


@pytest.fixture(autouse=False)
def cleanup_generated_modules():
    """Remove mdf_generated_* entries from sys.modules after each test.

    Prevents Windows temp-dir cleanup failures (RESEARCH.md Pitfall 5).
    """
    yield
    to_remove = [k for k in sys.modules if k.startswith("mdf_generated_")]
    for k in to_remove:
        del sys.modules[k]


# ---------------------------------------------------------------------------
# Task 1: ENGINE_VERSION
# ---------------------------------------------------------------------------


def test_engine_version_constant_exists():
    """engine.ENGINE_VERSION is defined and equals '0.1.0'."""
    import engine

    assert engine.ENGINE_VERSION == "0.1.0"


def test_engine_version_matches_compiler_version():
    """engine.ENGINE_VERSION matches compiler.COMPILER_VERSION."""
    import engine
    from compiler import COMPILER_VERSION

    assert engine.ENGINE_VERSION == COMPILER_VERSION


# ---------------------------------------------------------------------------
# Task 1: BundleLoader — module-level imports exist
# ---------------------------------------------------------------------------


def test_bundle_loader_module_importable():
    """engine.bundle_loader module is importable."""
    from engine import bundle_loader  # noqa: F401


def test_bundle_loader_exports_load_bundle():
    """engine.bundle_loader exposes load_bundle callable."""
    from engine.bundle_loader import load_bundle

    assert callable(load_bundle)


def test_bundle_loader_exports_bundle_version_error():
    """engine.bundle_loader exposes BundleVersionError."""
    from engine.bundle_loader import BundleVersionError

    assert issubclass(BundleVersionError, Exception)


def test_bundle_loader_exports_bundle_corrupt_error():
    """engine.bundle_loader exposes BundleCorruptError."""
    from engine.bundle_loader import BundleCorruptError

    assert issubclass(BundleCorruptError, Exception)


# ---------------------------------------------------------------------------
# Task 1: load_bundle — real elevator bundle
# ---------------------------------------------------------------------------


def test_bundle_loader_extracts_and_verifies_version(elevator_bundle_path, cleanup_generated_modules):
    """load_bundle returns a (manifest, tmpdir) tuple and manifest has class_defs."""
    from engine.bundle_loader import load_bundle

    manifest, tmpdir = load_bundle(elevator_bundle_path)
    try:
        assert isinstance(manifest, dict)
        assert "class_defs" in manifest
        assert len(manifest["class_defs"]) > 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_bundle_loader_reverses_state_event_keys(elevator_bundle_path, cleanup_generated_modules):
    """After load_bundle, transition_table keys are (state, event) tuples, not strings."""
    from engine.bundle_loader import load_bundle

    manifest, tmpdir = load_bundle(elevator_bundle_path)
    try:
        for cls_name, cls_def in manifest["class_defs"].items():
            tt = cls_def.get("transition_table", {})
            for key in tt:
                assert isinstance(key, tuple), (
                    f"{cls_name}: transition_table key {key!r} should be a tuple"
                )
                assert len(key) == 2, (
                    f"{cls_name}: transition_table key {key!r} should be (state, event)"
                )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_bundle_loader_rebinds_transition_table_callables(elevator_bundle_path, cleanup_generated_modules):
    """After load_bundle, at least one TransitionEntry has a non-None action_fn."""
    from engine.bundle_loader import load_bundle

    manifest, tmpdir = load_bundle(elevator_bundle_path)
    try:
        found_callable = False
        for cls_name, cls_def in manifest["class_defs"].items():
            for key, entry in cls_def.get("transition_table", {}).items():
                if entry.get("action_fn") is not None:
                    assert callable(entry["action_fn"]), (
                        f"{cls_name} {key}: action_fn is set but not callable"
                    )
                    found_callable = True
        assert found_callable, (
            "No callable action_fn found in any transition entry — rebinding failed"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_bundle_loader_hard_fails_on_version_mismatch(elevator_bundle_path, cleanup_generated_modules, monkeypatch):
    """load_bundle raises BundleVersionError when engine_version mismatches."""
    import engine.bundle_loader as bl
    from engine.bundle_loader import BundleVersionError, load_bundle

    # Monkeypatch ENGINE_VERSION inside bundle_loader to simulate a mismatch
    monkeypatch.setattr(bl, "ENGINE_VERSION", "9.9.9")
    with pytest.raises(BundleVersionError) as exc_info:
        manifest, tmpdir = load_bundle(elevator_bundle_path)
        shutil.rmtree(tmpdir, ignore_errors=True)
    message = str(exc_info.value)
    assert "0.1.0" in message, f"Expected bundle version '0.1.0' in error, got: {message}"
    assert "9.9.9" in message, f"Expected engine version '9.9.9' in error, got: {message}"


def test_bundle_loader_rejects_path_traversal(tmp_path, cleanup_generated_modules):
    """load_bundle raises BundleCorruptError when zip contains a path traversal entry."""
    from engine.bundle_loader import BundleCorruptError, load_bundle

    # Build a minimal bundle with a traversal entry
    bundle_path = tmp_path / "evil.mdfbundle"
    bundle_json = json.dumps({"engine_version": "0.1.0"})
    manifest_json = json.dumps({"class_defs": {}, "associations": {}, "generalizations": {}})
    with zipfile.ZipFile(bundle_path, "w") as zf:
        zf.writestr("bundle.json", bundle_json)
        zf.writestr("manifest.json", manifest_json)
        zf.writestr("../evil.py", "# path traversal payload")

    with pytest.raises(BundleCorruptError):
        manifest, tmpdir = load_bundle(bundle_path)
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Task 2: ScenarioDef schema
# ---------------------------------------------------------------------------


def test_scenario_schema_valid_yaml_parses():
    """ScenarioDef validates minimal.scenario.yaml and returns expected shape."""
    import yaml
    from schema.scenario_schema import ScenarioDef

    with open("tests/fixtures/minimal.scenario.yaml") as f:
        data = yaml.safe_load(f)
    scn = ScenarioDef.model_validate(data)
    assert len(scn.instances) == 1
    assert len(scn.relationships) == 0
    assert len(scn.events) == 1
    assert len(scn.triggers) == 0
    assert scn.events[0].sender == "elev1"


def test_scenario_schema_missing_sender_rejected():
    """EventDef without sender raises ValidationError."""
    from pydantic import ValidationError
    from schema.scenario_schema import ScenarioDef

    with pytest.raises(ValidationError):
        ScenarioDef.model_validate({"events": [{"event": "X", "target": "a"}]})


def test_scenario_schema_at_ms_after_ms_mutually_exclusive():
    """EventDef with both at_ms and after_ms raises ValidationError."""
    from pydantic import ValidationError
    from schema.scenario_schema import ScenarioDef

    with pytest.raises(ValidationError):
        ScenarioDef.model_validate(
            {"events": [{"event": "X", "target": "a", "sender": "a", "at_ms": 1, "after_ms": 2}]}
        )


def test_scenario_schema_event_or_call_required():
    """EventDef with neither event nor call raises ValidationError."""
    from pydantic import ValidationError
    from schema.scenario_schema import ScenarioDef

    with pytest.raises(ValidationError):
        ScenarioDef.model_validate({"events": [{"target": "a", "sender": "a"}]})


# ---------------------------------------------------------------------------
# Task 2: Preflight multiplicity check
# ---------------------------------------------------------------------------


def test_preflight_passes_valid_population():
    """check_multiplicity returns empty list when no violations exist."""
    from engine.preflight import check_multiplicity
    from schema.scenario_schema import ScenarioDef

    scn = ScenarioDef(instances=[], relationships=[], events=[], triggers=[])
    issues = check_multiplicity(scn, {"associations": {}})
    assert issues == []


def test_preflight_rejects_missing_required_multiplicity():
    """check_multiplicity returns issues when a required 1..1 link is absent."""
    from engine.preflight import check_multiplicity
    from schema.scenario_schema import InstanceDef, ScenarioDef

    scn = ScenarioDef(
        instances=[InstanceDef(**{"class": "Elevator", "name": "e1", "id": {"elevator_id": 1}})],
        relationships=[],
        events=[],
        triggers=[],
    )
    manifest = {
        "associations": {
            "R1": {
                "rel_id": "R1",
                "class_a": "Elevator",
                "class_b": "Shaft",
                "mult_a_to_b": "1",
                "mult_b_to_a": "1",
            }
        }
    }
    issues = check_multiplicity(scn, manifest)
    assert len(issues) >= 1
    assert "R1" in issues[0].location


# ---------------------------------------------------------------------------
# Phase 05.3-04 Task 1: TriggerEvaluator
# ---------------------------------------------------------------------------

def _make_fake_instance(class_name: str, identifier: dict, state: str, **attrs) -> dict:
    """Build a minimal instance dict that mimics what the registry produces."""
    from engine.event import make_instance_key
    inst = dict(attrs)
    inst.update(identifier)
    inst["curr_state"] = state
    inst["__class_name__"] = class_name
    inst["__instance_key__"] = make_instance_key(identifier)
    return inst


def _make_minimal_manifest(class_name: str = "Elevator") -> dict:
    """Build a minimal manifest for use in unit tests (no real transitions needed)."""
    return {
        "class_defs": {
            class_name: {
                "name": class_name,
                "identifier_attrs": ["elevator_id"],
                "initial_state": "Idle",
                "transition_table": {},
                "attributes": {},
            }
        },
        "associations": {},
        "generalizations": {},
    }


def test_trigger_fires_on_state_match():
    """TriggerEvaluator fires trigger when instance is in specified state."""
    from schema.scenario_schema import TriggerCondition, TriggerAction, TriggerDef
    from engine.trigger import TriggerEvaluator

    e1 = _make_fake_instance("Elevator", {"elevator_id": 1}, "Idle")
    aliases = {"e1": e1}
    trig = TriggerDef(
        when=TriggerCondition(instance="e1", state="Idle"),
        then=TriggerAction(event="X", target="e1", sender="e1"),
        repeat=False,
    )
    evaluator = TriggerEvaluator([trig], aliases)

    # Create a minimal fake ctx (trigger reads inst["curr_state"] directly)
    class FakeCtx:
        pass

    fired = evaluator.evaluate(FakeCtx())
    assert len(fired) == 1
    assert fired[0] is trig


def test_trigger_disarms_after_first_fire_when_repeat_false():
    """Trigger with repeat=False fires once, then is disarmed."""
    from schema.scenario_schema import TriggerCondition, TriggerAction, TriggerDef
    from engine.trigger import TriggerEvaluator

    e1 = _make_fake_instance("Elevator", {"elevator_id": 1}, "Idle")
    aliases = {"e1": e1}
    trig = TriggerDef(
        when=TriggerCondition(instance="e1", state="Idle"),
        then=TriggerAction(event="X", target="e1", sender="e1"),
        repeat=False,
    )
    evaluator = TriggerEvaluator([trig], aliases)

    class FakeCtx:
        pass

    fired1 = evaluator.evaluate(FakeCtx())
    fired2 = evaluator.evaluate(FakeCtx())
    assert len(fired1) == 1
    assert len(fired2) == 0


def test_trigger_rearms_when_repeat_true():
    """Trigger with repeat=True fires every time the condition is met."""
    from schema.scenario_schema import TriggerCondition, TriggerAction, TriggerDef
    from engine.trigger import TriggerEvaluator

    e1 = _make_fake_instance("Elevator", {"elevator_id": 1}, "Idle")
    aliases = {"e1": e1}
    trig = TriggerDef(
        when=TriggerCondition(instance="e1", state="Idle"),
        then=TriggerAction(event="X", target="e1", sender="e1"),
        repeat=True,
    )
    evaluator = TriggerEvaluator([trig], aliases)

    class FakeCtx:
        pass

    fired1 = evaluator.evaluate(FakeCtx())
    fired2 = evaluator.evaluate(FakeCtx())
    assert len(fired1) == 1
    assert len(fired2) == 1


def test_trigger_fires_on_attr_eq_match():
    """Trigger fires only when instance attribute equals specified value."""
    from schema.scenario_schema import TriggerCondition, TriggerAction, TriggerDef
    from engine.trigger import TriggerEvaluator

    e1 = _make_fake_instance("Elevator", {"elevator_id": 1}, "Moving", current_floor=2)
    aliases = {"e1": e1}
    trig = TriggerDef(
        when=TriggerCondition(instance="e1", attr="current_floor", eq=2),
        then=TriggerAction(event="ArrivalSignal", target="e1", sender="e1"),
        repeat=False,
    )
    evaluator = TriggerEvaluator([trig], aliases)

    class FakeCtx:
        pass

    # Matches (current_floor == 2)
    fired = evaluator.evaluate(FakeCtx())
    assert len(fired) == 1

    # Simulate floor change, re-arm manually
    e1["current_floor"] = 3
    evaluator.armed[0].armed = True  # manually re-arm to confirm attr check is independent
    fired2 = evaluator.evaluate(FakeCtx())
    assert len(fired2) == 0


def test_trigger_both_state_and_attr_must_match():
    """Trigger with state+attr requires both conditions (AND logic, D-19)."""
    from schema.scenario_schema import TriggerCondition, TriggerAction, TriggerDef
    from engine.trigger import TriggerEvaluator

    e1 = _make_fake_instance("Elevator", {"elevator_id": 1}, "Idle", current_floor=1)
    aliases = {"e1": e1}
    trig = TriggerDef(
        when=TriggerCondition(instance="e1", state="Idle", attr="current_floor", eq=2),
        then=TriggerAction(event="X", target="e1", sender="e1"),
        repeat=False,
    )
    evaluator = TriggerEvaluator([trig], aliases)

    class FakeCtx:
        pass

    # State matches but attr does not (current_floor=1, want 2)
    fired = evaluator.evaluate(FakeCtx())
    assert len(fired) == 0

    # Both match now
    e1["current_floor"] = 2
    fired2 = evaluator.evaluate(FakeCtx())
    assert len(fired2) == 1


def test_trigger_fire_limit_raises_on_exceed():
    """TriggerEvaluator raises RuntimeError after exceeding TRIGGER_FIRE_LIMIT fires."""
    from schema.scenario_schema import TriggerCondition, TriggerAction, TriggerDef
    from engine.trigger import TriggerEvaluator, TRIGGER_FIRE_LIMIT

    e1 = _make_fake_instance("Elevator", {"elevator_id": 1}, "Idle")
    aliases = {"e1": e1}
    trig = TriggerDef(
        when=TriggerCondition(instance="e1", state="Idle"),
        then=TriggerAction(event="X", target="e1", sender="e1"),
        repeat=True,  # infinite loop candidate
    )
    evaluator = TriggerEvaluator([trig], aliases)
    # Manually set total_fires to just below the limit
    evaluator.total_fires = TRIGGER_FIRE_LIMIT

    class FakeCtx:
        pass

    with pytest.raises(RuntimeError, match="Trigger fire limit"):
        evaluator.evaluate(FakeCtx())


def test_run_scenario_yields_micro_steps_and_resolves_aliases():
    """run_scenario yields micro-steps from ctx.execute() after setup."""
    from engine.ctx import SimulationContext
    from engine.scenario_runner import run_scenario
    from schema.scenario_schema import ScenarioDef, InstanceDef, EventDef

    manifest = _make_minimal_manifest("Elevator")
    # Add a transition so the scheduler can process the event
    manifest["class_defs"]["Elevator"]["transition_table"] = {
        ("Idle", "Floor_assigned"): {
            "to_state": "Departing",
            "action_fn": None,
            "guard_fn": None,
        }
    }

    scenario = ScenarioDef(
        instances=[
            InstanceDef(**{"class": "Elevator", "name": "elev1", "id": {"elevator_id": 1}, "state": "Idle"})
        ],
        relationships=[],
        events=[
            EventDef(event="Floor_assigned", target="elev1", sender="elev1", args={"floor_num": 3})
        ],
        triggers=[],
    )

    ctx = SimulationContext(manifest)
    steps = list(run_scenario(ctx, scenario, manifest))
    assert len(steps) > 0
    # The instance should have been created (aliases resolved)
    inst = ctx.registry.lookup("Elevator", {"elevator_id": 1})
    assert inst is not None
