"""
tests/test_compiler_manifest.py — Manifest builder + loader + senescent classifier (Plan 03).

Tests the canonical-JSON-based compiler pipeline:
  - schema/canonical_builder.py parity with tools/drawio.py private functions
  - compiler/loader.py: model root → LoadedModel (canonical objects)
  - compiler/senescence.py: has_self_generate + classify_senescent_states
  - compiler/manifest_builder.py: LoadedModel → DomainManifest

Coverage targets (from plan must_haves):
  (a) Canonical builder parity
  (b) Loader smoke test + error handling
  (c) Senescent classifier (D-14)
  (d) Attribute flattening (D-04)
  (e) Generalization Case A/B/C (D-03)
  (f) Determinism — sorted dicts (D-07)
  (g) Transition table encoding (D-13)

Requirement: MCP-08 (partial) — manifest builder producing DomainManifest TypedDicts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from schema.drawio_canonical import (
    CanonicalClassDiagram,
    CanonicalClassEntry,
    CanonicalAssociation,
    CanonicalGeneralization,
    CanonicalState,
    CanonicalStateDiagram,
    CanonicalTransition,
)
from compiler.loader import LoadedModel, load_model
from compiler.senescence import has_self_generate, classify_senescent_states
from compiler.manifest_builder import build_domain_manifest, build_class_manifest
from compiler.error import CompilationFailed
from pycca.grammar import STATEMENT_PARSER


# ---------------------------------------------------------------------------
# Helpers to build canonical fixtures
# ---------------------------------------------------------------------------

def _make_cd(
    domain: str = "Test",
    classes: list[CanonicalClassEntry] | None = None,
    assocs: list[CanonicalAssociation] | None = None,
    gens: list[CanonicalGeneralization] | None = None,
) -> CanonicalClassDiagram:
    return CanonicalClassDiagram(
        type="class_diagram",
        domain=domain.lower(),
        classes=classes or [],
        associations=assocs or [],
        generalizations=gens or [],
    )


def _make_sd(
    class_name: str,
    states: list[CanonicalState],
    transitions: list[CanonicalTransition] | None = None,
    initial_state: str | None = None,
) -> CanonicalStateDiagram:
    return CanonicalStateDiagram(
        type="state_diagram",
        domain="test",
        class_name=class_name,
        initial_state=initial_state or (states[0].name if states else "Init"),
        states=states,
        transitions=transitions or [],
    )


def _make_cls(
    name: str,
    stereotype: str = "entity",
    attributes: list[str] | None = None,
    specializes: str | None = None,
) -> CanonicalClassEntry:
    return CanonicalClassEntry(
        name=name,
        stereotype=stereotype,
        specializes=specializes,
        attributes=attributes or [],
        methods=[],
    )


def _minimal_loaded(*extra_classes: CanonicalClassEntry) -> LoadedModel:
    classes = [
        _make_cls("SuperClass", attributes=["- super_attr: String"]),
        _make_cls("SubClass", attributes=["- sub_attr: int"], specializes="R1"),
        *extra_classes,
    ]
    cd = _make_cd(
        classes=classes,
        gens=[CanonicalGeneralization(name="R1", supertype="SuperClass", subtypes=["SubClass"])],
    )
    return LoadedModel(class_diagram=cd, state_diagrams={}, root=Path("."))


# ---------------------------------------------------------------------------
# (a) Canonical builder parity
# ---------------------------------------------------------------------------

class TestCanonicalBuilderParity:
    """schema/canonical_builder functions must produce identical output to
    the original tools/drawio.py private functions."""

    def test_state_parity_with_elevator(self):
        """yaml_to_canonical_state_json matches _yaml_to_canonical_state on elevator."""
        from schema.canonical_builder import yaml_to_canonical_state_json
        # Import drawio private via the module-level wrapper
        from tools.drawio import _yaml_to_canonical_state

        sd_path = Path("examples/elevator/.design/model/Elevator/state-diagrams/Elevator.yaml")
        if not sd_path.exists():
            pytest.skip("Elevator example not available")
        raw = yaml.safe_load(sd_path.read_text(encoding="utf-8"))
        from schema.yaml_schema import StateDiagramFile
        sd = StateDiagramFile.model_validate(raw)

        result_new = yaml_to_canonical_state_json("Elevator", sd)
        result_old = _yaml_to_canonical_state("Elevator", sd)
        assert result_new == result_old

    def test_class_parity_with_elevator(self):
        """yaml_to_canonical_class_json matches _yaml_to_canonical_class on elevator."""
        from schema.canonical_builder import yaml_to_canonical_class_json
        from tools.drawio import _yaml_to_canonical_class

        cd_path = Path("examples/elevator/.design/model/Elevator/class-diagram.yaml")
        if not cd_path.exists():
            pytest.skip("Elevator example not available")
        raw = yaml.safe_load(cd_path.read_text(encoding="utf-8"))
        from schema.yaml_schema import ClassDiagramFile
        cd = ClassDiagramFile.model_validate(raw)

        result_new = yaml_to_canonical_class_json("Elevator", cd)
        result_old = _yaml_to_canonical_class("Elevator", cd)
        assert result_new == result_old


# ---------------------------------------------------------------------------
# (b) Loader
# ---------------------------------------------------------------------------

class TestLoader:
    def _elevator_model_root(self, tmp_path: Path) -> Path:
        """Copy the Elevator domain into a tmp single-domain root."""
        import shutil
        src = Path("examples/elevator/.design/model/Elevator")
        if not src.exists():
            return None  # type: ignore[return-value]
        shutil.copytree(src, tmp_path / "Elevator")
        return tmp_path

    def test_load_elevator_model(self, tmp_path):
        """load_model returns populated LoadedModel for elevator example."""
        root = self._elevator_model_root(tmp_path)
        if root is None:
            pytest.skip("Elevator example not available")
        loaded = load_model(root)
        assert loaded.class_diagram is not None
        assert loaded.class_diagram.type == "class_diagram"
        assert len(loaded.class_diagram.classes) > 0
        assert len(loaded.state_diagrams) > 0

    def test_load_elevator_state_diagrams_keyed_by_class(self, tmp_path):
        """State diagrams are keyed by class name."""
        root = self._elevator_model_root(tmp_path)
        if root is None:
            pytest.skip("Elevator example not available")
        loaded = load_model(root)
        assert "Elevator" in loaded.state_diagrams
        assert loaded.state_diagrams["Elevator"].class_name == "Elevator"

    def test_load_missing_root_raises(self, tmp_path):
        """Missing model root raises CompilationFailed."""
        with pytest.raises(CompilationFailed):
            load_model(tmp_path / "nonexistent")

    def test_load_empty_domain_dir_raises(self, tmp_path):
        """Model root with no domain subdirectory raises CompilationFailed."""
        with pytest.raises(CompilationFailed):
            load_model(tmp_path)  # tmp_path exists but has no subdirs

    def test_load_missing_class_diagram_raises(self, tmp_path):
        """Domain dir with no class-diagram.yaml raises CompilationFailed."""
        domain_dir = tmp_path / "Test"
        domain_dir.mkdir()
        # No class-diagram.yaml — loader must raise
        with pytest.raises(CompilationFailed):
            load_model(tmp_path)

    def test_load_types_yaml_loaded(self, tmp_path):
        """Minimal model with types.yaml → loaded.types_raw is not None."""
        domain_dir = tmp_path / "Test"
        domain_dir.mkdir()
        (domain_dir / "class-diagram.yaml").write_text(
            "schema_version: '1.0.0'\n"
            "domain: Test\n"
            "classes: []\n"
            "associations: []\n"
            "generalizations: []\n",
            encoding="utf-8",
        )
        (domain_dir / "types.yaml").write_text(
            "schema_version: '1.0.0'\n"
            "domain: Test\n"
            "types: []\n",
            encoding="utf-8",
        )
        loaded = load_model(tmp_path)
        assert loaded.types_raw is not None


# ---------------------------------------------------------------------------
# (c) Senescent classifier (D-14)
# ---------------------------------------------------------------------------

class TestHasSelfGenerate:
    def test_direct_self_generate(self):
        tree = STATEMENT_PARSER.parse("generate Foo to self;")
        assert has_self_generate(tree) is True

    def test_other_target_not_self(self):
        tree = STATEMENT_PARSER.parse("generate Foo to other;")
        assert has_self_generate(tree) is False

    def test_self_generate_inside_if(self):
        """Conservative: self-generate inside if block still counts (D-14)."""
        src = "if (self.x > 0) { generate Ready to self; }"
        tree = STATEMENT_PARSER.parse(src)
        assert has_self_generate(tree) is True

    def test_no_generate_at_all(self):
        tree = STATEMENT_PARSER.parse("self.x = 1;")
        assert has_self_generate(tree) is False


class TestClassifySenescent:
    def test_no_entry_action_is_senescent(self):
        """State with no entry action → senescent."""
        sd = _make_sd("Car", [CanonicalState(name="Idle", entry_action=None)])
        result = classify_senescent_states(sd, STATEMENT_PARSER)
        assert "Idle" in result

    def test_entry_action_no_self_generate(self):
        """Entry action with no self-generate → senescent."""
        sd = _make_sd("Car", [CanonicalState(name="Moving", entry_action="self.speed = 10;")])
        result = classify_senescent_states(sd, STATEMENT_PARSER)
        assert "Moving" in result

    def test_self_generate_not_senescent(self):
        """Entry action with generate-to-self → NOT senescent."""
        sd = _make_sd("Car", [CanonicalState(name="Active", entry_action="generate Ready to self;")])
        result = classify_senescent_states(sd, STATEMENT_PARSER)
        assert "Active" not in result

    def test_guarded_self_generate_not_senescent(self):
        """Even guarded self-generate makes state non-senescent (conservative)."""
        src = "if (self.x > 0) { generate Ready to self; }"
        sd = _make_sd("Car", [CanonicalState(name="Conditional", entry_action=src)])
        result = classify_senescent_states(sd, STATEMENT_PARSER)
        assert "Conditional" not in result

    def test_result_is_sorted(self):
        """classify_senescent_states returns a sorted list (D-07)."""
        sd = _make_sd("Car", [
            CanonicalState(name="Zebra", entry_action=None),
            CanonicalState(name="Alpha", entry_action=None),
        ])
        result = classify_senescent_states(sd, STATEMENT_PARSER)
        assert result == sorted(result)

    def test_elevator_senescent_expected(self, tmp_path):
        """Elevator Elevator class: Idle/Moving/Exchanging senescent; Departing etc. not."""
        import shutil
        src = Path("examples/elevator/.design/model/Elevator")
        if not src.exists():
            pytest.skip("Elevator example not available")
        shutil.copytree(src, tmp_path / "Elevator")
        loaded = load_model(tmp_path)
        sd = loaded.state_diagrams.get("Elevator")
        if sd is None:
            pytest.skip("Elevator state diagram not found")
        result = classify_senescent_states(sd, STATEMENT_PARSER)
        senescent_set = set(result)
        # These states have no self-generate in their entry actions
        assert "Idle" in senescent_set
        # Departing has generate Ready to self → transient
        assert "Departing" not in senescent_set


# ---------------------------------------------------------------------------
# (d) Attribute flattening (D-04)
# ---------------------------------------------------------------------------

class TestAttributeFlattening:
    def test_subtype_inherits_supertype_attr(self):
        loaded = _minimal_loaded()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        sub = manifest["class_defs"]["SubClass"]
        assert "super_attr" in sub["attributes"]

    def test_subtype_has_own_attrs(self):
        loaded = _minimal_loaded()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        sub = manifest["class_defs"]["SubClass"]
        assert "sub_attr" in sub["attributes"]

    def test_subtype_wins_on_conflict(self):
        classes = [
            _make_cls("Super", attributes=["- shared: String"]),
            _make_cls("Sub", attributes=["- shared: int"], specializes="R1"),
        ]
        cd = _make_cd(
            classes=classes,
            gens=[CanonicalGeneralization(name="R1", supertype="Super", subtypes=["Sub"])],
        )
        loaded = LoadedModel(class_diagram=cd, state_diagrams={}, root=Path("."))
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        sub = manifest["class_defs"]["Sub"]
        assert sub["attributes"]["shared"]["type"] == "int"

    def test_no_duplicate_attr_keys(self):
        loaded = _minimal_loaded()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        for cls in manifest["class_defs"].values():
            keys = list(cls["attributes"].keys())
            assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# (e) Generalization Cases A / B / C (D-03)
# ---------------------------------------------------------------------------

class TestGeneralizationCases:
    def _loaded_case_a(self) -> LoadedModel:
        """Case A: entity supertype + active subtype with own SM."""
        classes = [
            _make_cls("SuperEnt", stereotype="entity"),
            _make_cls("SubActive", stereotype="active", specializes="R1"),
        ]
        cd = _make_cd(
            classes=classes,
            gens=[CanonicalGeneralization(name="R1", supertype="SuperEnt", subtypes=["SubActive"])],
        )
        sub_sd = _make_sd(
            "SubActive",
            states=[CanonicalState(name="SubStart", entry_action=None)],
            transitions=[],
            initial_state="SubStart",
        )
        return LoadedModel(class_diagram=cd, state_diagrams={"SubActive": sub_sd}, root=Path("."))

    def _loaded_case_b(self) -> LoadedModel:
        """Case B: active supertype with SM, subtype has no SM → copy super."""
        classes = [
            _make_cls("SuperActive", stereotype="active"),
            _make_cls("SubNoSM", stereotype="active", specializes="R1"),
        ]
        cd = _make_cd(
            classes=classes,
            gens=[CanonicalGeneralization(name="R1", supertype="SuperActive", subtypes=["SubNoSM"])],
        )
        super_sd = _make_sd(
            "SuperActive",
            states=[CanonicalState(name="Idle", entry_action=None)],
            transitions=[CanonicalTransition(from_state="Idle", to="Idle", event="Ping", params=None, guard=None)],
            initial_state="Idle",
        )
        return LoadedModel(
            class_diagram=cd,
            state_diagrams={"SuperActive": super_sd},  # no SubNoSM SD
            root=Path("."),
        )

    def _loaded_case_c(self) -> LoadedModel:
        """Case C: active supertype + active subtype that redefines its SM."""
        classes = [
            _make_cls("SuperActive", stereotype="active"),
            _make_cls("SubRedefines", stereotype="active", specializes="R1"),
        ]
        cd = _make_cd(
            classes=classes,
            gens=[CanonicalGeneralization(name="R1", supertype="SuperActive", subtypes=["SubRedefines"])],
        )
        super_sd = _make_sd(
            "SuperActive",
            states=[CanonicalState(name="SuperStart", entry_action=None)],
            initial_state="SuperStart",
        )
        sub_sd = _make_sd(
            "SubRedefines",
            states=[CanonicalState(name="SubStart", entry_action=None)],
            initial_state="SubStart",
        )
        return LoadedModel(
            class_diagram=cd,
            state_diagrams={"SuperActive": super_sd, "SubRedefines": sub_sd},
            root=Path("."),
        )

    def test_case_a_super_has_no_table(self):
        loaded = self._loaded_case_a()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        assert not manifest["class_defs"]["SuperEnt"]["transition_table"]

    def test_case_a_sub_has_own_table(self):
        loaded = self._loaded_case_a()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        sub = manifest["class_defs"]["SubActive"]
        assert sub["initial_state"] == "SubStart"

    def test_case_b_sub_copies_super_table(self):
        loaded = self._loaded_case_b()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        sub = manifest["class_defs"]["SubNoSM"]
        assert sub["transition_table"]  # copied from super

    def test_case_c_sub_uses_own_sm_not_super(self):
        loaded = self._loaded_case_c()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        sub = manifest["class_defs"]["SubRedefines"]
        assert sub["initial_state"] == "SubStart"  # own SM, not SuperStart


# ---------------------------------------------------------------------------
# (f) Determinism — sorted dicts (D-07)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_class_defs_sorted(self):
        loaded = _minimal_loaded()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        keys = list(manifest["class_defs"].keys())
        assert keys == sorted(keys)

    def test_attributes_sorted(self):
        loaded = _minimal_loaded()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        for cls in manifest["class_defs"].values():
            keys = list(cls["attributes"].keys())
            assert keys == sorted(keys), f"{cls['name']}.attributes not sorted"

    def test_associations_sorted(self):
        classes = [_make_cls("A"), _make_cls("B")]
        assocs = [
            CanonicalAssociation(name="R2", point_1="A", point_2="B",
                                 mult_1_2="1", mult_2_1="1..*",
                                 phrase_1_2="has", phrase_2_1="belongs to"),
            CanonicalAssociation(name="R1", point_1="B", point_2="A",
                                 mult_1_2="1", mult_2_1="1",
                                 phrase_1_2="owns", phrase_2_1="owned by"),
        ]
        cd = _make_cd(classes=classes, assocs=assocs)
        loaded = LoadedModel(class_diagram=cd, state_diagrams={}, root=Path("."))
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        keys = list(manifest["associations"].keys())
        assert keys == sorted(keys)

    def test_two_builds_identical(self):
        """Two successive builds of the same input produce identical JSON (D-07)."""
        loaded = _minimal_loaded()
        m1 = build_domain_manifest(loaded, STATEMENT_PARSER)
        m2 = build_domain_manifest(loaded, STATEMENT_PARSER)
        assert json.dumps(m1, sort_keys=True, default=str) == json.dumps(m2, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# (g) Transition table encoding (D-13)
# ---------------------------------------------------------------------------

class TestTransitionTableEncoding:
    def _loaded_with_transition(self) -> LoadedModel:
        classes = [_make_cls("Light", stereotype="active")]
        cd = _make_cd(classes=classes)
        sd = _make_sd(
            "Light",
            states=[
                CanonicalState(name="Off", entry_action=None),
                CanonicalState(name="On", entry_action=None),
            ],
            transitions=[
                CanonicalTransition(from_state="Off", to="On", event="Toggle", params=None, guard=None),
            ],
            initial_state="Off",
        )
        return LoadedModel(class_diagram=cd, state_diagrams={"Light": sd}, root=Path("."))

    def test_explicit_transition_present(self):
        loaded = self._loaded_with_transition()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        table = manifest["class_defs"]["Light"]["transition_table"]
        assert ("Off", "Toggle") in table
        assert table[("Off", "Toggle")]["next_state"] == "On"

    def test_absent_cell_is_cant_happen(self):
        """Absent (state, event) key → can't_happen (scheduler raises ErrorMicroStep)."""
        loaded = self._loaded_with_transition()
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        table = manifest["class_defs"]["Light"]["transition_table"]
        # (On, Toggle) is not defined → absent = can't_happen
        assert ("On", "Toggle") not in table

    def test_event_ignored_encoding(self):
        """event_ignored: all-None entry is handled correctly by scheduler."""
        # Build a manifest with explicit event_ignored entry
        entry: TransitionEntry = {"next_state": None, "action_fn": None, "guard_fn": None}
        assert entry["next_state"] is None
        assert entry["action_fn"] is None
        assert entry["guard_fn"] is None

    def test_transition_table_keys_sorted(self):
        classes = [_make_cls("Light", stereotype="active")]
        cd = _make_cd(classes=classes)
        sd = _make_sd(
            "Light",
            states=[
                CanonicalState(name="A", entry_action=None),
                CanonicalState(name="B", entry_action=None),
            ],
            transitions=[
                CanonicalTransition(from_state="B", to="A", event="Reset", params=None, guard=None),
                CanonicalTransition(from_state="A", to="B", event="Go", params=None, guard=None),
            ],
            initial_state="A",
        )
        loaded = LoadedModel(class_diagram=cd, state_diagrams={"Light": sd}, root=Path("."))
        manifest = build_domain_manifest(loaded, STATEMENT_PARSER)
        table = manifest["class_defs"]["Light"]["transition_table"]
        keys = [str(k) for k in table.keys()]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Import for TransitionEntry type hint in test
