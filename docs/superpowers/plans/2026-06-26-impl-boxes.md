# Implementation Boxes in Draw.io Diagrams

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add disconnected monospace rectangle boxes to Draw.io class diagrams (one per provided bridge implementation, signature from DOMAINS.yaml) and state diagrams (one per class method with an action body).

**Architecture:** Five files touched — schema constants, canonical Pydantic models, canonical builder, and the drawio renderer. No YAML schema changes needed. Change detection is extended by including bridge impl and method data in the canonical JSON fingerprints.

**Tech Stack:** Python 3.11+, Pydantic v2, lxml, existing `tools/drawio.py` renderer patterns.

## Global Constraints

- All tests run with: `python -m pytest tests/ -x -q`
- Virtual env: `.venv/` managed by `uv`; activate with `.venv/Scripts/activate` (Windows) or `.venv/bin/activate` (Linux/Mac)
- No new dependencies — all required libraries already installed
- Follow existing patterns: `_make_issue()` for errors, `severity="error"` for hard failures
- `DOMAINS.yaml` bridge lookup: for a provided bridge `to_domain=X` in class-diagram.yaml, find DOMAINS.yaml entries where `bridge.from_domain == X AND bridge.to == current_domain`
- Methods with `action: null` produce no box; silently omit method boxes if class-diagram.yaml is absent

---

### Task 1: Schema constants and ID functions

**Files:**
- Modify: `schema/drawio_schema.py`
- Test: `tests/test_drawio_schema.py` (create if absent)

**Interfaces:**
- Produces:
  - `STYLE_IMPL_BOX: str`
  - `bridge_impl_id(domain: str, to_domain: str, impl_name: str) -> str`
  - `method_box_id(domain: str, class_name: str, method_name: str) -> str`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_drawio_schema.py
from schema.drawio_schema import (
    STYLE_IMPL_BOX,
    bridge_impl_id,
    method_box_id,
    BIJECTION_TABLE,
)

def test_style_impl_box_nonempty():
    assert STYLE_IMPL_BOX
    assert "Courier New" in STYLE_IMPL_BOX
    assert "f5f5f5" in STYLE_IMPL_BOX

def test_bridge_impl_id():
    assert bridge_impl_id("Elevator", "Transport", "ElevatorDetected") == \
        "elevator:bridge_impl:Transport:ElevatorDetected"

def test_method_box_id():
    assert method_box_id("Elevator", "Elevator", "_get_lit_buttons") == \
        "elevator:method:Elevator:_get_lit_buttons"

def test_bijection_table_has_impl_keys():
    assert "bridge_impl" in BIJECTION_TABLE
    assert "method_box" in BIJECTION_TABLE
```

- [ ] **Step 2: Run to confirm failure**

```
python -m pytest tests/test_drawio_schema.py -x -q
```
Expected: `ImportError` or `AssertionError`

- [ ] **Step 3: Add constants and functions to `schema/drawio_schema.py`**

Add to `__all__` list:
```python
"STYLE_IMPL_BOX",
"bridge_impl_id",
"method_box_id",
```

Add after `STYLE_BRIDGE`:
```python
STYLE_IMPL_BOX = (
    "rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;"
    "fontFamily=Courier New;fontSize=11;fillColor=#f5f5f5;"
    "strokeColor=#666666;fontColor=#333333;"
    "spacingLeft=6;spacingRight=6;spacingTop=4;spacingBottom=4;"
)
```

Add to `BIJECTION_TABLE` dict:
```python
"bridge_impl": STYLE_IMPL_BOX,
"method_box":  STYLE_IMPL_BOX,
```

Add after `transition_id()`:
```python
def bridge_impl_id(domain: str, to_domain: str, impl_name: str) -> str:
    """Return deterministic mxCell ID for a bridge implementation box."""
    return f"{domain.lower()}:bridge_impl:{to_domain}:{impl_name}"


def method_box_id(domain: str, class_name: str, method_name: str) -> str:
    """Return deterministic mxCell ID for a method implementation box."""
    return f"{domain.lower()}:method:{class_name}:{method_name}"
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_drawio_schema.py -x -q
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add schema/drawio_schema.py tests/test_drawio_schema.py
git commit -m "feat: add STYLE_IMPL_BOX and bridge_impl/method_box ID functions"
```

---

### Task 2: Canonical models

**Files:**
- Modify: `schema/drawio_canonical.py`
- Test: `tests/test_drawio_canonical.py` (create if absent)

**Interfaces:**
- Consumes: nothing new
- Produces:
  - `CanonicalBridgeImpl(name, to_domain, params_sig, return_type, action)`
  - `CanonicalMethod(name, params_sig, return_type, action)`
  - `CanonicalClassDiagram.bridge_impls: list[CanonicalBridgeImpl]` (default `[]`)
  - `CanonicalStateDiagram.methods: list[CanonicalMethod]` (default `[]`)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_drawio_canonical.py
import json
from schema.drawio_canonical import (
    CanonicalBridgeImpl, CanonicalMethod,
    CanonicalClassDiagram, CanonicalClassEntry,
    CanonicalAssociation, CanonicalGeneralization,
    CanonicalStateDiagram, CanonicalState, CanonicalTransition,
)

def test_canonical_bridge_impl_round_trips():
    impl = CanonicalBridgeImpl(
        name="ElevatorDetected",
        to_domain="Transport",
        params_sig="sensor_id: Integer",
        return_type=None,
        action="generate Foo to self;",
    )
    data = impl.model_dump()
    assert data["name"] == "ElevatorDetected"
    assert data["params_sig"] == "sensor_id: Integer"
    assert data["return_type"] is None

def test_canonical_method_round_trips():
    m = CanonicalMethod(
        name="_get_lit_buttons",
        params_sig="",
        return_type="Set<DestFloorButton>",
        action="return select many related by self->R4;",
    )
    assert m.return_type == "Set<DestFloorButton>"

def test_class_diagram_bridge_impls_default_empty():
    cd = CanonicalClassDiagram(
        type="class_diagram", domain="elevator",
        classes=[], associations=[], generalizations=[],
    )
    assert cd.bridge_impls == []

def test_state_diagram_methods_default_empty():
    sd = CanonicalStateDiagram(
        type="state_diagram", domain="Elevator",
        **{"class": "Elevator"},
        initial_state="Idle",
        states=[], transitions=[],
    )
    assert sd.methods == []

def test_class_diagram_serializes_bridge_impls():
    impl = CanonicalBridgeImpl(
        name="Foo", to_domain="Bar", params_sig="x: Integer",
        return_type="Boolean", action="return true;",
    )
    cd = CanonicalClassDiagram(
        type="class_diagram", domain="elevator",
        classes=[], associations=[], generalizations=[],
        bridge_impls=[impl],
    )
    s = json.dumps(cd.model_dump(by_alias=True), sort_keys=True)
    assert "bridge_impls" in s
    assert "Foo" in s
```

