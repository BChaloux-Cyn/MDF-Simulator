"""
tests/test_compiler_manifest.py — RED stubs for manifest builder (Plan 03).

These tests are RED until compiler/manifest_builder.py is implemented in Plan 03.
The import of `compiler.manifest_builder` fails because the module does not exist yet.

Coverage targets:
  (a) Attribute flattening (D-04): subtype inherits all supertype attributes; subtype wins on conflict
  (b) Generalization Case A/B/C (D-03): three cases for super/sub active class combinations
  (c) Senescent state classifier (D-14): states with no generate-to-self in entry action
  (d) Determinism: all dict fields are sorted by key before serialization

Requirement: MCP-08 (partial) — manifest builder producing DomainManifest TypedDicts.
"""

import pytest

# ---------------------------------------------------------------------------
# RED sentinel: import fails until Plan 03 creates compiler/manifest_builder.py
# ---------------------------------------------------------------------------
pytest.importorskip(
    "compiler.manifest_builder",
    reason="compiler.manifest_builder not yet implemented (Plan 03)",
)

from compiler.manifest_builder import (  # noqa: E402
    build_class_manifest,
    build_domain_manifest,
    classify_senescent_states,
)


# ---------------------------------------------------------------------------
# (a) Attribute flattening (D-04)
# ---------------------------------------------------------------------------

def test_attribute_flattening_inherits_supertype(minimal_class_diagram):
    """Subtype manifest includes all supertype attributes."""
    domain_manifest = build_domain_manifest(minimal_class_diagram)
    sub = domain_manifest["class_defs"]["SubClass"]
    assert "super_attr" in sub["attributes"]


def test_attribute_flattening_subtype_wins_on_conflict(conflicting_class_diagram):
    """Subtype attribute definition overrides supertype on name conflict."""
    domain_manifest = build_domain_manifest(conflicting_class_diagram)
    sub = domain_manifest["class_defs"]["SubClass"]
    # Subtype's 'shared_attr' wins over supertype's
    assert sub["attributes"]["shared_attr"]["type"] == "int"  # subtype defines as int


def test_attribute_flattening_no_duplicate_entries(minimal_class_diagram):
    """Flattened attributes dict has no duplicate keys."""
    domain_manifest = build_domain_manifest(minimal_class_diagram)
    for cls in domain_manifest["class_defs"].values():
        keys = list(cls["attributes"].keys())
        assert len(keys) == len(set(keys)), f"Duplicates in {cls['name']}.attributes"


# ---------------------------------------------------------------------------
# (b) Generalization Case A / B / C (D-03)
# ---------------------------------------------------------------------------

def test_generalization_case_a_entity_super_active_sub(case_a_diagram):
    """Case A: entity supertype + active subtype — sub builds its own table."""
    domain_manifest = build_domain_manifest(case_a_diagram)
    sub = domain_manifest["class_defs"]["SubClass"]
    assert sub["transition_table"] is not None
    assert sub["initial_state"] is not None


def test_generalization_case_a_super_has_no_table(case_a_diagram):
    """Case A: entity supertype has no transition table of its own."""
    domain_manifest = build_domain_manifest(case_a_diagram)
    super_cls = domain_manifest["class_defs"]["SuperClass"]
    assert not super_cls["transition_table"]


def test_generalization_case_b_active_super_active_sub_no_redefine(case_b_diagram):
    """Case B: active super + active sub (no SM redefinition) — sub copies super table."""
    domain_manifest = build_domain_manifest(case_b_diagram)
    sub = domain_manifest["class_defs"]["SubClass"]
    # Sub's transition table must be derived from super's SM, not sub's own
    assert sub["transition_table"]


def test_generalization_case_c_active_super_active_sub_redefine(case_c_diagram):
    """Case C: active super + active sub (redefines SM) — sub builds from own SM only."""
    domain_manifest = build_domain_manifest(case_c_diagram)
    sub = domain_manifest["class_defs"]["SubClass"]
    # Sub's initial_state comes from sub's own state diagram
    assert sub["initial_state"] == "SubStart"


# ---------------------------------------------------------------------------
# (c) Senescent state classifier (D-14)
# ---------------------------------------------------------------------------

def test_senescent_state_no_self_generate(state_diagram_no_self_gen):
    """States with no generate-to-self in entry action are classified senescent."""
    senescent = classify_senescent_states(state_diagram_no_self_gen)
    assert "Idle" in senescent


def test_senescent_state_with_self_generate_not_classified(state_diagram_with_self_gen):
    """States that generate to self are NOT classified as senescent."""
    senescent = classify_senescent_states(state_diagram_with_self_gen)
    assert "Active" not in senescent  # Active has generate-to-self


def test_senescent_state_no_entry_action(state_diagram_no_entry):
    """States with no entry action at all are classified senescent (no self-generate possible)."""
    senescent = classify_senescent_states(state_diagram_no_entry)
    assert "Waiting" in senescent


def test_senescent_state_conservative_guarded(state_diagram_guarded_gen):
    """States with generate-to-self inside an if guard are still classified non-senescent (conservative)."""
    senescent = classify_senescent_states(state_diagram_guarded_gen)
    # Conservative: any syntactic generate-to-self → non-senescent, even if guarded
    assert "Conditional" not in senescent


def test_senescent_states_result_is_sorted(state_diagram_no_self_gen):
    """classify_senescent_states returns a sorted list (determinism D-07)."""
    result = classify_senescent_states(state_diagram_no_self_gen)
    assert isinstance(result, list)
    assert result == sorted(result)


# ---------------------------------------------------------------------------
# (d) Determinism — sorted dicts
# ---------------------------------------------------------------------------

def test_manifest_attributes_sorted(minimal_class_diagram):
    """Attributes dict in ClassManifest is sorted by key."""
    domain_manifest = build_domain_manifest(minimal_class_diagram)
    for cls in domain_manifest["class_defs"].values():
        keys = list(cls["attributes"].keys())
        assert keys == sorted(keys), f"{cls['name']}.attributes not sorted"


def test_manifest_class_defs_sorted(minimal_class_diagram):
    """class_defs dict in DomainManifest is sorted by class name."""
    domain_manifest = build_domain_manifest(minimal_class_diagram)
    keys = list(domain_manifest["class_defs"].keys())
    assert keys == sorted(keys)


def test_manifest_associations_sorted(minimal_class_diagram):
    """associations dict in DomainManifest is sorted by rel_id."""
    domain_manifest = build_domain_manifest(minimal_class_diagram)
    keys = list(domain_manifest["associations"].keys())
    assert keys == sorted(keys)


def test_manifest_transition_table_sorted(case_a_diagram):
    """transition_table keys are sorted (determinism)."""
    domain_manifest = build_domain_manifest(case_a_diagram)
    for cls in domain_manifest["class_defs"].values():
        if cls["transition_table"]:
            keys = [str(k) for k in cls["transition_table"].keys()]
            assert keys == sorted(keys)


def test_manifest_two_builds_identical(minimal_class_diagram):
    """Two successive builds of the same diagram produce identical manifest dicts."""
    import json
    m1 = build_domain_manifest(minimal_class_diagram)
    m2 = build_domain_manifest(minimal_class_diagram)
    assert json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)
