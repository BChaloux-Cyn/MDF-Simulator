# Typed Python Emission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace name-only method dispatch with typed Python emission — annotated `.py` files validated by mypy at compile time, fixing COMP-001 and catching type errors in MDF action bodies.

**Architecture:** The transformer and codegen emit annotated Python using a new `mdf_type_to_python` mapping function. `TypedDict` stubs for each class and event are generated inline in each class module. `mypy.api` runs on the generated source after codegen and maps errors back to MDF source via `# from file:line` comments. A small `mdf/runtime.py` module provides `_mdf_remove()` for the only case where `remove` dispatch differs by container type.

**Tech Stack:** Python 3.11+, `mypy` (programmatic API via `mypy.api`), `black` (existing), `lark` (existing), `pydantic` (existing).

## Global Constraints

- D-01: String templates + black; no `ast` module; no `exec`.
- D-05: Every emitted block preceded by `# from <file>:<line>`.
- D-07: All dicts and iterations sorted.
- D-10: Action sig `(ctx, self_dict, params) -> None`; guard sig `(self_dict, params) -> bool`.
- D-11: `compiler/*` MUST NOT import from `engine/*` at runtime (TYPE_CHECKING only).
- Nominal typing only — `FloorNumber` and `int` are never interchangeable; no base-type resolution.
- Container methods are per-type: `Map.remove` and `Set.remove` are independent dispatch cases.

---

## File Map

| File | Status | Responsibility |
|------|--------|---------------|
| `compiler/type_utils.py` | **New** | `mdf_type_to_python()` — single MDF→Python type mapping entry point |
| `mdf/__init__.py` | **New** | Package marker |
| `mdf/runtime.py` | **New** | `_mdf_remove()` — runtime dispatch for the `remove` ambiguity |
| `compiler/manifest_builder.py` | **Modify** | Populate `events` from `CanonicalTransition.params` |
| `compiler/transformer.py` | **Modify** | `typed_var_decl` emits annotation; `remove` → `_mdf_remove` |
| `compiler/codegen.py` | **Modify** | TypedDict generation, typed signatures, runtime import |
| `compiler/mypy_check.py` | **New** | `check_generated_sources()` — mypy.api + error mapping |
| `compiler/__init__.py` | **Modify** | Call `check_generated_sources` after codegen, before packaging |
| `tests/test_type_utils.py` | **New** | Tests for `mdf_type_to_python` |
| `tests/test_runtime.py` | **New** | Tests for `_mdf_remove` |
| `tests/test_compiler_transformer.py` | **Modify** | Update remove tests; add annotation test |
| `tests/test_codegen.py` | **New** | TypedDict generation + signature tests |
| `tests/test_mypy_check.py` | **New** | mypy integration + error mapping tests |

---

## Task 1: `compiler/type_utils.py` — MDF→Python type mapping

**Files:**
- Create: `compiler/type_utils.py`
- Create: `tests/test_type_utils.py`

**Interfaces:**
- Produces: `mdf_type_to_python(type_str: str) -> str` — imported by Tasks 4 and 5

---

- [ ] **Step 1: Write failing tests**

```python
# tests/test_type_utils.py
import pytest
from compiler.type_utils import mdf_type_to_python


class TestPrimitives:
    def test_integer(self):
        assert mdf_type_to_python("Integer") == "int"

    def test_real(self):
        assert mdf_type_to_python("Real") == "float"

    def test_string(self):
        assert mdf_type_to_python("String") == "str"

    def test_boolean(self):
        assert mdf_type_to_python("Boolean") == "bool"


class TestContainers:
    def test_map(self):
        assert mdf_type_to_python("Map<String,Integer>") == "dict[str, int]"

    def test_set(self):
        assert mdf_type_to_python("Set<Integer>") == "set[int]"

    def test_list(self):
        assert mdf_type_to_python("List<String>") == "list[str]"

    def test_optional(self):
        assert mdf_type_to_python("Optional<Door>") == "Door | None"

    def test_nested(self):
        assert mdf_type_to_python("Map<String,Set<Integer>>") == "dict[str, set[int]]"

    def test_spaces_ignored(self):
        assert mdf_type_to_python("Map<String, Integer>") == "dict[str, int]"


class TestPassthrough:
    def test_enum_name_passes_through(self):
        assert mdf_type_to_python("Direction") == "Direction"

    def test_class_name_passes_through(self):
        assert mdf_type_to_python("Elevator") == "Elevator"

    def test_typedef_name_passes_through(self):
        assert mdf_type_to_python("FloorNumber") == "FloorNumber"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_type_utils.py -v
```
Expected: `ModuleNotFoundError: No module named 'compiler.type_utils'`

