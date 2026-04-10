"""
tests/test_simulation_runner.py — Bundle loader, scenario schema, and preflight tests.

Phase 05.3-03: Bundle loader (Task 1) + scenario schema + preflight (Task 2).

Coverage:
  Task 1: ENGINE_VERSION, load_bundle, key reversal, callable rebinding, version
          mismatch rejection, path traversal rejection.
  Task 2: ScenarioDef schema validation, EventDef constraints, preflight multiplicity.
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
