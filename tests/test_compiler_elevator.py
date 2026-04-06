"""
tests/test_compiler_elevator.py — RED stub for elevator end-to-end compile (Plan 05).

This test is RED until compiler/__init__.py implements compile_model() in Plan 05.
The import of `compiler` fails because the module does not exist yet.

Coverage target:
  - compile_model(Path("examples/elevator"), tmp_path) returns a .mdfbundle path
  - The bundle is a valid zip file (loadable without error)

Requirement: MCP-08 (partial) — elevator model compiles to a self-contained bundle.
"""

import zipfile
from pathlib import Path
import pytest

# ---------------------------------------------------------------------------
# RED sentinel: import fails until Plan 05 creates compiler/__init__.py
# ---------------------------------------------------------------------------
pytest.importorskip(
    "compiler",
    reason="compiler package not yet implemented (Plan 05)",
)

from compiler import compile_model  # noqa: E402


# ---------------------------------------------------------------------------
# Elevator end-to-end compile
# ---------------------------------------------------------------------------

def test_elevator_compile_returns_bundle_path(tmp_path):
    """compile_model returns a Path with .mdfbundle suffix."""
    model_root = Path("examples/elevator")
    result = compile_model(model_root, tmp_path)
    assert isinstance(result, Path)
    assert result.suffix == ".mdfbundle"
    assert result.exists()


def test_elevator_bundle_is_valid_zip(tmp_path):
    """The .mdfbundle produced from the elevator model is a valid zip file."""
    model_root = Path("examples/elevator")
    bundle_path = compile_model(model_root, tmp_path)
    assert zipfile.is_zipfile(bundle_path), "Bundle is not a valid zip file"


def test_elevator_bundle_contains_required_entries(tmp_path):
    """Elevator bundle contains bundle.json, manifest.json, and generated/ files."""
    model_root = Path("examples/elevator")
    bundle_path = compile_model(model_root, tmp_path)
    with zipfile.ZipFile(bundle_path) as zf:
        names = set(zf.namelist())
    assert "bundle.json" in names
    assert "manifest.json" in names
    assert "generated/__init__.py" in names
    # At least one class file must be generated
    generated_files = [n for n in names if n.startswith("generated/") and n.endswith(".py")]
    assert len(generated_files) >= 1


def test_elevator_compile_no_errors(tmp_path):
    """compile_model does not raise any exception on the clean elevator model."""
    model_root = Path("examples/elevator")
    # Must not raise CompileError or any other exception
    compile_model(model_root, tmp_path)


def test_elevator_compile_deterministic(tmp_path):
    """Two consecutive compiles of the elevator model produce identical bundles."""
    model_root = Path("examples/elevator")
    bundle1 = compile_model(model_root, tmp_path / "run1")
    bundle2 = compile_model(model_root, tmp_path / "run2")
    assert bundle1.read_bytes() == bundle2.read_bytes(), (
        "Elevator compile is non-deterministic across runs"
    )
