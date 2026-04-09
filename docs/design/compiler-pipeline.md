# Compiler Pipeline Design

## 1. Pipeline Overview

`compiler.compile_model(model_root, output_dir)` runs four sequential stages:

```
YAML files
    │
    ▼  loader.py
LoadedModel
    │
    ▼  manifest_builder.py
DomainManifest (TypedDict, callables=None)
    │
    ▼  codegen.py
dict[class_name → str]   (generated Python source)
    │
    ▼  packager.py
<domain>.mdfbundle        (deterministic zip)
```

### Stage 1 — Load (`compiler/loader.py`)

`load_model(model_root) -> LoadedModel`

Walks `<model_root>/<Domain>/` and validates each file through Pydantic, then
converts to canonical form:

- `class-diagram.yaml` → `ClassDiagramFile` → `CanonicalClassDiagram` (required)
- `state-diagrams/*.yaml` → `StateDiagramFile` → `CanonicalStateDiagram` (optional, per class)
- `types.yaml` → `TypesFile` (optional)

Errors are collected in an `ErrorAccumulator` and raised together as
`CompilationFailed` rather than aborting at the first bad file.

**Output type:**

```python
@dataclass
class LoadedModel:
    class_diagram:  CanonicalClassDiagram
    state_diagrams: dict[str, CanonicalStateDiagram]
    types_raw:      TypesFile | None
    root:           Path
```

### Stage 2 — Manifest Build (`compiler/manifest_builder.py`)

`build_domain_manifest(loaded, parser) -> DomainManifest`

Converts `LoadedModel` canonical objects into `DomainManifest` TypedDicts (defined
in `engine/manifest.py`). This is the only stage where generalization inheritance
is resolved.

Key operations:
- Parse attribute labels from the canonical string form (`+ name: type {tags}`)
  into structured dicts.
- Topological sort of classes (parents before children) so subtype manifests can
  reference their already-built supertype manifest.
- Generalization cases (D-03):
  - **Case A** — entity supertype + active subtype: subtype builds its own transition table.
  - **Case B** — active supertype, subtype has no SM: copy supertype table wholesale.
  - **Case C** — active supertype, subtype redefines SM: build own table.
- Attribute flattening (D-04): supertype attrs first, then own attrs; subtype wins on conflict.
- All dicts sorted by key throughout (D-07).
- `action_fn` and `guard_fn` in every `TransitionEntry` are left `None`; codegen fills them.

### Stage 3 — Code Generation (`compiler/codegen.py`)

`generate_class_module(cls_manifest, type_registry, parser) -> str`

Iterates `manifest["class_defs"]` in sorted class name order. For each class, emits
one Python source module (see section 4). The caller then runs `format_source()` over
each result, which invokes `black.format_str` for canonical formatting.

Errors per class are caught and accumulated; `acc.raise_if_any()` promotes them to a
single `CompilationFailed` after all classes are attempted.

### Stage 4 — Package (`compiler/packager.py`)

`write_bundle(domain_name, files, manifest, output_dir, ...) -> Path`

Writes `<domain>.mdfbundle` — a ZIP containing `bundle.json`, `manifest.json`, and
`generated/<Class>.py` files (see section 5).

---

## 2. D-11 Isolation Constraint

**Rule:** `compiler/` must not import from `engine/` at runtime.

**Rationale:** `engine/` is the consumer of compiler output; importing it from inside
the compiler creates a circular dependency and couples the two layers. The engine may
evolve independently (new runtime features, different scheduling strategies) without
forcing a recompile of the schema layer.

**Mechanism:** The only shared interface is the `DomainManifest` TypedDict shape
defined in `engine/manifest.py`. The compiler references this type exclusively under
`TYPE_CHECKING`:

```python
# compiler/manifest_builder.py, compiler/codegen.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.manifest import DomainManifest, ClassManifest, TransitionEntry
```

At runtime these imports never execute. The TypedDicts are plain dicts; the compiler
constructs them by key name without the engine being loaded.

**Bundle boundary:** The `.mdfbundle` artifact is the physical handoff. The engine
loads `manifest.json` from the bundle and dynamically imports the generated `.py`
modules to rebind `action_fn` / `guard_fn`. The compiler writes; the engine reads.
Neither calls the other.

**Enforcement:** `compiler/__init__.py` documents this constraint and the CI lint
step (or code review) is responsible for catching any new `from engine.` imports
that appear outside a `TYPE_CHECKING` block.

---

## 3. Transformer Self-Rewriting

`compiler/transformer.py` implements `ActionTransformer(Transformer)` — a
bottom-up Lark `Transformer` that converts a pycca parse tree into a Python
source string. Lark's bottom-up contract means each rule method receives
**already-transformed children** (strings), not raw `Tree` nodes.

### Why strings, not AST

Per D-01: no `ast` module, no `exec`. The generated code is formatted by `black`
and stored as plain Python source inside the bundle. This makes bundle diffs
human-readable and avoids the complexity of maintaining a second-level AST.

### Core rewrites

