# Typed Python Emission — Design Spec

**Date:** 2026-06-30
**Status:** Draft
**Supersedes:** `2026-06-30-type-aware-transformer-design.md` (custom type system approach — abandoned)

---

## 1. Problem

`compiler/transformer.py` dispatches `method_call_stmt` purely by method name, with no
knowledge of the receiver's type. The clearest symptom is COMP-001:

| Receiver | Correct Python | Current emission |
|----------|---------------|-----------------|
| `Map<K,V>.remove(k)` | `obj.pop(k, None)` | `obj.pop(k, None)` ✓ |
| `Set<T>.remove(x)` | `obj.discard(x)` | `obj.pop(x, None)` ✗ |
| `List<T>.remove(x)` | `obj.remove(x)` | `obj.pop(x, None)` ✗ |

Beyond this bug, the compiler emits no type annotations, so errors in action bodies
(wrong field access, incompatible types, invalid method calls) are only caught at
runtime — or not at all.

---

## 2. Approach

Rather than building a custom type system, wrap Python's. The compiler emits typed
`.py` files; mypy validates them at compile time. No custom `MDFType`, `SymbolScope`,
or `TypedExpr` infrastructure is needed.

---

## 3. Goals

| ID | Goal |
|----|------|
| G-1 | Fix COMP-001: `remove` on Set/List emits correct Python |
| G-2 | Typed local variables from `typed_var_decl` declarations |
| G-3 | Typed `self_dict` — action functions know the class's attribute types |
| G-4 | Typed `params` — action functions know the event's parameter types |
| G-5 | mypy runs as part of compilation; type errors = compile errors |
| G-6 | Type errors map back to MDF source file and line |

---

## 4. Non-Goals

- Grammar changes — `pycca/grammar.py` is not touched
- Engine changes — instance representation stays as `dict` at runtime
- Type inference beyond explicit `typed_var_decl` declarations
- Typed `self_dict` for `select_stmt`/`create_stmt` results (only pre-seeded `self`)
- Flow-sensitive type narrowing (e.g. Optional narrowing after `has_value()` check)

---

## 5. Architecture

Four changes to the existing pipeline:

```
pycca source
    │
    ▼
compiler/transformer.py     (1) typed_var_decl emits "var: PythonType = expr"
    │                           remove dispatch → _mdf_remove(obj, arg)
    ▼
compiler/codegen.py         (2) generates TypedDict per class + per event
    │                           at top of each class module; action/guard
    │                           signatures reference them
    ▼
generated/*.py              typed Python files (existing output, now annotated)
    │
    ▼
compiler/mypy_check.py      (3) NEW — runs mypy.api on generated files,
    │                           maps errors back to MDF source via
    │                           "# from file:line" comments (D-05)
    │
mdf/runtime.py              (4) NEW — _mdf_remove(container, item) and
                                future runtime dispatch helpers
```

**Files changed:** `compiler/transformer.py`, `compiler/codegen.py`,
`compiler/__init__.py`

**Files added:** `compiler/mypy_check.py`, `mdf/runtime.py`

**Files unchanged:** `engine/`, `schema/`, `pycca/`, all tools

---

## 6. MDF → Python Type Mapping

A pure function `mdf_type_to_python(type_str: str) -> str` in `compiler/type_utils.py`
(new). Single entry point for all MDF type string → Python type string conversion.
Parameters are resolved recursively. Placed in its own module to avoid a circular
import: both `compiler/transformer.py` and `compiler/codegen.py` import it.

| MDF type | Python type |
|----------|-------------|
| `Map<K,V>` | `dict[K, V]` |
| `Set<T>` | `set[T]` |
| `List<T>` | `list[T]` |
| `Optional<T>` | `T \| None` |
| `Integer` | `int` |
| `Real` | `float` |
| `String` | `str` |
| `Boolean` | `bool` |
| Any enum name | itself (emitted as `enum.Enum` in the module) |
| Any typedef name | itself (emitted as `NewType` in the module) |
| Any class name | itself (TypedDict for that class, emitted in the module) |

Enum, typedef, and class names pass through unchanged — their definitions are
already emitted at the top of the same module, so mypy resolves them locally.

