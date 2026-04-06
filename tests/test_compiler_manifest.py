"""
tests/test_compiler_manifest.py — RED stubs for compiler manifest builder (Plan 05.2-03).

Covers:
  - Attribute flattening (D-04): subtype inherits all supertype attributes
  - Generalization cases A/B/C (D-03): transition table inheritance rules
  - Senescent state classifier (D-14): static syntactic analysis
  - Determinism: sorted dicts in DomainManifest output
"""
import pytest


class TestAttributeFlattening:
    def test_subtype_inherits_supertype_attrs(self):
        """Subtype ClassManifest.attributes contains supertype attrs + own attrs (D-04)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")

    def test_name_conflict_subtype_wins(self):
        """When supertype and subtype define same attr, subtype value wins (D-04)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")

    def test_identifier_attrs_flattened(self):
        """identifier_attrs likewise flattened from supertype chain (D-04)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")


class TestGeneralizationCaseA:
    def test_case_a_entity_super_active_sub(self):
        """Case A: entity supertype + active subtype → subtype builds its own transition_table (D-03)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")


class TestGeneralizationCaseB:
    def test_case_b_active_super_active_sub_no_override(self):
        """Case B: active supertype + active subtype (no SM redefinition) → subtype copies supertype transition_table (D-03)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")


class TestGeneralizationCaseC:
    def test_case_c_active_super_active_sub_override(self):
        """Case C: active supertype + active subtype (redefines SM) → subtype builds only from its own SM (D-03)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")


class TestSenescentStateClassifier:
    def test_senescent_state_no_self_generate(self):
        """State with no 'generate ... to self' in entry action classified senescent (D-14)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")

    def test_transient_state_has_self_generate(self):
        """State with any 'generate ... to self' (even guarded) classified transient (D-14)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")

    def test_elevator_senescent_states(self):
        """Elevator class: Idle, Moving, Exchanging are senescent; Departing, Floor_Updating, Arriving are transient."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")


class TestManifestDeterminism:
    def test_transition_table_dicts_sorted_by_key(self):
        """Transition table dict keys are sorted before serialization (D-07)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")

    def test_manifest_json_sorted_keys(self):
        """manifest.json serialized with sort_keys=True (D-07)."""
        pytest.skip("Implemented by Plan 05.2-03 — manifest_builder.py")