| pycca source | rule | Python output |
|---|---|---|
| `self` (bare) | `name` | `self_dict` |
| `self.attr` | `dotted_name` | `self_dict["attr"]` |
| `self.attr = expr;` | `assignment` | `self_dict["attr"] = expr` |
| `rcvd_evt.field` | `dotted_name` | `params["field"]` |
| `self->R1->R2` | `traversal_chain` | `ctx.traverse(self_dict, ["R1", "R2"])` |
| `generate E(p: v) to t;` | `generate_stmt` | `ctx.generate("E", target=..., args={"p": v})` |

The `self` → `self_dict` rewrite in `name` handles bare `self` in expression context.
The `dotted_name` rule handles `self.attr` — two children `(obj, attr)` — and checks
`obj` to dispatch:

```python
def dotted_name(self, children):
    obj, attr = _tok(children[0]), _tok(children[1])
    if obj == "self":
        return f'self_dict["{attr}"]'
    if obj == "rcvd_evt":
        return f'params["{attr}"]'
    return f'{obj}["{attr}"]'   # other instance variables
```

### Nested expression handling

Because the transformer is bottom-up, nested expressions are already resolved
strings when a parent rule fires. For example:

```
# pycca
self.floor = rcvd_evt.target + 1;
```

Parse tree (simplified): `assignment(NAME("floor"), add_expr(dotted_name("rcvd_evt","target"), NUMBER("1")))`

Transformer walk:
1. `dotted_name(["rcvd_evt", "target"])` → `'params["target"]'`
2. `number(["1"])` → `"1"`
3. `add_expr(['params["target"]', "1"])` → `'params["target"] + 1'`
4. `assignment(["floor", 'params["target"] + 1'])` → `'self_dict["floor"] = params["target"] + 1'`

Arithmetic operators (`+`, `-`, `*`, `/`) arrive as anonymous `Token` objects
between operand children; `add_expr` and `mul_expr` scan the children list for
`isinstance(c, Token)` to recover the operator string.

### Guard transformer

`GuardTransformer(ActionTransformer)` inherits all expression rules and overrides
statement rules to raise `NotImplementedError`. It is used by `transform_guard`,
which parses with `start="expr"` — a single boolean expression, no semicolons.

### Safety

`__default__` raises `NotImplementedError` on any unhandled rule (T-05.2-05).
`__default_token__` converts every token to `str`. These two catches ensure no
`Tree(...)` object can silently leak into emitted source.

---

## 4. Codegen Output Structure

Each call to `generate_class_module(cls_manifest, ...)` produces one Python module.

### Module skeleton

```python
# from <domain>/<ClassName>.yaml:0
"""Generated module for class <ClassName>."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from engine.ctx import SimulationContext

# --- enum / typedef definitions (only types used by this class) ---
class Direction(enum.Enum):
    Down = 'Down'
    Stopped = 'Stopped'
    Up = 'Up'

# --- action functions (one per state, sorted by state name) ---
# from <domain>/Elevator.yaml:0
def action_At_Floor_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    self_dict["current_floor"] = params["floor_num"]
    ctx.generate("Door_open", target=self_dict["__instance_key__"], args={})

# --- guard functions (only emitted when transition has a guard expression) ---
# from <domain>/Elevator.yaml:0
def guard_Moving_Up_Floor_reached(self_dict: dict, params: dict) -> bool:
    return self_dict["next_stop_floor"] == params["floor_num"]

# --- transition table ---
TRANSITION_TABLE: dict = {
    ('At_Floor', 'Close_door'): {'next_state': 'Idle', 'action_fn': action_At_Floor_entry, 'guard_fn': None},
    ('Moving_Up', 'Floor_reached'): {'next_state': 'At_Floor', 'action_fn': action_Moving_Up_entry, 'guard_fn': guard_Moving_Up_Floor_reached},
    ('Moving_Up', 'Stop_requested'): {'next_state': None, 'action_fn': None, 'guard_fn': None},  # event_ignored
}
```

### Action function signature (D-10)

```python
def action_<state>_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
```

- `ctx` — `SimulationContext`; provides `generate`, `create`, `delete`, `relate`,
  `unrelate`, `traverse`, `select_any`, `select_many`, `bridge`.
- `self_dict` — the instance's attribute dict (mutable; keyed by attribute name).
- `params` — the triggering event's parameter dict.

The `SimulationContext` import is inside `TYPE_CHECKING` only; at runtime the
generated function accesses `ctx` as an untyped callable argument.

### Guard function signature (D-10)

```python
def guard_<state>_<event>(self_dict: dict, params: dict) -> bool:
    return <transformed_expression>
```

Two-argument form. Guards have no access to `ctx` — they are pure predicates over
instance state and event parameters.

### Transition table encoding

Keys are `(state: str, event: str)` tuples. Values are `TransitionEntry` dicts:

- **Present cell, `next_state` set** — explicit transition.
- **Present cell, `next_state=None`, all callables `None`** — `event_ignored` (D-13).
- **Absent cell** — `can't_happen`; a `KeyError` in the scheduler produces an
  `ErrorMicroStep` (D-13).

