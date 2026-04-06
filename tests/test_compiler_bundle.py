"""
tests/test_compiler_bundle.py — Codegen, packager, and bundle tests (Plan 04).

Coverage targets:
  (a) Bundle layout matches D-12: bundle.json, manifest.json, generated/__init__.py, generated/<Class>.py
  (b) Two consecutive builds produce identical zip bytes (D-07 determinism)
  (c) bundle.json contains no timestamp field
  (d) Zip entries are written in sorted order
  (e) generate_class_module: valid Python, correct signatures, TRANSITION_TABLE, D-05 comments
  (f) format_source: black formatting, error handling

Requirement: MCP-08 (partial) — .mdfbundle zip packaging with deterministic output.
"""

import json
import zipfile
from pathlib import Path
import pytest

from compiler.packager import write_bundle  # noqa: E402
from compiler.codegen import generate_class_module, generate_init_module, format_source
from compiler.error import CompilationFailed
from pycca.grammar import STATEMENT_PARSER


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_bundle_inputs():
    """Minimal set of inputs for write_bundle: one class file, minimal manifest."""
    files = {
        "Elevator": (
            "from __future__ import annotations\n\n"
            "def action_Idle_entry(ctx, self_dict, params):\n    pass\n"
        ),
    }
    manifest = {
        "class_defs": {
            "Elevator": {
                "name": "Elevator",
                "is_abstract": False,
                "identifier_attrs": ["id"],
                "attributes": {"id": {"type": "int"}, "floor": {"type": "int"}},
                "initial_state": "Idle",
                "final_states": [],
                "transition_table": {},
                "supertype": None,
                "subtypes": [],
            }
        },
        "associations": {},
        "generalizations": {},
    }
    return {
        "domain_name": "elevator",
        "files": files,
        "manifest": manifest,
        "engine_version": "0.1.0",
        "pycca_version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# (a) Bundle layout matches D-12
# ---------------------------------------------------------------------------

def test_bundle_contains_bundle_json(tmp_path, minimal_bundle_inputs):
    """Bundle zip contains bundle.json at root."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        assert "bundle.json" in zf.namelist()


def test_bundle_contains_manifest_json(tmp_path, minimal_bundle_inputs):
    """Bundle zip contains manifest.json at root."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        assert "manifest.json" in zf.namelist()


def test_bundle_contains_generated_init(tmp_path, minimal_bundle_inputs):
    """Bundle zip contains generated/__init__.py."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        assert "generated/__init__.py" in zf.namelist()


def test_bundle_contains_class_file(tmp_path, minimal_bundle_inputs):
    """Bundle zip contains generated/<ClassName>.py for each compiled class."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        assert "generated/Elevator.py" in zf.namelist()


def test_bundle_filename_matches_d12(tmp_path, minimal_bundle_inputs):
    """Bundle file is named <domain_name>.mdfbundle (D-12)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    assert bundle_path.name == "elevator.mdfbundle"


def test_bundle_returns_path(tmp_path, minimal_bundle_inputs):
    """write_bundle returns a Path pointing to the created file."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    assert isinstance(bundle_path, Path)
    assert bundle_path.exists()


# ---------------------------------------------------------------------------
# (b) Two consecutive builds produce identical zip bytes (D-07)
# ---------------------------------------------------------------------------

def test_two_builds_identical_bytes(tmp_path, minimal_bundle_inputs):
    """Two consecutive bundle builds produce byte-for-byte identical zip files."""
    path1 = write_bundle(output_dir=tmp_path / "build1", **minimal_bundle_inputs)
    path2 = write_bundle(output_dir=tmp_path / "build2", **minimal_bundle_inputs)
    assert path1.read_bytes() == path2.read_bytes(), (
        "Bundle is non-deterministic: two builds produced different bytes"
    )


def test_two_builds_identical_zip_entries(tmp_path, minimal_bundle_inputs):
    """Two builds have the same zip entry list in the same order."""
    path1 = write_bundle(output_dir=tmp_path / "build1", **minimal_bundle_inputs)
    path2 = write_bundle(output_dir=tmp_path / "build2", **minimal_bundle_inputs)
    with zipfile.ZipFile(path1) as z1, zipfile.ZipFile(path2) as z2:
        assert z1.namelist() == z2.namelist()


# ---------------------------------------------------------------------------
# (c) bundle.json contains no timestamps
# ---------------------------------------------------------------------------

def test_bundle_json_no_timestamp(tmp_path, minimal_bundle_inputs):
    """bundle.json must not contain a 'timestamp' or 'built_at' field (D-07)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        meta = json.loads(zf.read("bundle.json"))
    assert "timestamp" not in meta
    assert "built_at" not in meta
    assert "created_at" not in meta


def test_bundle_json_has_required_fields(tmp_path, minimal_bundle_inputs):
    """bundle.json contains engine_version, pycca_version, model_hash (D-02)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        meta = json.loads(zf.read("bundle.json"))
    assert "engine_version" in meta
    assert "pycca_version" in meta
    assert "model_hash" in meta


def test_bundle_json_sorted_keys(tmp_path, minimal_bundle_inputs):
    """bundle.json keys are sorted (D-07 — no timestamp, deterministic hash)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        raw = zf.read("bundle.json").decode()
    meta = json.loads(raw)
    keys = list(meta.keys())
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# (d) Zip entries written in sorted order
# ---------------------------------------------------------------------------

def test_zip_entries_sorted_order(tmp_path, minimal_bundle_inputs):
    """Zip entry names are in sorted order (D-07 — deterministic writes)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        names = zf.namelist()
    # bundle.json and manifest.json first, then sorted generated/ entries
    generated = [n for n in names if n.startswith("generated/") and n != "generated/__init__.py"]
    assert generated == sorted(generated)


def test_zip_bundle_json_is_first_entry(tmp_path, minimal_bundle_inputs):
    """bundle.json is the first entry in the zip (by convention)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.namelist()[0] == "bundle.json"


def test_zip_manifest_json_is_second_entry(tmp_path, minimal_bundle_inputs):
    """manifest.json is the second entry in the zip (by convention)."""
    bundle_path = write_bundle(output_dir=tmp_path, **minimal_bundle_inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.namelist()[1] == "manifest.json"


def test_zip_multiple_classes_sorted(tmp_path, minimal_bundle_inputs):
    """Multiple generated class files appear in sorted alphabetical order."""
    inputs = dict(minimal_bundle_inputs)
    inputs["files"] = {
        "Zebra": "# zebra\n",
        "Apple": "# apple\n",
        "Mango": "# mango\n",
    }
    bundle_path = write_bundle(output_dir=tmp_path, **inputs)
    with zipfile.ZipFile(bundle_path) as zf:
        generated = [n for n in zf.namelist() if n.startswith("generated/") and n != "generated/__init__.py"]
    assert generated == ["generated/Apple.py", "generated/Mango.py", "generated/Zebra.py"]


# ---------------------------------------------------------------------------
# (e) generate_class_module codegen tests (D-10, D-05, D-07)
# ---------------------------------------------------------------------------

from schema.drawio_canonical import CanonicalClassEntry, CanonicalStateDiagram, CanonicalState, CanonicalTransition


def _minimal_class_manifest(name: str = "Light") -> dict:
    """Minimal ClassManifest dict for codegen tests."""
    return {
        "name": name,
        "is_abstract": False,
        "identifier_attrs": ["id"],
        "attributes": {"id": {"type": "int", "visibility": "public", "scope": "instance",
                               "identifier": [1], "referential": None}},
        "entry_actions": {
            "Off": None,
            "On": "self.brightness = 100;",
        },
        "initial_state": "Off",
        "final_states": [],
        "senescent_states": ["Off"],
        "transition_table": {
            ("Off", "Toggle"): {"next_state": "On", "action_fn": None, "guard_fn": None},
            ("On", "Toggle"): {"next_state": "Off", "action_fn": None, "guard_fn": None},
        },
        "supertype": None,
        "subtypes": [],
    }


def test_generate_class_module_valid_python():
    """generate_class_module returns parseable Python source."""
    src = generate_class_module(_minimal_class_manifest(), {}, STATEMENT_PARSER)
    # Must compile without SyntaxError
    compile(src, "<test>", "exec")


def test_generate_class_module_has_transition_table():
    """Generated module contains a TRANSITION_TABLE dict."""
    src = generate_class_module(_minimal_class_manifest(), {}, STATEMENT_PARSER)
    assert "TRANSITION_TABLE" in src


def test_generate_class_module_action_signature():
    """Action function signature matches D-10."""
    src = generate_class_module(_minimal_class_manifest(), {}, STATEMENT_PARSER)
    # At least one action function for states with entry actions
    assert 'def action_On_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:' in src


def test_generate_class_module_d05_comment():
    """Every generated file has a # from <file>:<line> header comment (D-05)."""
    src = generate_class_module(_minimal_class_manifest(), {}, STATEMENT_PARSER, source_file="model/Light.yaml")
    assert "# from model/Light.yaml:0" in src


def test_generate_class_module_transition_table_sorted():
    """TRANSITION_TABLE keys appear in sorted (state, event) order."""
    src = generate_class_module(_minimal_class_manifest(), {}, STATEMENT_PARSER)
    # ('Off', 'Toggle') should appear before ('On', 'Toggle') alphabetically
    off_pos = src.index("'Off'")
    on_pos = src.index("'On'")
    # The TRANSITION_TABLE section starts after action functions
    table_pos = src.index("TRANSITION_TABLE")
    off_in_table = src.index("'Off'", table_pos)
    on_in_table = src.index("'On'", table_pos)
    assert off_in_table < on_in_table


def test_generate_class_module_enum_rendered():
    """Enum types in type_registry are rendered as enum.Enum subclasses."""
    manifest = _minimal_class_manifest()
    manifest["attributes"] = {"status": {"type": "Status", "visibility": "public",
                                          "scope": "instance", "identifier": None, "referential": None}}
    type_registry = {"Status": {"kind": "enum", "members": ["Active", "Idle"]}}
    src = generate_class_module(manifest, type_registry, STATEMENT_PARSER)
    assert "class Status(enum.Enum):" in src
    assert "'Active'" in src or '"Active"' in src


def test_generate_class_module_typedef_rendered():
    """Typedef types in type_registry are rendered as NewType statements."""
    manifest = _minimal_class_manifest()
    manifest["attributes"] = {"floor_num": {"type": "FloorNum", "visibility": "public",
                                              "scope": "instance", "identifier": None, "referential": None}}
    type_registry = {"FloorNum": {"kind": "typedef", "base": "int"}}
    src = generate_class_module(manifest, type_registry, STATEMENT_PARSER)
    assert "NewType" in src
    assert "FloorNum" in src


def test_generate_class_module_entity_no_sm():
    """Entity class with no SM emits empty TRANSITION_TABLE."""
    manifest = {
        "name": "Building",
        "is_abstract": False,
        "identifier_attrs": ["id"],
        "attributes": {},
        "entry_actions": {},
        "initial_state": None,
        "final_states": [],
        "senescent_states": [],
        "transition_table": {},
        "supertype": None,
        "subtypes": [],
    }
    src = generate_class_module(manifest, {}, STATEMENT_PARSER)
    compile(src, "<test>", "exec")
    assert "TRANSITION_TABLE: dict = {}" in src


# ---------------------------------------------------------------------------
# (f) format_source tests
# ---------------------------------------------------------------------------

def test_format_source_idempotent():
    """format_source twice on same input is idempotent."""
    src = "x = 1\n"
    once = format_source(src)
    twice = format_source(once)
    assert once == twice


def test_format_source_invalid_raises_compile_error():
    """format_source raises CompileError on syntactically invalid Python."""
    bad = "def (:"
    with pytest.raises(CompilationFailed):
        format_source(bad, filename="bad.py")


def test_format_source_returns_string():
    """format_source always returns a string."""
    result = format_source("x=1\n")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# generate_init_module
# ---------------------------------------------------------------------------

def test_generate_init_module_sorted_imports():
    """generate_init_module imports class modules in sorted order."""
    manifest = {
        "class_defs": {"Zebra": {}, "Apple": {}, "Mango": {}},
        "associations": {},
        "generalizations": {},
    }
    src = generate_init_module(manifest)
    apple_pos = src.index("Apple")
    mango_pos = src.index("Mango")
    zebra_pos = src.index("Zebra")
    assert apple_pos < mango_pos < zebra_pos


def test_generate_init_module_valid_python():
    """generate_init_module returns parseable Python."""
    manifest = {
        "class_defs": {"Elevator": {}, "Floor": {}},
        "associations": {},
        "generalizations": {},
    }
    src = generate_init_module(manifest)
    compile(src, "<test>", "exec")
