import json
from schema.canonical_builder import yaml_to_canonical_class, yaml_to_canonical_state
from schema.yaml_schema import (
    ClassDiagramFile, StateDiagramFile, ClassDef, Method, MethodParam,
    ProvidedBridge, BridgeImplementation,
)

def _minimal_cd():
    return ClassDiagramFile.model_validate({
        "schema_version": "1.0.0",
        "domain": "Test",
        "classes": [],
        "associations": [],
        "bridges": [{
            "to_domain": "Foo",
            "direction": "provided",
            "implementations": [{"name": "DoThing", "action": "x = 1;"}],
        }],
    })

def _minimal_op_lookup():
    from schema.yaml_schema import BridgeOperation, OperationParam
    op = BridgeOperation.model_validate({"name": "DoThing", "params": [{"name": "x", "type": "Integer"}], "return": "Boolean"})
    return {"Foo": {"DoThing": op}}

def _minimal_sd():
    return StateDiagramFile.model_validate({
        "schema_version": "1.0.0",
        "domain": "Test",
        "class": "MyClass",
        "initial_state": "Idle",
        "states": [{"name": "Idle"}],
        "transitions": [],
    })

def _minimal_class_def():
    return ClassDef.model_validate({
        "name": "MyClass",
        "stereotype": "active",
        "methods": [{
            "name": "doWork",
            "visibility": "public",
            "scope": "instance",
            "params": [{"name": "n", "type": "Integer"}],
            "return": "Boolean",
            "action": "return n > 0;",
        }, {
            "name": "noAction",
            "visibility": "private",
            "scope": "instance",
        }],
    })

def test_bridge_impls_included_with_op_lookup():
    cd = _minimal_cd()
    result = yaml_to_canonical_class("Test", cd, _minimal_op_lookup())
    assert len(result.bridge_impls) == 1
    impl = result.bridge_impls[0]
    assert impl.name == "DoThing"
    assert impl.to_domain == "Foo"
    assert impl.params_sig == "x: Integer"
    assert impl.return_type == "Boolean"
    assert impl.action == "x = 1;"

def test_bridge_impls_empty_without_op_lookup():
    cd = _minimal_cd()
    result = yaml_to_canonical_class("Test", cd, op_lookup=None)
    assert result.bridge_impls == []

def test_methods_included_with_class_def():
    sd = _minimal_sd()
    cls = _minimal_class_def()
    result = yaml_to_canonical_state("Test", sd, class_def=cls)
    assert len(result.methods) == 1  # noAction is omitted (no action body)
    m = result.methods[0]
    assert m.name == "doWork"
    assert m.params_sig == "n: Integer"
    assert m.return_type == "Boolean"
    assert m.action == "return n > 0;"

def test_methods_empty_without_class_def():
    sd = _minimal_sd()
    result = yaml_to_canonical_state("Test", sd, class_def=None)
    assert result.methods == []

def test_canonical_class_json_includes_bridge_impls():
    from schema.canonical_builder import yaml_to_canonical_class_json
    cd = _minimal_cd()
    s = yaml_to_canonical_class_json("Test", cd, _minimal_op_lookup())
    data = json.loads(s)
    assert len(data["bridge_impls"]) == 1

def test_canonical_state_json_includes_methods():
    from schema.canonical_builder import yaml_to_canonical_state_json
    sd = _minimal_sd()
    cls = _minimal_class_def()
    s = yaml_to_canonical_state_json("Test", sd, class_def=cls)
    data = json.loads(s)
    assert len(data["methods"]) == 1