- [ ] **Step 3: Implement `compiler/type_utils.py`**

```python
"""compiler/type_utils.py — MDF type string → Python type string conversion."""
from __future__ import annotations

_PRIMITIVES: dict[str, str] = {
    "Integer": "int",
    "Real": "float",
    "String": "str",
    "Boolean": "bool",
}


def mdf_type_to_python(type_str: str) -> str:
    """Convert an MDF type string to its Python equivalent.

    Handles primitives, generic containers (Map/Set/List/Optional), and
    passes all other names through unchanged (enums, typedefs, classes).
    """
    type_str = type_str.strip()
    if type_str in _PRIMITIVES:
        return _PRIMITIVES[type_str]
    if "<" in type_str:
        base, rest = type_str.split("<", 1)
        base = base.strip()
        params_str = rest.rstrip(">").strip()
        params = _split_params(params_str)
        py_params = ", ".join(mdf_type_to_python(p) for p in params)
        if base == "Map":
            return f"dict[{py_params}]"
        if base == "Set":
            return f"set[{py_params}]"
        if base == "List":
            return f"list[{py_params}]"
        if base == "Optional":
            return f"{py_params} | None"
    return type_str


def _split_params(params_str: str) -> list[str]:
    """Split comma-separated type params respecting angle bracket nesting."""
    params: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in params_str:
        if ch == "<":
            depth += 1
            current.append(ch)
        elif ch == ">":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            params.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        params.append("".join(current).strip())
    return params
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_type_utils.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add compiler/type_utils.py tests/test_type_utils.py
git commit -m "feat: add mdf_type_to_python conversion utility"
```

---

## Task 2: `mdf/runtime.py` — runtime dispatch helper

**Files:**
- Create: `mdf/__init__.py`
- Create: `mdf/runtime.py`
- Create: `tests/test_runtime.py`

**Interfaces:**
- Produces: `_mdf_remove(container: object, item: object) -> None` — imported in generated modules

---

- [ ] **Step 1: Write failing tests**

```python
# tests/test_runtime.py
import pytest
from mdf.runtime import _mdf_remove


class TestMdfRemove:
    def test_dict_removes_key(self):
        d = {"a": 1, "b": 2}
        _mdf_remove(d, "a")
        assert d == {"b": 2}

    def test_dict_silent_on_missing_key(self):
        d = {"a": 1}
        _mdf_remove(d, "missing")  # must not raise
        assert d == {"a": 1}

    def test_set_discards_item(self):
        s = {1, 2, 3}
        _mdf_remove(s, 2)
        assert s == {1, 3}

    def test_set_silent_on_missing_item(self):
        s = {1, 2}
        _mdf_remove(s, 99)  # must not raise
        assert s == {1, 2}

    def test_list_removes_item(self):
        lst = [1, 2, 3]
        _mdf_remove(lst, 2)
        assert lst == [1, 3]

    def test_list_silent_on_missing_item(self):
        lst = [1, 2]
        _mdf_remove(lst, 99)  # must not raise
        assert lst == [1, 2]

    def test_unknown_type_raises_type_error(self):
        with pytest.raises(TypeError, match="unsupported container type"):
            _mdf_remove("not_a_container", "x")
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_runtime.py -v
```
Expected: `ModuleNotFoundError: No module named 'mdf'`

- [ ] **Step 3: Create `mdf/__init__.py`**

```python
# mdf/__init__.py
```
(empty — package marker only)

- [ ] **Step 4: Implement `mdf/runtime.py`**

```python
"""mdf/runtime.py — Runtime dispatch helpers for MDF-compiled action code."""
from __future__ import annotations


def _mdf_remove(container: object, item: object) -> None:
    """MDF remove() dispatch — Map → dict.pop, Set → set.discard, List → list.remove."""
    if isinstance(container, dict):
        container.pop(item, None)  # type: ignore[call-arg]
    elif isinstance(container, set):
        container.discard(item)  # type: ignore[arg-type]
    elif isinstance(container, list):
        try:
            container.remove(item)  # type: ignore[arg-type]
        except ValueError:
            pass
    else:
        raise TypeError(
            f"_mdf_remove: unsupported container type {type(container).__name__}"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_runtime.py -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```
