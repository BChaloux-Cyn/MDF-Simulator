import pytest
from compiler.codegen import generate_class_module


def _make_manifest(
    name="Widget",
    attributes=None,
    events=None,
    transition_table=None,
    entry_actions=None,
):
    return {
        "name": name,
        "is_abstract": False,
        "identifier_attrs": [],
        "attributes": attributes or {},
        "entry_actions": entry_actions or {},
        "initial_state": None,
        "final_states": [],
        "senescent_states": [],
        "transition_table": transition_table or {},
        "supertype": None,
        "subtypes": [],
        "events": events or {},
    }


class TestClassTypedDict:
    def test_class_typeddict_emitted(self):
        manifest = _make_manifest(
            attributes={"floor_count": {"name": "floor_count", "type": "Integer",
                                        "visibility": "private", "scope": "instance",
                                        "identifier": None, "referential": None}}
        )
        src = generate_class_module(manifest, {}, None)
        assert "class WidgetDict(TypedDict):" in src

    def test_class_typeddict_has_engine_keys(self):
        manifest = _make_manifest()
        src = generate_class_module(manifest, {}, None)
        assert "__class_name__: str" in src
        assert "__instance_key__: str" in src

    def test_class_typeddict_attribute_type_mapped(self):
        manifest = _make_manifest(
            attributes={"floor_count": {"name": "floor_count", "type": "Integer",
                                        "visibility": "private", "scope": "instance",
                                        "identifier": None, "referential": None}}
        )
        src = generate_class_module(manifest, {}, None)
        assert "floor_count: int" in src

    def test_class_typeddict_passthrough_type(self):
        manifest = _make_manifest(
            attributes={"direction": {"name": "direction", "type": "Direction",
                                      "visibility": "private", "scope": "instance",
                                      "identifier": None, "referential": None}}
        )
        src = generate_class_module(manifest, {}, None)
        assert "direction: Direction" in src


class TestEventTypedDict:
    def test_event_with_params_generates_typeddict(self):
        manifest = _make_manifest(events={"Activate": "level: Integer"})
        src = generate_class_module(manifest, {}, None)
        assert "class ActivateParams(TypedDict):" in src
        assert "level: int" in src

    def test_event_without_params_no_typeddict(self):
        manifest = _make_manifest(events={"Reset": None})
        src = generate_class_module(manifest, {}, None)
        assert "class ResetParams" not in src

    def test_no_events_no_event_typedicts(self):
        manifest = _make_manifest()
        src = generate_class_module(manifest, {}, None)
        assert "Params(TypedDict)" not in src


class TestActionSignature:
    def test_action_uses_class_typeddict(self):
        manifest = _make_manifest(
            entry_actions={"Active": ""},
            transition_table={("Idle", "Activate"): [{"next_state": "Active",
                                                       "action_fn": None,
                                                       "guard_fn": None}]},
            events={"Activate": "level: Integer"},
        )
        src = generate_class_module(manifest, {}, None)
        assert 'self_dict: "WidgetDict"' in src

    def test_action_uses_event_typeddict_for_single_trigger(self):
        manifest = _make_manifest(
            entry_actions={"Active": ""},
            transition_table={("Idle", "Activate"): [{"next_state": "Active",
                                                       "action_fn": None,
                                                       "guard_fn": None}]},
            events={"Activate": "level: Integer"},
        )
        src = generate_class_module(manifest, {}, None)
        assert 'params: "ActivateParams"' in src

    def test_action_uses_dict_for_multiple_triggers(self):
        manifest = _make_manifest(
            entry_actions={"Active": ""},
            transition_table={
                ("Idle", "Activate"): [{"next_state": "Active", "action_fn": None, "guard_fn": None}],
                ("Waiting", "Resume"): [{"next_state": "Active", "action_fn": None, "guard_fn": None}],
            },
            events={"Activate": "level: Integer", "Resume": "mode: String"},
        )
        src = generate_class_module(manifest, {}, None)
        assert 'params: dict' in src


class TestGuardSignature:
    def test_guard_uses_event_typeddict(self):
        manifest = _make_manifest(
            transition_table={
                ("Idle", "Activate"): [{"next_state": "Active", "action_fn": None,
                                         "guard_fn": "rcvd_evt.level > 0"}],
            },
            events={"Activate": "level: Integer"},
        )
        src = generate_class_module(manifest, {}, None)
        assert 'params: "ActivateParams"' in src

    def test_guard_uses_dict_for_no_param_event(self):
        manifest = _make_manifest(
            transition_table={
                ("Idle", "Reset"): [{"next_state": "Idle", "action_fn": None,
                                      "guard_fn": "True"}],
            },
            events={"Reset": None},
        )
        src = generate_class_module(manifest, {}, None)
        assert "params: dict" in src


class TestRuntimeImport:
    def test_mdf_remove_imported_when_action_uses_it(self):
        manifest = _make_manifest(
            entry_actions={"Active": "my_map.remove(k);"},
            transition_table={("Idle", "Go"): [{"next_state": "Active", "action_fn": None, "guard_fn": None}]},
            events={"Go": None},
        )
        src = generate_class_module(manifest, {}, None)
        assert "from mdf.runtime import _mdf_remove" in src

    def test_mdf_remove_not_imported_when_unused(self):
        manifest = _make_manifest()
        src = generate_class_module(manifest, {}, None)
        assert "from mdf.runtime import _mdf_remove" not in src


class TestTypedDictImport:
    def test_typeddict_imported(self):
        manifest = _make_manifest()
        src = generate_class_module(manifest, {}, None)
        assert "TypedDict" in src