- [ ] **Step 2: Run to confirm failure**

```
python -m pytest tests/test_drawio_canonical.py -x -q
```
Expected: `ImportError`

- [ ] **Step 3: Add new models to `schema/drawio_canonical.py`**

Add after the imports block at the top:

```python
# ---------------------------------------------------------------------------
# Implementation box canonical models
# ---------------------------------------------------------------------------

class CanonicalBridgeImpl(BaseModel):
    name: str
    to_domain: str
    params_sig: str
    return_type: str | None
    action: str


class CanonicalMethod(BaseModel):
    name: str
    params_sig: str
    return_type: str | None
    action: str
```

Extend `CanonicalClassDiagram`:
```python
class CanonicalClassDiagram(BaseModel):
    type: Literal["class_diagram"]
    domain: str
    classes: list[CanonicalClassEntry]
    associations: list[CanonicalAssociation]
    generalizations: list[CanonicalGeneralization]
    bridge_impls: list[CanonicalBridgeImpl] = []   # NEW
```

Extend `CanonicalStateDiagram`:
```python
class CanonicalStateDiagram(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["state_diagram"]
    domain: str
    class_name: str = Field(alias="class")
    initial_state: str
    states: list[CanonicalState]
    transitions: list[CanonicalTransition]
    methods: list[CanonicalMethod] = []   # NEW
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_drawio_canonical.py -x -q
```
Expected: 5 passed

- [ ] **Step 5: Run full suite to check no regressions**

```
python -m pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```
git add schema/drawio_canonical.py tests/test_drawio_canonical.py
git commit -m "feat: add CanonicalBridgeImpl and CanonicalMethod to canonical models"
```

---

### Task 3: Canonical builder extensions

**Files:**
- Modify: `schema/canonical_builder.py`
- Test: `tests/test_canonical_builder.py` (create if absent)

**Interfaces:**
- Consumes: `CanonicalBridgeImpl`, `CanonicalMethod` from Task 2
- Produces:
  - `yaml_to_canonical_class(domain, cd, op_lookup=None)` — `op_lookup: dict[str, dict[str, Any]] | None`
  - `yaml_to_canonical_state(domain, sd, class_def=None)` — `class_def: ClassDef | None`
  - `yaml_to_canonical_class_json(domain, cd, op_lookup=None) -> str`
  - `yaml_to_canonical_state_json(domain, sd, class_def=None) -> str`

`op_lookup` key structure: `op_lookup[to_domain][op_name] = BridgeOperation`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_canonical_builder.py
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
```

- [ ] **Step 2: Run to confirm failure**

```
python -m pytest tests/test_canonical_builder.py -x -q
```
Expected: `TypeError` on wrong argument count or `AssertionError`

- [ ] **Step 3: Update imports in `schema/canonical_builder.py`**

Add to the existing imports at top of file:
```python
from schema.drawio_canonical import (
    CanonicalAssociation,
    CanonicalBridgeImpl,      # NEW
    CanonicalClassDiagram,
    CanonicalClassEntry,
    CanonicalGeneralization,
    CanonicalMethod,          # NEW
    CanonicalState,
    CanonicalStateDiagram,
    CanonicalTransition,
)
```

- [ ] **Step 4: Update `yaml_to_canonical_class`**

Change the function signature and add bridge impl collection. The full updated function:

```python
def yaml_to_canonical_class(
    domain: str,
    cd: "ClassDiagramFile",
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> CanonicalClassDiagram:
    """Convert a ClassDiagramFile to a CanonicalClassDiagram object."""
    from schema.yaml_schema import ProvidedBridge

    # Build gen_map from partition declarations on supertype classes
    gen_map: dict[str, dict] = {}
    for cls in cd.classes:
        if cls.partitions:
            for p in cls.partitions:
                gen_map[p.name] = {"supertype": cls.name, "subtypes": sorted(p.subtypes)}

    canonical_classes: list[CanonicalClassEntry] = []
    for cls in sorted(cd.classes, key=lambda c: c.name):
        attrs = [
            _attr_label(a.visibility, a.scope, a.name, a.type, a.identifier, a.referential)
            for a in cls.attributes
        ]
        methods = [
            _method_label(m.visibility, m.scope, m.name, m.params, m.return_type)
            for m in cls.methods
        ]
        canonical_classes.append(
            CanonicalClassEntry(
                name=cls.name,
                stereotype=cls.stereotype,
                specializes=cls.specializes,
                attributes=attrs,
                methods=methods,
            )
        )

    canonical_assocs: list[CanonicalAssociation] = []
    for assoc in sorted(cd.associations, key=lambda a: a.name):
        if assoc.name in gen_map:
            continue
        canonical_assocs.append(
            CanonicalAssociation(
                name=assoc.name,
                point_1=assoc.point_1,
                point_2=assoc.point_2,
                mult_1_2=assoc.mult_1_to_2,
                mult_2_1=assoc.mult_2_to_1,
                phrase_1_2=_wrap_squarest(assoc.phrase_1_to_2),
                phrase_2_1=_wrap_squarest(assoc.phrase_2_to_1),
            )
        )

    canonical_gens: list[CanonicalGeneralization] = [
        CanonicalGeneralization(
            name=rname,
            supertype=info["supertype"],
            subtypes=info["subtypes"],
        )
        for rname, info in sorted(gen_map.items())
    ]

    bridge_impls: list[CanonicalBridgeImpl] = []
    if op_lookup is not None:
        for bridge in cd.bridges:
            if not isinstance(bridge, ProvidedBridge):
                continue
            for impl in bridge.implementations:
                op = op_lookup.get(bridge.to_domain, {}).get(impl.name)
                if op is None:
                    continue
                params_sig = ", ".join(
                    f"{p.name}: {p.type}" for p in op.params
                )
                bridge_impls.append(CanonicalBridgeImpl(
                    name=impl.name,
                    to_domain=bridge.to_domain,
                    params_sig=params_sig,
                    return_type=op.return_type,
                    action=impl.action,
                ))
    bridge_impls.sort(key=lambda b: (b.to_domain, b.name))

    return CanonicalClassDiagram(
        type="class_diagram",
        domain=domain.lower(),
        classes=canonical_classes,
        associations=canonical_assocs,
        generalizations=canonical_gens,
        bridge_impls=bridge_impls,
    )
```

- [ ] **Step 5: Update `yaml_to_canonical_state`**

```python
def yaml_to_canonical_state(
    domain: str,
    sd: "StateDiagramFile",
    class_def: "ClassDef | None" = None,
) -> CanonicalStateDiagram:
    """Convert a StateDiagramFile to a CanonicalStateDiagram object."""
    event_map = {e.name: e for e in sd.events} if sd.events else {}

    canonical_states = sorted(
        [CanonicalState(name=st.name, entry_action=st.entry_action) for st in sd.states],
        key=lambda s: s.name,
    )

    canonical_transitions: list[CanonicalTransition] = []
    for trans in sd.transitions:
        event_def = event_map.get(trans.event)
        if event_def and event_def.params:
            params = ", ".join(f"{p.name}: {p.type}" for p in event_def.params)
        else:
            params = None
        canonical_transitions.append(
            CanonicalTransition(
                from_state=trans.from_state,
                to=trans.to,
                event=trans.event,
                params=params,
                guard=trans.guard,
            )
        )
    canonical_transitions.sort(key=lambda t: (t.from_state, t.event, t.to))

    methods: list[CanonicalMethod] = []
    if class_def is not None:
        for m in class_def.methods:
            if m.action is None:
                continue
            params_sig = ", ".join(f"{p.name}: {p.type}" for p in m.params)
            methods.append(CanonicalMethod(
                name=m.name,
                params_sig=params_sig,
                return_type=m.return_type,
                action=m.action,
            ))
        methods.sort(key=lambda m: m.name)

    return CanonicalStateDiagram(
        type="state_diagram",
        domain=domain,
        class_name=sd.class_name,
        initial_state=sd.initial_state,
        states=canonical_states,
        transitions=canonical_transitions,
        methods=methods,
    )
```

- [ ] **Step 6: Update the JSON wrapper functions**

```python
def yaml_to_canonical_class_json(
    domain: str,
    cd: "ClassDiagramFile",
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> str:
    """Return canonical JSON string (drop-in for drawio.py's _yaml_to_canonical_class)."""
    return json.dumps(
        yaml_to_canonical_class(domain, cd, op_lookup).model_dump(by_alias=True),
        sort_keys=True,
    )


def yaml_to_canonical_state_json(
    domain: str,
    sd: "StateDiagramFile",
    class_def: "ClassDef | None" = None,
) -> str:
    """Return canonical JSON string (drop-in for drawio.py's _yaml_to_canonical_state)."""
    return json.dumps(
        yaml_to_canonical_state(domain, sd, class_def).model_dump(by_alias=True),
        sort_keys=True,
    )
```

Also add `ClassDef` to the `TYPE_CHECKING` imports at the top:
```python
if TYPE_CHECKING:
    from schema.yaml_schema import ClassDef, ClassDiagramFile, StateDiagramFile
```

- [ ] **Step 7: Run tests**

```
python -m pytest tests/test_canonical_builder.py tests/ -x -q
```
Expected: all pass

- [ ] **Step 8: Commit**

```
git add schema/canonical_builder.py tests/test_canonical_builder.py
git commit -m "feat: extend canonical builder with bridge impl and method data"
```

---

### Task 4: Class diagram — bridge impl boxes

**Files:**
- Modify: `tools/drawio.py`
- Test: `tests/test_drawio_impl_boxes.py` (create)