git add mdf/__init__.py mdf/runtime.py tests/test_runtime.py
git commit -m "feat: add mdf runtime package with _mdf_remove dispatch helper"
```

---

## Task 3: Populate event parameter types in `manifest_builder`

**Files:**
- Modify: `compiler/manifest_builder.py` — populate `events` from `CanonicalTransition.params`

**Interfaces:**
- Consumes: `CanonicalTransition.params: str | None` (already `"param: Type, ..."` format from `yaml_to_canonical_state`)
- Produces: `build_class_manifest` return dict includes `events: dict[str, str | None]` — event name → params string or None

---

- [ ] **Step 1: Write a failing test**

Add to the existing manifest builder test suite. If `tests/test_manifest_builder.py` does not exist, create it:

```python
# tests/test_manifest_builder.py  (create if absent, otherwise add to existing class)
import pytest
from compiler.manifest_builder import build_class_manifest
from schema.drawio_canonical import CanonicalClassEntry, CanonicalStateDiagram, CanonicalState, CanonicalTransition
from unittest.mock import MagicMock


def _minimal_entry(name="Widget") -> CanonicalClassEntry:
    return CanonicalClassEntry(
        name=name,
        stereotype="active",
        specializes=None,
        attributes=[],
        methods=[],
    )


def _minimal_sd(class_name="Widget") -> CanonicalStateDiagram:
    return CanonicalStateDiagram(
        type="state_diagram",
        domain="test",
        **{"class": class_name},
        initial_state="Idle",
        states=[
            CanonicalState(name="Idle", entry_action=None),
            CanonicalState(name="Active", entry_action=None),
        ],
        transitions=[
            CanonicalTransition(
                **{"from": "Idle"},
                to="Active",
                event="Activate",
                params="level: Integer",
                guard=None,
            ),
            CanonicalTransition(
                **{"from": "Active"},
                to="Idle",
                event="Reset",
                params=None,
                guard=None,
            ),
        ],
    )