**Type system rules:**
- Nominal typing only. `FloorNumber` and `Integer` are never compatible unless
  they are the same string. No structural subtyping, no base-type resolution.
- Container methods are per-type, not per-name. `Map.remove` and `Set.remove`
  are independent dispatch cases that share a keyword.
- Non-container types (classes, defined types, scalars) have no container methods.
  mypy enforces this automatically — `set[T]` has no `.put()`, `dict` has no
  `.discard()`, etc.

---

## 7. TypedDict Generation — `compiler/codegen.py`

Generated at the top of each class module, after existing enum/NewType blocks,
before action/guard functions.

### 7.1 Class TypedDict

One per domain class. Keyed to match the `self_dict["attr"]` access pattern
already emitted by the transformer.

```python
class ElevatorDict(TypedDict):
    __class_name__: str
    __instance_key__: str
    current_floor: FloorNumber
    direction: Direction
    # ... one entry per attribute, type mapped via mdf_type_to_python()
```

`__class_name__` and `__instance_key__` are always `str` — present on every
instance dict by engine convention.

### 7.2 Event TypedDict

One per event that carries parameters. Named `<EventName>Params`.

```python
class ArriveAtFloorParams(TypedDict):
    floor: FloorNumber
```

Events with no parameters get no TypedDict — `params` stays typed as `dict`
for those action functions.

### 7.3 Updated Action and Guard Signatures

```python
def action_Moving_Up_entry(
    ctx: "SimulationContext",
    self_dict: "ElevatorDict",
    params: "ArriveAtFloorParams",
) -> None:
    ...

def guard_Idle_CallReceived(
    self_dict: "ElevatorDict",
    params: "CallReceivedParams",
) -> bool:
    ...
```

Both types are quoted strings (forward references under the existing
`TYPE_CHECKING` guard) — no circular import risk with the engine.

When the triggering event has no parameters, `params: dict` is used unchanged.

---

## 8. Transformer Changes — `compiler/transformer.py`

Two targeted changes only.

### 8.1 `typed_var_decl` emits type annotations

```python
# Before
def typed_var_decl(self, children):
    _type_str = children[0]  # noqa: F841 — discarded
    var, expr = _tok(children[1]), children[2]
    return f"{var} = {expr}"

# After
def typed_var_decl(self, children):
    py_type = mdf_type_to_python(_tok(children[0]))
    var, expr = _tok(children[1]), children[2]
    return f"{var}: {py_type} = {expr}"
```

### 8.2 `remove` dispatch uses `_mdf_remove`

```python
# Before (in method_call_stmt)
if method == "remove":
    return f"{obj}.pop({args}, None)"

# After
if method == "remove":
    return f"_mdf_remove({obj}, {args})"
```

No other transformer rules change. The transformer remains type-unaware —
all type validation is delegated to mypy.

### 8.3 Runtime import in generated header

`codegen.py` adds to the generated module header:

```python
from mdf.runtime import _mdf_remove
```

---

## 9. `mdf/runtime.py` — Runtime Dispatch Helper

```python
"""mdf/runtime.py — Runtime dispatch helpers for MDF-compiled action code."""
from __future__ import annotations


def _mdf_remove(container: object, item: object) -> None:
    """MDF remove() dispatch — Map → dict.pop, Set → set.discard, List → list.remove."""
    if isinstance(container, dict):
        container.pop(item, None)  # type: ignore[call-arg]
    elif isinstance(container, set):
        container.discard(item)
    elif isinstance(container, list):
        try:
            container.remove(item)
        except ValueError:
            pass
    else:
        raise TypeError(
            f"_mdf_remove: unsupported container type {type(container).__name__}"
        )
```