**Interfaces:**
- Consumes: `STYLE_IMPL_BOX`, `bridge_impl_id` from Task 1; `CanonicalBridgeImpl` from Task 2; updated `yaml_to_canonical_class_json` from Task 3
- Produces: updated `render_to_drawio_class()`, `_build_class_diagram_xml()`, `_content_matches_class()`, `_drawio_to_canonical_class()`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_drawio_impl_boxes.py
import pytest
import yaml
from pathlib import Path
from lxml import etree

# ── helpers ──────────────────────────────────────────────────────────────────

def _write_domains(tmp_path: Path, ops: list[dict]) -> None:
    content = {
        "schema_version": "1.0.0",
        "domains": [
            {"name": "Test", "type": "application", "description": "d"},
            {"name": "Foo",  "type": "realized",    "description": "d"},
        ],
        "bridges": [{
            "from": "Foo",
            "to": "Test",
            "operations": ops,
        }],
    }
    (tmp_path / "DOMAINS.yaml").write_text(yaml.dump(content), encoding="utf-8")


def _write_class_diagram(tmp_path: Path, impls: list[dict]) -> None:
    (tmp_path / "Test").mkdir(exist_ok=True)
    content = {
        "schema_version": "1.0.0",
        "domain": "Test",
        "classes": [{"name": "Widget", "stereotype": "entity",
                      "attributes": [{"name": "id", "type": "UniqueID", "identifier": True}]}],
        "associations": [],
        "bridges": [{
            "to_domain": "Foo",
            "direction": "provided",
            "implementations": impls,
        }],
    }
    (tmp_path / "Test" / "class-diagram.yaml").write_text(yaml.dump(content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)


def _render_class(tmp_path: Path, domain: str = "Test") -> list[dict]:
    import importlib
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        return dw.render_to_drawio_class(domain, force=True)
    finally:
        dw.MODEL_ROOT = orig


# ── class diagram bridge impl tests ──────────────────────────────────────────

def test_bridge_impl_box_appears_in_xml(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": [{"name": "x", "type": "Integer"}], "return": "Boolean"}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "return x > 0;"}])
    results = _render_class(tmp_path)
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id") for el in tree.iter("mxCell")]
    assert "test:bridge_impl:Foo:DoThing" in ids

def test_bridge_impl_box_header_contains_signature(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": [{"name": "x", "type": "Integer"}], "return": "Boolean"}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "return x > 0;"}])
    _render_class(tmp_path)
    xml = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    tree = etree.fromstring(xml)
    for el in tree.iter("mxCell"):
        if el.get("id") == "test:bridge_impl:Foo:DoThing":
            value = el.get("value", "")
            assert "DoThing" in value
            assert "x: Integer" in value
            assert "Boolean" in value
            assert "return x &gt; 0;" in value
            break
    else:
        pytest.fail("bridge_impl cell not found")

def test_missing_domains_yaml_returns_error(tmp_path):
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    # No DOMAINS.yaml written
    results = _render_class(tmp_path)
    assert any(r.get("severity") == "error" for r in results)
    assert not (tmp_path / "diagrams" / "Test-class-diagram.drawio").exists()

def test_missing_operation_in_domains_returns_error(tmp_path):
    _write_domains(tmp_path, [{"name": "OtherOp", "params": []}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    results = _render_class(tmp_path)
    assert any(r.get("severity") == "error" for r in results)

def test_class_diagram_skip_when_unchanged(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": []}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    r1 = _render_class(tmp_path)
    assert r1[0]["status"] == "written"
    r2 = _render_class(tmp_path)  # second render without force
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        r2 = dw.render_to_drawio_class("Test")
    finally:
        dw.MODEL_ROOT = orig
    assert r2[0]["status"] == "skipped"

def test_class_diagram_rerenders_when_action_changes(tmp_path):
    _write_domains(tmp_path, [{"name": "DoThing", "params": []}])
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 1;"}])
    _render_class(tmp_path)
    xml_v1 = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    _write_class_diagram(tmp_path, [{"name": "DoThing", "action": "x = 2;"}])
    _render_class(tmp_path)
    xml_v2 = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    assert xml_v1 != xml_v2

def test_class_diagram_no_impl_box_when_no_provided_bridges(tmp_path):
    # Domain with no bridges at all — DOMAINS.yaml not required
    (tmp_path / "Test").mkdir(exist_ok=True)
    content = {
        "schema_version": "1.0.0", "domain": "Test",
        "classes": [{"name": "Widget", "stereotype": "entity",
                      "attributes": [{"name": "id", "type": "UniqueID", "identifier": True}]}],
        "associations": [], "bridges": [],
    }
    (tmp_path / "Test" / "class-diagram.yaml").write_text(yaml.dump(content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)
    results = _render_class(tmp_path)
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-class-diagram.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert not any("bridge_impl" in i for i in ids)
```

- [ ] **Step 2: Run to confirm failure**

```
python -m pytest tests/test_drawio_impl_boxes.py -x -q
```
Expected: tests fail (no impl boxes rendered yet)

- [ ] **Step 3: Add imports to `tools/drawio.py`**

Find the existing import block and add:
```python
from schema.drawio_schema import (
    BIJECTION_TABLE,
    STYLE_ASSOC_LABEL,
    STYLE_ASSOCIATION,
    STYLE_ATTRIBUTE,
    STYLE_CLASS,
    STYLE_CLASS_ACTIVE,
    STYLE_GENERALIZATION,
    STYLE_IMPL_BOX,       # NEW
    STYLE_INITIAL_PSEUDO,
    STYLE_SEPARATOR,
    STYLE_STATE,
    STYLE_TRANSITION,
    association_id,
    association_label_id,
    bridge_impl_id,        # NEW
    class_id,
    method_box_id,         # NEW
    separator_id,
    state_id,
    transition_id,
)
from schema.yaml_schema import ClassDiagramFile, StateDiagramFile
```

- [ ] **Step 4: Add new constants after existing ones (around line 58)**

```python
IMPL_BOX_W = 400          # width of bridge impl / method boxes
IMPL_BOX_HEADER_H = 30    # header height for impl boxes
IMPL_BOX_GAP = 20         # vertical gap between stacked impl boxes
IMPL_COL_OFFSET = 60      # horizontal gap from right edge of main content
```

- [ ] **Step 5: Add helper functions after `_class_height` (around line 108)**

```python
def _impl_box_height(action: str) -> int:
    """Height of an impl box based on action body line count."""
    n_lines = action.count("\n") + 1
    return IMPL_BOX_HEADER_H + max(n_lines, 3) * ROW_H


def _impl_box_body(action: str) -> str:
    """Format pycca action body for an impl box value string."""
    return html.escape(action).replace("\n", "<br>")


def _impl_box_header_bridge(name: str, op: object) -> str:
    """Format bridge impl box header: <b>name(params): return</b>."""
    if op is None:
        return f"<b>{name}</b>"
    params_sig = ", ".join(
        f"{p.name}: {_html_escape_type(p.type)}" for p in op.params
    )
    ret = f": {_html_escape_type(op.return_type)}" if op.return_type else ""
    return f"<b>{name}({params_sig}){ret}</b>"


def _impl_box_header_method(m: object) -> str:
    """Format method box header: <b>vis name(params): return</b>."""
    sym = _VIS.get(m.visibility, "-")
    params_sig = ", ".join(
        f"{p.name}: {_html_escape_type(p.type)}" for p in m.params
    )
    ret = f": {_html_escape_type(m.return_type)}" if m.return_type else ""
    return f"<b>{sym} {m.name}({params_sig}){ret}</b>"


_IMPL_DIVIDER = "──────────────────"


def _parse_impl_box_value(value: str) -> tuple[str, "str | None", str]:
    """Parse an impl box cell value back into (params_sig, return_type, action).

    Expects format: <b>header</b><br>─...─<br>body
    """
    import re as _re
    parts = _re.split(r"<br>─+<br>", value, maxsplit=1)
    if len(parts) != 2:
        return "", None, ""
    raw_header, raw_body = parts
    # Strip bold tags and visibility symbol
    header = _re.sub(r"</?b>", "", raw_header).strip()
    header = _re.sub(r"^[+\-#] ", "", header)
    header = html.unescape(header)
    m = _re.match(r"^[^(]+\(([^)]*)\)(?:: (.+))?$", header)
    params_sig = m.group(1).strip() if m else ""
    return_type = (m.group(2).strip() if m and m.group(2) else None)
    action = html.unescape(raw_body.replace("<br>", "\n"))
    return params_sig, return_type, action
```

- [ ] **Step 6: Add op_lookup building and validation to `render_to_drawio_class`**

Find `render_to_drawio_class` (around line 1920). After loading and validating `class-diagram.yaml`, add:

```python
    from schema.yaml_schema import DomainsFile, ProvidedBridge

    # Build op_lookup only if there are provided bridges
    provided_bridges = [b for b in cd.bridges if isinstance(b, ProvidedBridge)]
    op_lookup: dict[str, dict[str, object]] | None = None

    if provided_bridges:
        domains_yaml_path = domain_path.parent / "DOMAINS.yaml"
        if not domains_yaml_path.exists():
            return [_make_issue(
                "DOMAINS.yaml not found — required to render bridge implementation signatures",
                location=f"domain={domain}",
                severity="error",
            )]
        try:
            raw_d = yaml.safe_load(domains_yaml_path.read_text(encoding="utf-8"))
            domains_file = DomainsFile.model_validate(raw_d)
        except Exception as exc:
            return [_make_issue(
                f"Failed to load DOMAINS.yaml: {exc}",
                location=str(domains_yaml_path),
                severity="error",
            )]

        # Build lookup: to_domain (from_domain in DOMAINS.yaml) -> op_name -> BridgeOperation
        # A provided bridge in class-diagram (to_domain=X) corresponds to a DOMAINS.yaml
        # entry where from_domain=X and to=current_domain.
        op_lookup = {}
        for bridge_entry in domains_file.bridges:
            if bridge_entry.to.lower() == domain.lower():
                op_lookup.setdefault(bridge_entry.from_domain, {})
                for op in bridge_entry.operations:
                    op_lookup[bridge_entry.from_domain][op.name] = op

        # Validate every implementation has a matching operation
        for pb in provided_bridges:
            for impl in pb.implementations:
                if impl.name not in op_lookup.get(pb.to_domain, {}):
                    return [_make_issue(
                        f"Bridge implementation '{impl.name}' (to_domain={pb.to_domain}) "
                        f"has no matching BridgeOperation in DOMAINS.yaml",
                        location=f"domain={domain}, bridge.to_domain={pb.to_domain}",
                        severity="error",
                    )]
```

Then update the two calls that follow to pass `op_lookup`:
```python
    if not force and _content_matches_class(domain_path, domain, cd, op_lookup):
        return [{"file": str(drawio_path), "status": "skipped"}]

    xml_bytes = _build_class_diagram_xml(domain, cd, op_lookup=op_lookup)
```

- [ ] **Step 7: Update `_yaml_to_canonical_class` and `_content_matches_class` signatures**

```python
def _yaml_to_canonical_class(
    domain: str, cd: ClassDiagramFile,
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> str:
    from schema.canonical_builder import yaml_to_canonical_class_json
    return yaml_to_canonical_class_json(domain, cd, op_lookup)


def _content_matches_class(
    domain_path: Path, domain: str, cd: ClassDiagramFile,
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> bool:
    drawio_path = domain_path.parent / "diagrams" / f"{domain}-class-diagram.drawio"
    yaml_canonical = _yaml_to_canonical_class(domain, cd, op_lookup)
    drawio_canonical = _drawio_to_canonical_class(drawio_path)
    if drawio_canonical is None:
        return False
    return yaml_canonical == drawio_canonical
```

- [ ] **Step 8: Update `_build_class_diagram_xml` to accept and render impl boxes**

Change the function signature:
```python
def _build_class_diagram_xml(
    domain: str,
    cd: ClassDiagramFile,
    use_layout: bool = True,
    layout: str = "kamada_kawai",
    include_edges: bool = True,
    route_edges: bool = True,
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> bytes:
```

After the main layout is computed but before building `mxfile`, pre-compute impl box specs:

```python
    from schema.yaml_schema import ProvidedBridge

    impl_box_specs: list[tuple[str, str, str, object]] = []
    if op_lookup:
        for bridge in cd.bridges:
            if not isinstance(bridge, ProvidedBridge):
                continue
            for impl in bridge.implementations:
                op = op_lookup.get(bridge.to_domain, {}).get(impl.name)
                impl_box_specs.append((bridge.to_domain, impl.name, impl.action, op))
        impl_box_specs.sort(key=lambda s: (s[0], s[1]))
```

Then update canvas dimension computation to factor in impl boxes (replace the existing `canvas_w`/`canvas_h` block):

```python
    main_max_x = max((positions[i][0] + node_widths[i]  for i in range(n)), default=0)
    main_max_y = max((positions[i][1] + node_heights[i] for i in range(n)), default=0)

    if impl_box_specs:
        box_col_x = int(main_max_x) + IMPL_COL_OFFSET
        impl_heights = [_impl_box_height(spec[2]) for spec in impl_box_specs]
        total_impl_h = sum(impl_heights) + IMPL_BOX_GAP * (len(impl_heights) - 1)
        canvas_w = box_col_x + IMPL_BOX_W + MARGIN
        canvas_h = max(int(main_max_y) + MARGIN, MARGIN + total_impl_h + MARGIN)
    else:
        canvas_w = int(main_max_x) + MARGIN
        canvas_h = int(main_max_y) + MARGIN
```

At the end of the function, after generalization edges (before `etree.indent`), add impl boxes:

```python
    # Bridge implementation boxes
    if impl_box_specs:
        box_y = MARGIN
        for to_domain, impl_name, action, op in impl_box_specs:
            bid = bridge_impl_id(domain, to_domain, impl_name)
            header = _impl_box_header_bridge(impl_name, op)
            body = _impl_box_body(action)
            value = f"{header}<br>{_IMPL_DIVIDER}<br>{body}"
            h = _impl_box_height(action)
            impl_cell = etree.SubElement(
                root_el, "mxCell",
                id=bid, value=value,
                style=STYLE_IMPL_BOX, vertex="1", parent="1",
            )
            etree.SubElement(
                impl_cell, "mxGeometry",
                x=str(box_col_x), y=str(box_y),
                width=str(IMPL_BOX_W), height=str(h),
                attrib={"as": "geometry"},
            )
            box_y += h + IMPL_BOX_GAP
```

- [ ] **Step 9: Update `_drawio_to_canonical_class` to parse bridge_impl cells**

At the end of `_drawio_to_canonical_class`, after `canonical_gens` is built and before constructing `model`, add:

```python
    from schema.drawio_canonical import CanonicalBridgeImpl

    # --- Bridge impl boxes ---
    bridge_impls: list[CanonicalBridgeImpl] = []
    for cid, el in cells.items():
        parts = cid.split(":")
        # Pattern: domain:bridge_impl:to_domain:impl_name (4 parts)
        if len(parts) != 4 or parts[1] != "bridge_impl":
            continue
        to_domain = parts[2]
        impl_name = parts[3]
        value = el.get("value", "")
        params_sig, return_type, action = _parse_impl_box_value(value)
        bridge_impls.append(CanonicalBridgeImpl(
            name=impl_name,
            to_domain=to_domain,
            params_sig=params_sig,
            return_type=return_type,
            action=action,
        ))
    bridge_impls.sort(key=lambda b: (b.to_domain, b.name))
```

And update the `CanonicalClassDiagram` construction to include `bridge_impls`:
```python
    model = CanonicalClassDiagram(
        type="class_diagram",
        domain=domain,
        classes=canonical_classes,
        associations=canonical_assocs,
        generalizations=canonical_gens,
        bridge_impls=bridge_impls,
    )
```

Also add the import for `CanonicalBridgeImpl` at the top of the function (or at file level):
The function already does a local import block — add `CanonicalBridgeImpl` there.

- [ ] **Step 10: Run tests**

```
python -m pytest tests/test_drawio_impl_boxes.py -x -q
```
Expected: all 7 class diagram tests pass

- [ ] **Step 11: Run full suite**

```
python -m pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 12: Commit**

```
git add tools/drawio.py tests/test_drawio_impl_boxes.py
git commit -m "feat: render bridge implementation boxes in class diagrams"
```

---

### Task 5: State diagram — method boxes

**Files:**
- Modify: `tools/drawio.py`
- Modify: `tests/test_drawio_impl_boxes.py` (add state diagram tests)

**Interfaces:**
- Consumes: `method_box_id` from Task 1; `CanonicalMethod` from Task 2; `_impl_box_header_method`, `_impl_box_body`, `_impl_box_height`, `_parse_impl_box_value` from Task 4; updated `yaml_to_canonical_state_json` from Task 3
- Produces: updated `render_to_drawio_state()`, `_build_state_diagram_xml()`, `_content_matches_state()`, `_drawio_to_canonical_state()`

- [ ] **Step 1: Add state diagram tests to `tests/test_drawio_impl_boxes.py`**

```python
# ── state diagram method tests ────────────────────────────────────────────────

def _write_state_diagram(tmp_path: Path, class_name: str, methods: list[dict]) -> None:
    sd_dir = tmp_path / "Test" / "state-diagrams"
    sd_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "schema_version": "1.0.0",
        "domain": "Test",
        "class": class_name,
        "initial_state": "Idle",
        "states": [{"name": "Idle"}],
        "transitions": [],
    }
    (sd_dir / f"{class_name}.yaml").write_text(yaml.dump(content), encoding="utf-8")
    # Write class-diagram.yaml so methods can be loaded
    (tmp_path / "Test").mkdir(exist_ok=True)
    cd_content = {
        "schema_version": "1.0.0", "domain": "Test",
        "classes": [{"name": class_name, "stereotype": "active",
                      "attributes": [], "methods": methods}],
        "associations": [], "bridges": [],
    }
    (tmp_path / "Test" / "class-diagram.yaml").write_text(yaml.dump(cd_content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)


def _render_state(tmp_path: Path, class_name: str = "Widget") -> list[dict]:
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        return dw.render_to_drawio_state("Test", class_name, force=True)
    finally:
        dw.MODEL_ROOT = orig


def test_method_box_appears_in_state_diagram(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [{"name": "n", "type": "Integer"}], "return": "Boolean",
        "action": "return n > 0;",
    }])
    results = _render_state(tmp_path, "Widget")
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Widget:doWork" in ids

def test_method_box_header_and_body(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [{"name": "n", "type": "Integer"}], "return": "Boolean",
        "action": "return n > 0;",
    }])
    _render_state(tmp_path, "Widget")
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    for el in tree.iter("mxCell"):
        if el.get("id") == "test:method:Widget:doWork":
            value = el.get("value", "")
            assert "+ doWork" in value
            assert "n: Integer" in value
            assert "Boolean" in value
            assert "return n &gt; 0;" in value
            break
    else:
        pytest.fail("method cell not found")

def test_method_with_null_action_omitted(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 1;",
    }, {
        "name": "noAction", "visibility": "private", "scope": "instance",
    }])
    _render_state(tmp_path, "Widget")
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert "test:method:Widget:doWork" in ids
    assert "test:method:Widget:noAction" not in ids

def test_method_boxes_absent_when_no_class_diagram(tmp_path):
    # State diagram exists but no class-diagram.yaml
    sd_dir = tmp_path / "Test" / "state-diagrams"
    sd_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "schema_version": "1.0.0", "domain": "Test", "class": "Widget",
        "initial_state": "Idle", "states": [{"name": "Idle"}], "transitions": [],
    }
    (sd_dir / "Widget.yaml").write_text(yaml.dump(content), encoding="utf-8")
    (tmp_path / "diagrams").mkdir(exist_ok=True)
    results = _render_state(tmp_path, "Widget")
    # Should succeed — no error
    assert results[0]["status"] == "written"
    xml = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    tree = etree.fromstring(xml)
    ids = [el.get("id", "") for el in tree.iter("mxCell")]
    assert not any("method" in i for i in ids)

def test_state_diagram_skip_when_unchanged(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 1;",
    }])
    _render_state(tmp_path, "Widget")
    import tools.drawio as dw
    orig = dw.MODEL_ROOT
    dw.MODEL_ROOT = tmp_path
    try:
        r2 = dw.render_to_drawio_state("Test", "Widget")
    finally:
        dw.MODEL_ROOT = orig
    assert r2[0]["status"] == "skipped"

def test_state_diagram_rerenders_when_method_action_changes(tmp_path):
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 1;",
    }])
    _render_state(tmp_path, "Widget")
    xml_v1 = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    _write_state_diagram(tmp_path, "Widget", [{
        "name": "doWork", "visibility": "public", "scope": "instance",
        "params": [], "action": "x = 2;",
    }])
    _render_state(tmp_path, "Widget")
    xml_v2 = (tmp_path / "diagrams" / "Test-Widget.drawio").read_bytes()
    assert xml_v1 != xml_v2
```

- [ ] **Step 2: Run to confirm failure**

```
python -m pytest tests/test_drawio_impl_boxes.py::test_method_box_appears_in_state_diagram -x -q
```
Expected: FAIL

- [ ] **Step 3: Update `render_to_drawio_state` to load ClassDef**

In `render_to_drawio_state` (around line 1964), after loading and validating `sd`, add:

```python
    from schema.yaml_schema import ClassDiagramFile

    # Attempt to load class-diagram.yaml to extract methods for rendering.
    # Silently skip if missing or the class is not found.
    class_def = None
    cd_path = domain_path / "class-diagram.yaml"
    if cd_path.exists():
        try:
            raw_cd = yaml.safe_load(cd_path.read_text(encoding="utf-8"))
            cd = ClassDiagramFile.model_validate(raw_cd)
            for cls in cd.classes:
                if cls.name == class_name:
                    class_def = cls
                    break
        except Exception:
            pass  # silently omit method boxes if class-diagram is malformed
```

Then update the two calls to pass `class_def`:
```python
    if not force and _content_matches_state(domain_path, domain, class_name, sd, class_def):
        return [{"file": str(drawio_path), "status": "skipped"}]

    xml_bytes = _build_state_diagram_xml(domain, sd, class_def=class_def)
```

- [ ] **Step 4: Update `_yaml_to_canonical_state` and `_content_matches_state` signatures**

```python
def _yaml_to_canonical_state(
    domain: str, sd: StateDiagramFile,
    class_def: object = None,
) -> str:
    from schema.canonical_builder import yaml_to_canonical_state_json
    return yaml_to_canonical_state_json(domain, sd, class_def)


def _content_matches_state(
    domain_path: Path, domain: str, class_name: str, sd: StateDiagramFile,
    class_def: object = None,
) -> bool:
    drawio_path = domain_path.parent / "diagrams" / f"{domain}-{class_name}.drawio"
    yaml_canonical = _yaml_to_canonical_state(domain, sd, class_def)
    drawio_canonical = _drawio_to_canonical_state(drawio_path)
    if drawio_canonical is None:
        return False
    return yaml_canonical == drawio_canonical
```

- [ ] **Step 5: Update `_build_state_diagram_xml` to accept ClassDef and append method boxes**

Change the function signature:
```python
def _build_state_diagram_xml(
    domain: str,
    sd: StateDiagramFile,
    class_def: object = None,
) -> bytes:
```

Pre-compute method box specs early in the function body, after `class_name = sd.class_name`:
```python
    method_box_specs: list[object] = []
    if class_def is not None:
        method_box_specs = sorted(
            [m for m in class_def.methods if m.action is not None],
            key=lambda m: m.name,
        )
```

Update canvas dimension computation (replace the existing `canvas_w`/`canvas_h` block):
```python
    main_max_x = max(positions[i][0] + node_widths[i]  for i in range(n_vertices))
    main_max_y = max(positions[i][1] + node_heights[i] for i in range(n_vertices))

    if method_box_specs:
        box_col_x = int(main_max_x) + IMPL_COL_OFFSET
        impl_heights = [_impl_box_height(m.action) for m in method_box_specs]
        total_h = sum(impl_heights) + IMPL_BOX_GAP * (len(impl_heights) - 1)
        canvas_w = box_col_x + IMPL_BOX_W + MARGIN
        canvas_h = max(int(main_max_y) + MARGIN, MARGIN + total_h + MARGIN)
    else:
        canvas_w = int(main_max_x) + MARGIN
        canvas_h = int(main_max_y) + MARGIN
```

After the transition edges loop (before `etree.indent`), append method boxes:
```python
    # Method implementation boxes
    if method_box_specs:
        box_y = MARGIN
        for m in method_box_specs:
            mid = method_box_id(domain, class_name, m.name)
            header = _impl_box_header_method(m)
            body = _impl_box_body(m.action)
            value = f"{header}<br>{_IMPL_DIVIDER}<br>{body}"
            h = _impl_box_height(m.action)
            mbox_cell = etree.SubElement(
                root_el, "mxCell",
                id=mid, value=value,
                style=STYLE_IMPL_BOX, vertex="1", parent="1",
            )
            etree.SubElement(
                mbox_cell, "mxGeometry",
                x=str(box_col_x), y=str(box_y),
                width=str(IMPL_BOX_W), height=str(h),
                attrib={"as": "geometry"},
            )
            box_y += h + IMPL_BOX_GAP
```

- [ ] **Step 6: Update `_drawio_to_canonical_state` to parse method cells**

At the end of `_drawio_to_canonical_state`, before constructing `model`, add:

```python
    from schema.drawio_canonical import CanonicalMethod

    # --- Method boxes ---
    methods: list[CanonicalMethod] = []
    for cell in cells:
        cid = cell.get("id", "")
        parts = cid.split(":")
        # Pattern: domain:method:class_name:method_name (4 parts)
        if len(parts) != 4 or parts[1] != "method":
            continue
        method_name = parts[3]
        value = cell.get("value", "")
        params_sig, return_type, action = _parse_impl_box_value(value)
        methods.append(CanonicalMethod(
            name=method_name,
            params_sig=params_sig,
            return_type=return_type,
            action=action,
        ))
    methods.sort(key=lambda m: m.name)
```

Update `CanonicalStateDiagram` construction:
```python
    model = CanonicalStateDiagram(
        type="state_diagram",
        domain=domain,
        class_name=class_name,
        initial_state=initial_state,
        states=states,
        transitions=transitions,
        methods=methods,
    )
```

Note: `_drawio_to_canonical_state` uses `cells = list(tree.iter("mxCell"))` — the loop over `cells` uses the list form, consistent with the existing code.

- [ ] **Step 7: Run all impl box tests**

```
python -m pytest tests/test_drawio_impl_boxes.py -x -q
```
Expected: all 13 tests pass

- [ ] **Step 8: Run full suite**

```
python -m pytest tests/ -x -q
```
Expected: all pass

- [ ] **Step 9: Commit**

```
git add tools/drawio.py tests/test_drawio_impl_boxes.py
git commit -m "feat: render method boxes in state diagrams"
```
