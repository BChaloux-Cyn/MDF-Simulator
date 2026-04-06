"""
tests/test_compiler_elevator.py — Phase 5.2 elevator end-to-end acceptance tests.

SC-07: compile_model on the elevator example completes without errors.
SC-08: two consecutive builds produce sha256-identical bundles (D-07 / D-12).

The elevator model lives at examples/elevator/.design/model/Elevator.
A session-scoped fixture copies it into a tmp directory as a single-domain
model root so load_model's domain-discovery logic finds exactly one domain.

Requirement: MCP-08 — elevator model compiles to a self-contained .mdfbundle.
"""

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from compiler import compile_model

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ELEVATOR_SRC = Path("examples/elevator/.design/model/Elevator")


@pytest.fixture(scope="session")
def elevator_model_root(tmp_path_factory):
    """Session-scoped single-domain model root containing the Elevator domain."""
    if not _ELEVATOR_SRC.exists():
        pytest.skip("Elevator example not available")
    root = tmp_path_factory.mktemp("elevator_model")
    shutil.copytree(_ELEVATOR_SRC, root / "Elevator")
    return root


@pytest.fixture(scope="session")
def elevator_bundle(elevator_model_root, tmp_path_factory):
    """Compile the elevator model once for the whole test session."""
    out = tmp_path_factory.mktemp("elevator_bundle")
    return compile_model(elevator_model_root, out)


# ---------------------------------------------------------------------------
# SC-07: compile_model returns a valid bundle path (no errors)
# ---------------------------------------------------------------------------

def test_elevator_compile_returns_bundle_path(elevator_bundle):
    """compile_model returns a Path with .mdfbundle suffix (SC-07)."""
    assert isinstance(elevator_bundle, Path)
    assert elevator_bundle.suffix == ".mdfbundle"
    assert elevator_bundle.exists()


def test_elevator_compile_no_errors(elevator_bundle):
    """compile_model does not raise any exception on the clean elevator model."""
    # If we got here, compile succeeded — elevator_bundle fixture guarantees it.
    assert elevator_bundle.exists()


# ---------------------------------------------------------------------------
# Bundle structure (D-12)
# ---------------------------------------------------------------------------

def test_elevator_bundle_is_valid_zip(elevator_bundle):
    """The .mdfbundle produced from the elevator model is a valid zip file."""
    assert zipfile.is_zipfile(elevator_bundle), "Bundle is not a valid zip file"


def test_elevator_bundle_contains_bundle_json(elevator_bundle):
    """Bundle contains bundle.json at root."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        assert "bundle.json" in zf.namelist()


def test_elevator_bundle_contains_manifest_json(elevator_bundle):
    """Bundle contains manifest.json at root."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        assert "manifest.json" in zf.namelist()


def test_elevator_bundle_contains_generated_init(elevator_bundle):
    """Bundle contains generated/__init__.py."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        assert "generated/__init__.py" in zf.namelist()


def test_elevator_bundle_contains_all_concrete_classes(elevator_bundle):
    """Bundle contains a generated/<Class>.py for every concrete elevator class."""
    expected_classes = {
        "CarDoor", "DestFloorButton", "Door", "Elevator",
        "Floor", "FloorCallButton", "Shaft", "ShaftDoor", "ShaftFloor",
    }
    with zipfile.ZipFile(elevator_bundle) as zf:
        generated = {
            n.removeprefix("generated/").removesuffix(".py")
            for n in zf.namelist()
            if n.startswith("generated/") and n.endswith(".py") and n != "generated/__init__.py"
        }
    assert expected_classes == generated


# ---------------------------------------------------------------------------
# bundle.json schema (D-02, D-07)
# ---------------------------------------------------------------------------

def test_elevator_bundle_json_required_keys(elevator_bundle):
    """bundle.json has exactly the required metadata keys with no timestamp."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        meta = json.loads(zf.read("bundle.json"))
    required = {"compiler_version", "engine_version", "model_hash", "pycca_version"}
    assert required == set(meta.keys()), f"bundle.json keys mismatch: {set(meta.keys())}"


def test_elevator_bundle_json_no_timestamp(elevator_bundle):
    """bundle.json contains no timestamp or build_time field (D-07)."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        meta = json.loads(zf.read("bundle.json"))
    for bad_key in ("timestamp", "built_at", "created_at", "build_time"):
        assert bad_key not in meta, f"Unexpected timestamp key '{bad_key}' in bundle.json"


def test_elevator_bundle_json_keys_sorted(elevator_bundle):
    """bundle.json keys are in sorted order (D-07)."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        raw = zf.read("bundle.json").decode()
    keys = list(json.loads(raw).keys())
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# manifest.json structural invariants
# ---------------------------------------------------------------------------

def test_elevator_manifest_classes_with_sm(elevator_bundle):
    """manifest.json has transition tables for the expected active classes."""
    expected_active = {"CarDoor", "DestFloorButton", "Elevator", "FloorCallButton", "ShaftDoor"}
    with zipfile.ZipFile(elevator_bundle) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    classes_with_sm = {
        cls for cls, v in manifest["class_defs"].items()
        if v.get("transition_table")
    }
    assert expected_active == classes_with_sm


def test_elevator_manifest_elevator_initial_state(elevator_bundle):
    """Elevator class manifest has initial_state == 'Idle'."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["class_defs"]["Elevator"]["initial_state"] == "Idle"


def test_elevator_manifest_senescent_states(elevator_bundle):
    """Elevator senescent_states == {Idle, Moving, Exchanging} (D-14)."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    actual = set(manifest["class_defs"]["Elevator"]["senescent_states"])
    assert actual == {"Idle", "Moving", "Exchanging"}


def test_elevator_manifest_associations_present(elevator_bundle):
    """manifest.json contains at least one association."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest.get("associations", {})) > 0


# ---------------------------------------------------------------------------
# SC-08: two consecutive builds produce sha256-identical bundles (D-07)
# ---------------------------------------------------------------------------

def test_elevator_compile_deterministic(elevator_model_root, tmp_path):
    """Two consecutive compiles of the elevator model produce identical bundles (SC-08)."""
    bundle1 = compile_model(elevator_model_root, tmp_path / "run1")
    bundle2 = compile_model(elevator_model_root, tmp_path / "run2")
    h1 = hashlib.sha256(bundle1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(bundle2.read_bytes()).hexdigest()
    assert h1 == h2, f"Non-deterministic build: {h1} != {h2}"


# ---------------------------------------------------------------------------
# D-05: generated code readability (automated checks)
# ---------------------------------------------------------------------------

def test_elevator_py_has_source_comment(elevator_bundle):
    """generated/Elevator.py contains a # from <file>:<line> comment (D-05)."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        src = zf.read("generated/Elevator.py").decode()
    assert "# from " in src, "No D-05 source comment found in generated/Elevator.py"


def test_elevator_py_has_transition_table(elevator_bundle):
    """generated/Elevator.py contains a TRANSITION_TABLE dict."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        src = zf.read("generated/Elevator.py").decode()
    assert "TRANSITION_TABLE" in src


def test_elevator_py_valid_python(elevator_bundle):
    """generated/Elevator.py is syntactically valid Python."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        src = zf.read("generated/Elevator.py").decode()
    compile(src, "generated/Elevator.py", "exec")


def test_elevator_py_action_signature(elevator_bundle):
    """generated/Elevator.py action functions use D-10 signature."""
    with zipfile.ZipFile(elevator_bundle) as zf:
        src = zf.read("generated/Elevator.py").decode()
    # Should have at least one action function with the correct sig
    assert 'ctx: "SimulationContext"' in src or "ctx:" in src