class TestClassManifestEvents:
    def test_events_field_present(self):
        parser = MagicMock()
        parser.parse.return_value = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), _minimal_sd(), None, parser
        )
        assert "events" in manifest

    def test_event_with_params_stored(self):
        parser = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), _minimal_sd(), None, parser
        )
        assert manifest["events"]["Activate"] == "level: Integer"

    def test_event_without_params_stored_as_none(self):
        parser = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), _minimal_sd(), None, parser
        )
        assert manifest["events"]["Reset"] is None

    def test_no_state_diagram_gives_empty_events(self):
        parser = MagicMock()
        manifest = build_class_manifest(
            _minimal_entry(), None, None, parser
        )
        assert manifest["events"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_manifest_builder.py::TestClassManifestEvents -v
```
Expected: FAIL — `KeyError: 'events'` or `TypeError`

- [ ] **Step 3: Populate `events` in `build_class_manifest` in `compiler/manifest_builder.py`**

In `build_class_manifest`, collect events from the state diagram transitions. Add this block just before the `return` statement:

```python
    # Collect event parameter signatures from transitions (D-06).
    # CanonicalTransition.params is already formatted as "name: Type, ..."
    # by yaml_to_canonical_state. Unique event names only; first occurrence wins.
    events: dict[str, str | None] = {}
    if sd is not None:
        for trans in sd.transitions:
            if trans.event and trans.event not in events:
                events[trans.event] = trans.params
```

Then add `"events": dict(sorted(events.items())),` to the return dict:

```python
    return {
        "name": entry.name,
        "is_abstract": is_abstract,
        "identifier_attrs": identifier_attrs,
        "attributes": attrs,
        "entry_actions": dict(sorted(entry_actions.items())),
        "initial_state": initial_state,
        "final_states": sorted(final_states),
        "senescent_states": senescent_states,
        "transition_table": transition_table,
        "supertype": None,
        "subtypes": [],
        "events": dict(sorted(events.items())),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_manifest_builder.py::TestClassManifestEvents -v
```
Expected: all PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```
pytest -x -q
```
Expected: all existing tests continue to pass.

- [ ] **Step 6: Commit**

```
git add compiler/manifest_builder.py tests/test_manifest_builder.py
git commit -m "feat: populate event param types in build_class_manifest"
```

---

## Task 4: Transformer changes — annotation emission and `remove` dispatch

**Files:**
- Modify: `compiler/transformer.py`
- Modify: `tests/test_compiler_transformer.py`

**Interfaces:**
- Consumes: `mdf_type_to_python` from `compiler.type_utils` (Task 1)
- Produces: `typed_var_decl` emits `var: py_type = expr`; `remove` method calls emit `_mdf_remove(obj, arg)`

---

- [ ] **Step 1: Update existing `remove` tests and add annotation test**

In `tests/test_compiler_transformer.py`, find and update the two existing `remove` tests, and add one new annotation test. The existing `test_remove_does_not_clobber_set_semantics` already asserts the correct behavior — it just needs the assertion updated to match the new emission pattern:

```python
# Find test_remove_emits_pop and change the assertion:
def test_remove_emits_pop(self):
    """remove statement now emits _mdf_remove dispatch helper."""
    from compiler.transformer import transform_action
    result = transform_action("my_map.remove(key);", "test.yaml", 0)
    assert "_mdf_remove(my_map, key)" in result

# Find test_remove_does_not_clobber_set_semantics and update:
def test_remove_does_not_clobber_set_semantics(self):
    """Set.remove and Map.remove both emit _mdf_remove — runtime dispatches correctly.

    Fixes COMP-001: previously both emitted pop(x, None) which is wrong for Set/List.
    """
    from compiler.transformer import transform_action
    result = transform_action("my_set.remove(x);", "test.yaml", 0)
    assert "_mdf_remove(my_set, x)" in result, (
        f"remove should emit _mdf_remove(...), got: {result!r}"
    )

# Add new annotation test (in the existing Map method test class or a new class):
def test_typed_var_decl_emits_annotation(self):
    """typed_var_decl emits 'var: PythonType = expr'."""
    from compiler.transformer import transform_action
    result = transform_action("Integer count = 0;", "test.yaml", 0)
    assert "count: int = 0" in result

def test_typed_var_decl_map_emits_dict_annotation(self):
    """typed_var_decl Map<String,Integer> emits 'var: dict[str, int] = expr'."""
    from compiler.transformer import transform_action
    result = transform_action("Map<String,Integer> my_map = Map<String,Integer>();", "test.yaml", 0)
    assert "my_map: dict[str, int] = {}" in result
```

- [ ] **Step 2: Run the updated tests to verify they fail**

```
pytest tests/test_compiler_transformer.py::TestMapMethods::test_remove_emits_pop tests/test_compiler_transformer.py::TestMapMethods::test_remove_does_not_clobber_set_semantics tests/test_compiler_transformer.py -k "typed_var_decl_emits" -v
```
Expected: FAIL — assertions don't match current `pop(...)` output; annotation tests fail with `ModuleNotFoundError`.

- [ ] **Step 3: Update `typed_var_decl` in `compiler/transformer.py`**

Find the `typed_var_decl` method (currently at line ~112) and replace it:

```python
def typed_var_decl(self, children: list[Any]) -> str:
    # type_expr NAME "=" expr ";"
    # children: [type_str, NAME token, expr_str]
    from compiler.type_utils import mdf_type_to_python
    py_type = mdf_type_to_python(_tok(children[0]))
    var = _tok(children[1])
    expr = children[2]
    return f"{var}: {py_type} = {expr}"
```

- [ ] **Step 4: Update `remove` dispatch in `method_call_stmt` in `compiler/transformer.py`**

Find `method_call_stmt` (currently at line ~700) and replace the `remove` branch:

```python
if method == "remove":
    return f"_mdf_remove({obj}, {args})"
```

- [ ] **Step 5: Run updated tests to verify they pass**

```
pytest tests/test_compiler_transformer.py -v
```
Expected: all tests PASS, including the previously-failing `test_remove_does_not_clobber_set_semantics`.

- [ ] **Step 6: Commit**

```
git add compiler/transformer.py tests/test_compiler_transformer.py
git commit -m "fix: emit _mdf_remove for remove dispatch; typed_var_decl emits type annotation (COMP-001)"
```

---

## Task 5: Codegen — TypedDict generation and typed signatures

**Files:**
- Modify: `compiler/codegen.py`
- Create: `tests/test_codegen.py`

**Interfaces:**
- Consumes: `mdf_type_to_python` from `compiler.type_utils` (Task 1); `ClassManifest["events"]` (Task 3); `_mdf_remove` (Task 2, via generated import)
- Produces: Generated class modules with TypedDicts and typed action/guard signatures

---

- [ ] **Step 1: Write failing tests**

```python
# tests/test_codegen.py
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
        # guard signature should use dict for param-less event
        assert "params: dict" in src


class TestRuntimeImport:
    def test_mdf_remove_imported(self):
        manifest = _make_manifest()
        src = generate_class_module(manifest, {}, None)
        assert "from mdf.runtime import _mdf_remove" in src


class TestTypedDictImport:
    def test_typeddict_imported(self):
        manifest = _make_manifest()
        src = generate_class_module(manifest, {}, None)
        assert "TypedDict" in src
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_codegen.py -v
```
Expected: multiple FAIL — no TypedDicts in output, old signatures, no `_mdf_remove` import.

- [ ] **Step 3: Add helpers to `compiler/codegen.py`**

At the top of `compiler/codegen.py`, add the import:

```python
from compiler.type_utils import mdf_type_to_python
```

Add these helper functions after `_render_typedef`:

```python
def _parse_event_params(params_str: str) -> dict[str, str]:
    """Parse 'name: Type, ...' into {name: type_str} (D-07: sorted)."""
    result: dict[str, str] = {}
    for part in params_str.split(","):
        name, _, type_str = part.strip().partition(":")
        if name and type_str:
            result[name.strip()] = type_str.strip()
    return dict(sorted(result.items()))


def _render_class_typeddict(cls_name: str, attributes: dict) -> str:
    """Render a TypedDict for a domain class (for self_dict typing)."""
    lines = [f"class {cls_name}Dict(TypedDict):"]
    lines.append("    __class_name__: str")
    lines.append("    __instance_key__: str")
    for attr_name, attr_info in sorted(attributes.items()):
        if isinstance(attr_info, dict):
            attr_type = attr_info.get("type", "object")
            py_type = mdf_type_to_python(attr_type)
            lines.append(f"    {attr_name}: {py_type}")
    return "\n".join(lines)


def _render_event_typeddict(event_name: str, params_str: str) -> str:
    """Render a TypedDict for a parameterised event (for params typing)."""
    params = _parse_event_params(params_str)
    lines = [f"class {event_name}Params(TypedDict):"]
    for param_name, param_type in params.items():
        py_type = mdf_type_to_python(param_type)
        lines.append(f"    {param_name}: {py_type}")
    return "\n".join(lines)


def _state_params_type(
    state: str,
    transition_table: dict,
    events: dict[str, str | None],
) -> str:
    """Return the params TypedDict name for a state's entry action.

    Uses the specific event TypedDict when exactly one event triggers
    this state and that event has params; otherwise falls back to 'dict'.
    """
    triggers: set[str] = set()
    for (_, event), entries in transition_table.items():
        for entry in entries:
            if entry.get("next_state") == state and event:
                triggers.add(event)
    if len(triggers) == 1:
        event_name = next(iter(triggers))
        if events.get(event_name):
            return f"{event_name}Params"
    return "dict"


def _guard_params_type(event: str, events: dict[str, str | None]) -> str:
    """Return the params TypedDict name for a guard on the given event."""
    if events.get(event):
        return f"{event}Params"
    return "dict"
```

- [ ] **Step 4: Update `_render_action_fn` signature in `compiler/codegen.py`**

Replace the existing `_render_action_fn` function:

```python
def _render_action_fn(
    fn_name: str,
    body_src: str,
    source_file: str,
    source_line: int,
    cls_name: str,
    params_type: str = "dict",
) -> str:
    """Render a D-10 action function with typed self_dict and params."""
    comment = f"# from {source_file}:{source_line}"
    if body_src and body_src.strip():
        lines = body_src.split("\n", 1)
        body = lines[1] if len(lines) > 1 else "pass"
    else:
        body = "pass"

    indented = textwrap.indent(body.strip() or "pass", "    ")
    return (
        f"{comment}\n"
        f'def {fn_name}(ctx: "SimulationContext", '
        f'self_dict: "{cls_name}Dict", '
        f'params: "{params_type}") -> None:\n'
        f"{indented}\n"
    )
```

- [ ] **Step 5: Update `_render_guard_fn` signature in `compiler/codegen.py`**

Replace the existing `_render_guard_fn` function:

```python
def _render_guard_fn(
    fn_name: str,
    expr_src: str,
    source_file: str,
    source_line: int,
    cls_name: str,
    params_type: str = "dict",
) -> str:
    """Render a D-10 guard function with typed self_dict and params."""
    comment = f"# from {source_file}:{source_line}"
    if expr_src and expr_src.strip():
        lines = expr_src.split("\n", 1)
        expr = lines[1] if len(lines) > 1 else "True"
    else:
        expr = "True"

    return (
        f"{comment}\n"
        f'def {fn_name}(self_dict: "{cls_name}Dict", '
        f'params: "{params_type}") -> bool:\n'
        f"    return {expr.strip()}\n"
    )
```

- [ ] **Step 6: Update `generate_class_module` in `compiler/codegen.py`**

In `generate_class_module`, make the following changes:

**a)** Extract `events` from the manifest at the top of the function (after existing extractions):

```python
events: dict[str, str | None] = class_manifest.get("events", {})
```

**b)** In the imports block (where `parts` is assembled), change the `typing` import line and add the `mdf.runtime` import:

```python
parts.append("from typing import TYPE_CHECKING, NewType, TypedDict")
# ... (keep existing parts) ...
parts.append("from mdf.runtime import _mdf_remove")
```

**c)** After the existing `typedef_lines` block and before action functions, add TypedDict emission:

```python
# Class TypedDict
parts.append(_render_class_typeddict(cls_name, attributes))
parts.append("")

# Event TypedDicts (only for events that have params, sorted by name)
for event_name in sorted(events.keys()):
    params_str = events[event_name]
    if params_str:
        parts.append(_render_event_typeddict(event_name, params_str))
        parts.append("")
```

**d)** Update the action function rendering calls to pass `cls_name` and params type:

In the loop that builds `action_fn_bodies`, replace `_render_action_fn(fn_name, transformed, source_file, 0)` with:

```python
action_params_type = _state_params_type(state_name, transition_table, events)
block = _render_action_fn(fn_name, transformed, source_file, 0, cls_name, action_params_type)
```

**e)** Update guard function rendering calls to pass `cls_name` and params type:

In the guard building loop, replace `_render_guard_fn(fn_name, transformed, source_file, 0)` with:

```python
guard_params_type = _guard_params_type(event, events)
block = _render_guard_fn(fn_name, transformed, source_file, 0, cls_name, guard_params_type)
```

- [ ] **Step 7: Run tests to verify they pass**

```
pytest tests/test_codegen.py -v
```
Expected: all tests PASS.

- [ ] **Step 8: Run full suite to check regressions**

```
pytest -x -q
```
Expected: all existing tests continue to pass.

- [ ] **Step 9: Commit**

```
git add compiler/codegen.py tests/test_codegen.py
git commit -m "feat: emit TypedDict stubs and typed action/guard signatures in codegen"
```

---

## Task 6: `compiler/mypy_check.py` — mypy integration

**Files:**
- Create: `compiler/mypy_check.py`
- Create: `tests/test_mypy_check.py`
- Modify: `requirements.in` (add `mypy`)

**Interfaces:**
- Produces: `check_generated_sources(sources: dict[str, str]) -> list[CompileError]` — imported by Task 7

---

- [ ] **Step 1: Add mypy to `requirements.in`**

Open `requirements.in` and add:

```
mypy
```

Then sync:

```
uv pip compile requirements.in -o requirements.txt
uv pip sync requirements.txt
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_mypy_check.py
import pytest
from pathlib import Path
from compiler.mypy_check import check_generated_files


_VALID_SOURCE = '''\
# from model.yaml:1
"""Generated module."""
from __future__ import annotations
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


class WidgetDict(TypedDict):
    __class_name__: str
    __instance_key__: str
    count: int


# from model.yaml:10
def action_Active_entry(
    ctx: "SimulationContext",
    self_dict: "WidgetDict",
    params: dict,
) -> None:
    x: int = 1
    self_dict["count"] = x
'''

_INVALID_SOURCE = '''\
# from model.yaml:1
"""Generated module."""
from __future__ import annotations
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


class WidgetDict(TypedDict):
    __class_name__: str
    __instance_key__: str
    count: int


# from model.yaml:20
def action_Active_entry(
    ctx: "SimulationContext",
    self_dict: "WidgetDict",
    params: dict,
) -> None:
    self_dict["nonexistent_field"] = 1
'''


class TestCheckGeneratedFiles:
    def test_valid_source_returns_no_errors(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_VALID_SOURCE)
        errors = check_generated_files([path])
        assert errors == []

    def test_invalid_key_access_returns_error(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_INVALID_SOURCE)
        errors = check_generated_files([path])
        assert len(errors) >= 1
        assert any("nonexistent_field" in e.message for e in errors)

    def test_error_maps_to_mdf_source_file(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_INVALID_SOURCE)
        errors = check_generated_files([path])
        assert any(e.file == "model.yaml" for e in errors)

    def test_error_maps_to_mdf_source_line(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_INVALID_SOURCE)
        errors = check_generated_files([path])
        # The # from comment before the function is "model.yaml:20"
        assert any(e.line == 20 for e in errors)

    def test_empty_paths_returns_no_errors(self):
        errors = check_generated_files([])
        assert errors == []
```

- [ ] **Step 3: Run tests to verify they fail**

```
pytest tests/test_mypy_check.py -v
```
Expected: `ModuleNotFoundError: No module named 'compiler.mypy_check'`

- [ ] **Step 4: Implement `compiler/mypy_check.py`**

```python
"""compiler/mypy_check.py — Run mypy on generated sources and map errors to MDF source."""
from __future__ import annotations

import re
from pathlib import Path

from mypy import api as mypy_api

from compiler.error import CompileError

_MYPY_ERROR_RE = re.compile(r"^(.+?):(\d+): error: (.+)$")
_SOURCE_COMMENT_RE = re.compile(r"^# from (.+?):(\d+)\s*$")


def check_generated_files(paths: list[str]) -> list[CompileError]:
    """Run mypy on generated Python source files and return mapped CompileErrors.

    Args:
        paths: file paths to generated .py files (already written to disk).

    Returns:
        List of CompileErrors with MDF source file/line recovered from
        ``# from <file>:<line>`` comments (D-05).
    """
    if not paths:
        return []

    stdout, _stderr, exit_code = mypy_api.run([
        "--strict",
        "--no-error-summary",
        "--ignore-missing-imports",
        *paths,
    ])

    if exit_code == 0:
        return []

    source_maps = {p: _build_source_map(p) for p in paths}
    return _parse_mypy_output(stdout, source_maps)


def _build_source_map(path: str) -> list[tuple[int, str, int]]:
    """Return (gen_line, mdf_file, mdf_line) for each ``# from`` comment."""
    result: list[tuple[int, str, int]] = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for i, line in enumerate(lines, start=1):
        m = _SOURCE_COMMENT_RE.match(line)
        if m:
            result.append((i, m.group(1), int(m.group(2))))
    return result


def _resolve_source(
    lineno: int,
    source_map: list[tuple[int, str, int]],
) -> tuple[str, int]:
    """Find the nearest ``# from`` comment at or before lineno."""
    best_file, best_line = "<generated>", 0
    for gen_line, mdf_file, mdf_line in source_map:
        if gen_line <= lineno:
            best_file, best_line = mdf_file, mdf_line
        else:
            break
    return best_file, best_line


def _parse_mypy_output(
    stdout: str,
    source_maps: dict[str, list[tuple[int, str, int]]],
) -> list[CompileError]:
    """Parse mypy stdout and return CompileErrors with MDF locations."""
    errors: list[CompileError] = []
    for line in stdout.splitlines():
        m = _MYPY_ERROR_RE.match(line)
        if not m:
            continue
        gen_file, lineno_str, message = m.groups()
        lineno = int(lineno_str)
        source_map = source_maps.get(gen_file, [])
        mdf_file, mdf_line = _resolve_source(lineno, source_map)
        errors.append(CompileError(file=mdf_file, line=mdf_line, message=message))
    return errors
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_mypy_check.py -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```
git add compiler/mypy_check.py tests/test_mypy_check.py requirements.in
git commit -m "feat: add mypy integration module with MDF source error mapping"
```

---

## Task 7: Wire mypy check into `compile_model`

**Files:**
- Modify: `compiler/__init__.py`

**Interfaces:**
- Consumes: `check_generated_files` from `compiler.mypy_check` (Task 6)

---

- [ ] **Step 1: Write a failing integration test**

Add this test to `tests/test_mypy_check.py` (or a new `tests/test_compile_integration.py`):

```python
# Add to tests/test_mypy_check.py

class TestCompileIntegration:
    def test_compile_model_raises_on_mypy_error(self, tmp_path):
        """compile_model raises CompilationFailed when generated code has type errors."""
        # Build a minimal model root with a state diagram whose action contains
        # a TypedDict key error — deliberately wrong attribute name.
        import textwrap
        from compiler import compile_model, CompilationFailed

        domain_dir = tmp_path / "model" / "TestDomain"
        domain_dir.mkdir(parents=True)
        sd_dir = domain_dir / "state-diagrams"
        sd_dir.mkdir()

        (domain_dir / "class-diagram.yaml").write_text(textwrap.dedent("""\
            schema_version: "1.0.0"
            domain: TestDomain
            classes:
              - name: Widget
                stereotype: active
                attributes:
                  - "- count: Integer"
        """))

        (sd_dir / "Widget.yaml").write_text(textwrap.dedent("""\
            schema_version: "1.0.0"
            domain: TestDomain
            class: Widget
            initial_state: Idle
            events: []
            states:
              - name: Idle
                entry_action: "self.nonexistent_field = 1;"
            transitions: []
        """))

        output_dir = tmp_path / "out"
        with pytest.raises(CompilationFailed):
            compile_model(tmp_path / "model", output_dir)
```

- [ ] **Step 2: Run the test to verify it fails**

```
pytest tests/test_mypy_check.py::TestCompileIntegration -v
```
Expected: FAIL — `compile_model` currently does not run mypy, so no error is raised.

- [ ] **Step 3: Add mypy check to `compiler/__init__.py`**

In `compile_model`, between step 3 (codegen) and step 4 (packaging), add the mypy check. Find the line `acc.raise_if_any()` after the codegen loop and add below it:

```python
    acc.raise_if_any()

    # ------------------------------------------------------------------
    # 3b. Type check: run mypy on generated sources
    # ------------------------------------------------------------------
    from compiler.mypy_check import check_generated_files
    mypy_errors = check_generated_files(list(written_paths))  # paths written during codegen loop
    if mypy_errors:
        type_acc = ErrorAccumulator()
        for err in mypy_errors:
            type_acc.add(err)
        type_acc.raise_if_any()
```

- [ ] **Step 4: Run the integration test to verify it passes**

```
pytest tests/test_mypy_check.py::TestCompileIntegration -v
```
Expected: PASS — `CompilationFailed` is now raised on type errors.

- [ ] **Step 5: Run full test suite**

```
pytest -x -q
```
Expected: all tests PASS.

- [ ] **Step 6: Verify COMP-001 is resolved via end-to-end test**

The existing `test_remove_does_not_clobber_set_semantics` should already be passing from Task 4. Confirm:

```
pytest tests/test_compiler_transformer.py::TestMapMethods::test_remove_does_not_clobber_set_semantics -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```
git add compiler/__init__.py
git commit -m "feat: run mypy on generated sources during compile_model (closes COMP-001)"
```

---

## Self-Review Notes

- **Spec coverage:** All 6 goals covered — G-1 (COMP-001 fix, Tasks 2+4), G-2 (typed locals, Task 4), G-3 (typed self_dict, Tasks 3+5), G-4 (typed params, Tasks 3+5), G-5 (mypy at compile time, Tasks 6+7), G-6 (error mapping, Task 6).
- **Type consistency:** `mdf_type_to_python` defined in Task 1 and consumed identically in Tasks 4 and 5. `check_generated_files` signature defined in Task 6 and consumed in Task 7. `events` dict populated in Task 3 and consumed in Task 5.
- **No placeholders:** All code blocks are complete.
- **Dependency order:** 1 → 2 → 3 → 4 → 5 → 6 → 7. Tasks 1, 2, 3 are independent and can run in any order.