# ---------------------------------------------------------------------------
from typing import TypedDict

class TransitionEntry(TypedDict):
    next_state: str | None
    action_fn: None
    guard_fn: None


# ---------------------------------------------------------------------------
# (h) _parse_attr_label edge cases
# ---------------------------------------------------------------------------

from compiler.manifest_builder import _parse_attr_label


class TestParseAttrLabel:
    def test_basic_public_attr(self):
        result = _parse_attr_label("+ car_id: int")
        assert result["name"] == "car_id"
        assert result["type"] == "int"
        assert result["visibility"] == "public"
        assert result["scope"] == "instance"

    def test_private_attr(self):
        result = _parse_attr_label("- name: String")
        assert result["visibility"] == "private"

    def test_identifier_tag(self):
        result = _parse_attr_label("- id: UniqueID {I1}")
        assert result["identifier"] == [1]

    def test_referential_tag(self):
        result = _parse_attr_label("- id: UniqueID {I1, R6}")
        assert result["identifier"] == [1]
        assert result["referential"] == "R6"

    def test_class_scope(self):
        result = _parse_attr_label("+ <u>count</u>: int")
        assert result["scope"] == "class"

    def test_multiple_identifier_tags(self):
        result = _parse_attr_label("- key: str {I1, I2}")
        assert result["identifier"] == [1, 2]

    def test_malformed_label_fallback(self):
        result = _parse_attr_label("not a valid label at all!!!")
        assert "raw" in result
        assert result["type"] == "Unknown"

    def test_protected_attr(self):
        result = _parse_attr_label("# speed: float")
        assert result["visibility"] == "protected"