`action_fn` and `guard_fn` hold direct function references (not strings) in the
live table. In `manifest.json` they are serialized as `null` and rebound by the
Phase 5.3 loader after dynamic import.

### `generate_init_module`

`generated/__init__.py` re-exports each class's `TRANSITION_TABLE`:

```python
from .Elevator import TRANSITION_TABLE as Elevator_TRANSITION_TABLE
from .Door import TRANSITION_TABLE as Door_TRANSITION_TABLE
```

This allows the engine to import per-class tables by name without iterating
the zip contents.

---

## 5. Deterministic Bundle Policy

`write_bundle` produces byte-identical output for the same model inputs.

### Sources of non-determinism eliminated

| Source | Fix |
|---|---|
| Zip entry order | All entries written in a fixed sequence: `bundle.json`, `manifest.json`, `generated/__init__.py`, then `generated/<Class>.py` files in sorted class name order |
| Zip modification timestamps | Every `ZipInfo.date_time` is set to `(2020, 1, 1, 0, 0, 0)` (constant `_ZIP_DATE`) |
| Dict iteration order | All dicts sorted by key at construction time (D-07); `json.dumps(..., sort_keys=True)` for serialization |
| Build timestamps | `bundle.json` contains no wall-clock timestamps; only `compiler_version`, `engine_version`, `pycca_version`, and `model_hash` |

### Model hash

`compute_model_hash(generated_files, manifest)` produces a SHA-256 digest over
the sorted `generated_files` dict and the callable-stripped manifest:

```python
payload = {
    "files": {k: generated_files[k] for k in sorted(generated_files)},
    "manifest": manifest,
}
serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
return hashlib.sha256(serialized.encode()).hexdigest()
```

The hash is written into `bundle.json` and can be used by callers to detect
whether a bundle is stale relative to the model source.

### Why determinism matters

- **Caching and incremental builds:** identical input → identical bytes → cache hit.
- **Version control:** bundle diffs are meaningful; timestamp churn does not create
  spurious changes.
- **Reproducible CI:** test assertions on bundle content are stable across machines
  and time zones.

### Callable stripping

`_strip_callables(obj)` recurses through the manifest before JSON serialization,
replacing any callable value with `None`. It also converts `(state, event)` tuple
keys to `"state::event"` strings (JSON does not support tuple keys). The Phase 5.3
bundle loader reverses the key encoding and rebinds callables from the dynamically
imported generated modules.

---

## 6. Key Data Structures

All three TypedDicts are defined in `engine/manifest.py` (shared shape; compiler
constructs them without importing the module at runtime — see section 2).

### `DomainManifest`

```python
class DomainManifest(TypedDict):
    class_defs:      dict[str, ClassManifest]       # sorted by class name
    associations:    dict[str, AssociationManifest] # sorted by rel_id (R1, R2, ...)
    generalizations: dict[str, list[str]]           # supertype → sorted subtypes
```

Top-level container. Serialized to `manifest.json` inside the bundle.

### `ClassManifest`

```python
class ClassManifest(TypedDict):
    name:              str
    is_abstract:       bool
    identifier_attrs:  list[str]                          # sorted attr names forming I1
    attributes:        dict[str, Any]                     # sorted; each value is a parsed attr dict
    entry_actions:     dict[str, str | None]              # state_name → pycca source (codegen input)
    initial_state:     str | None
    final_states:      list[str]                          # sorted
    senescent_states:  list[str]                          # D-14: states with no self-generate
    transition_table:  dict[tuple[str, str], TransitionEntry]
    supertype:         str | None                         # filled post-walk by domain builder
    subtypes:          list[str]                          # sorted; filled post-walk
```

`entry_actions` carries raw pycca source strings at manifest-build time. Codegen
reads these strings, transforms them through `ActionTransformer`, and emits the
resulting `action_<state>_entry` functions. After codegen the field is not used by
the engine (it holds callables via `TransitionEntry.action_fn` instead).

`attributes` values are structured dicts produced by `_parse_attr_label`:
```python
{
    "name":        str,
    "type":        str,
    "visibility":  "public" | "private" | "protected" | "package",
    "scope":       "instance" | "class",
    "identifier":  list[int] | None,   # [1], [1, 2], etc.
    "referential": str | None,         # "R6", etc.
}
```

### `TransitionEntry`

```python
class TransitionEntry(TypedDict):
    next_state: str | None
    action_fn:  Callable | None
    guard_fn:   Callable | None
```

At manifest-build time all cells have `action_fn=None`, `guard_fn=None`. Codegen
populates `TRANSITION_TABLE` in the generated module with direct function
references. The engine scheduler looks up `(current_state, event_name)` in the
loaded table to execute a transition.

### `AssociationManifest`

```python
class AssociationManifest(TypedDict):
    rel_id:     str   # "R1", "R2", ...
    class_a:    str
    class_b:    str
    mult_a_to_b: str  # "1", "0..1", "0..*", "1..*"
    mult_b_to_a: str
```

Used by `RelationshipStore` in the engine to validate `relate`/`unrelate` calls
and by `ctx.traverse` for navigating associations.