`discard` is used for sets (silent if absent, consistent with Map's `pop` default).
`list.remove` raises `ValueError` on absent items — caught to match the same
silent-miss semantics.

`_mdf_remove` is the only function needed now. Other container methods
(`put`, `get`, `contains_key`, `keys`, `values`, `size`, `is_empty`,
`peek_front`, `has_value`, `value`) all map unambiguously to a single Python
expression and require no runtime dispatch.

---

## 10. mypy Integration — `compiler/mypy_check.py`

### 10.1 Running mypy

```python
from mypy import api as mypy_api
from compiler.error import CompileError

def check_generated_files(paths: list[str]) -> list[CompileError]:
    stdout, _stderr, exit_code = mypy_api.run([
        "--strict",
        "--no-error-summary",
        *paths,
    ])
    if exit_code == 0:
        return []
    return _parse_mypy_output(stdout, paths)
```

### 10.2 Error mapping

mypy reports errors against generated file paths and line numbers. Each generated
function is preceded by a `# from <model_file>:<line>` comment (D-05, already
in place). `_parse_mypy_output` scans upward from the reported line to find the
nearest preceding `# from` comment to recover the original MDF location:

```
generated/elevator/Elevator.py:42: error: TypedDict "ElevatorDict" has no key "nonexistent"
    → scan upward → "# from elevator/class-diagram.yaml:17"
    → CompileError(file="elevator/class-diagram.yaml", line=17,
                   message='TypedDict "ElevatorDict" has no key "nonexistent"')
```

### 10.3 Invocation point

`compiler/__init__.py` calls `check_generated_files()` immediately after all
class modules are written, before returning the bundle. A failed mypy check
raises `CompilationFailed` through the existing `ErrorAccumulator` — no new
error pathway is needed.

---

## 11. Files Created and Modified

| File | Change |
|------|--------|
| `compiler/transformer.py` | Modified — `typed_var_decl` annotation, `remove` → `_mdf_remove` |
| `compiler/codegen.py` | Modified — TypedDict generation, updated signatures, runtime import |
| `compiler/type_utils.py` | New — `mdf_type_to_python` (shared by transformer and codegen) |
| `compiler/__init__.py` | Modified — invoke `check_generated_files` after codegen |
| `compiler/mypy_check.py` | New — mypy integration and error mapping |
| `mdf/runtime.py` | New — `_mdf_remove` dispatch helper |
| `tests/test_type_utils.py` | New — tests `mdf_type_to_python` |
| `tests/test_runtime.py` | New |
| `tests/test_compiler_transformer.py` | Modified — annotation + remove dispatch tests |
| `tests/test_codegen.py` | Modified — TypedDict generation + signature tests |
| `tests/test_mypy_check.py` | New |

No other files change.

---

## 12. Test Plan

### `tests/test_type_utils.py` (new — tests `compiler/type_utils.py`)

- Primitives: `Integer` → `int`, `String` → `str`, `Boolean` → `bool`, `Real` → `float`
- Generic containers: `Map<String,Integer>` → `dict[str, int]`
- Nested generics: `Map<String,Set<Integer>>` → `dict[str, set[int]]`
- Optional: `Optional<Door>` → `Door | None`
- Passthrough: enum name, typedef name, class name → unchanged

### `tests/test_runtime.py` (new)

- `_mdf_remove` on `dict` — removes key; silent if key absent
- `_mdf_remove` on `set` — discards item; silent if item absent
- `_mdf_remove` on `list` — removes item; silent if item absent
- `_mdf_remove` on unknown type — raises `TypeError`

### `tests/test_compiler_transformer.py` (additions)

- `typed_var_decl` emits `var: python_type = expr`
- `typed_var_decl Map<String,Integer>` → `var: dict[str, int] = ...`
- `remove` call emits `_mdf_remove(obj, arg)` regardless of receiver
- Existing: `test_remove_does_not_clobber_set_semantics` — must pass (COMP-001)

### `tests/test_codegen.py` (additions)

- Class module contains `TypedDict` for the class with all attributes + `__class_name__` + `__instance_key__`
- Attribute types are mapped through `mdf_type_to_python`
- Event with parameters generates `<EventName>Params` TypedDict
- Event with no parameters generates no TypedDict
- Action function signature uses the class TypedDict for `self_dict`
- Action function signature uses the event TypedDict for `params` when event has params
- Action function uses `dict` for `params` when event has no params
- `from mdf.runtime import _mdf_remove` appears in the module header

### `tests/test_mypy_check.py` (new)

- Valid generated file with correct TypedDict key access → no errors
- Generated file accessing a nonexistent TypedDict key → `CompileError` with MDF source file and line
- Error line maps correctly via the `# from file:line` comment
