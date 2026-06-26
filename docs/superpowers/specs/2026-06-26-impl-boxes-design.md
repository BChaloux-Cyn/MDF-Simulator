# Implementation Boxes in Draw.io Diagrams

**Date:** 2026-06-26  
**Status:** Approved

## Summary

Add disconnected rectangle boxes to rendered Draw.io diagrams showing:
- **Class diagrams**: one box per provided bridge implementation (domain function), with signature sourced from `DOMAINS.yaml` and pycca action body from `class-diagram.yaml`
- **State diagrams**: one box per class method that has an action body, with full UML signature and pycca action body from `class-diagram.yaml`

Boxes are placed in a vertical column to the right of the main diagram content. Change detection is extended to re-render when action bodies or signatures change.

---

## Architecture

Five files are modified. The YAML schema (`yaml_schema.py`) is **not changed** — `ProvidedBridge.implementations` and `ClassDef.methods` with `.action` already exist. `DOMAINS.yaml` is the source of truth for bridge operation signatures (params and return type).

| File | Change |
|---|---|
| `schema/drawio_schema.py` | Add `STYLE_IMPL_BOX`, `bridge_impl_id()`, `method_box_id()` |
| `schema/drawio_canonical.py` | Add `CanonicalBridgeImpl`, `CanonicalMethod`; extend `CanonicalClassDiagram` and `CanonicalStateDiagram` |
| `schema/canonical_builder.py` | `yaml_to_canonical_class` accepts optional `op_lookup`; `yaml_to_canonical_state` accepts optional `class_def` |
| `tools/drawio.py` | Renderer and change detection updates (see below) |
| `schema/yaml_schema.py` | No change |

---

## Rendering

### Box Style (`STYLE_IMPL_BOX`)

Single flat `mxCell` rectangle — no swimlane nesting.

```
rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;
fontFamily=Courier New;fontSize=11;fillColor=#f5f5f5;
strokeColor=#666666;fontColor=#333333;
spacingLeft=6;spacingRight=6;spacingTop=4;spacingBottom=4;
```

Visually distinct from UML class boxes (blue/green swimlanes) — clearly marks implementation artefacts.

### Box Content

**Bridge impl box:**
```
<b>ElevatorDetected(sensor_id: UniqueID): void</b><br>──────────────────<br>Optional&lt;ShaftFloor&gt; sf = ...<br>if (sf.has_value()) {<br>    ...<br>}
```

Header format: `<b>{name}({params_sig}): {return_type}</b>`  
- `params_sig` = comma-joined `{name}: {type}` from `DOMAINS.yaml` `BridgeOperation.params`; empty string if no params → renders as `name()`
- Return type omitted from header if `BridgeOperation.return_type` is `None`
- Divider: literal `──────────────────`
- Action body: `\n` → `<br>`, `<` → `&lt;`, `>` → `&gt;`

**Method box (state diagram):**

Header format: `<b>{vis_sym} {name}({params_sig}){: return_type}</b>`  
- `vis_sym`: `+` for public, `-` for private (same as class diagram method rows)
- Same action body formatting as bridge impl

### Box Sizing

```python
IMPL_BOX_W = 400
IMPL_BOX_HEADER_H = 30

def _impl_box_height(action: str) -> int:
    n_lines = action.count('\n') + 1
    return IMPL_BOX_HEADER_H + max(n_lines, 3) * ROW_H
```

### Placement

After igraph lays out the main nodes:

```python
right_edge = max(x + w for all main nodes)
box_x = right_edge + 60
box_y = MARGIN
# stack boxes vertically with 20px gap
```

Canvas width and height expand to accommodate the column. Sort order:
- Bridge impls: `(to_domain, impl_name)`
- Methods: `method_name`

### Cell IDs

```
bridge_impl_id(domain, to_domain, impl_name) → "{domain}:bridge_impl:{to_domain}:{impl_name}"
method_box_id(domain, class_name, method_name) → "{domain}:method:{class_name}:{method_name}"
```

### State Diagram Method Loading

`render_to_drawio_state` loads `class-diagram.yaml` and finds the `ClassDef` where `name == class_name`. The matching `ClassDef` is passed to `_build_state_diagram_xml` as an optional parameter. Methods with `action: null` produce no box.

---

## Change Detection

### New Canonical Models (`drawio_canonical.py`)

```python
class CanonicalBridgeImpl(BaseModel):
    name: str
    to_domain: str
    params_sig: str        # "" if no params
    return_type: str | None
    action: str

class CanonicalMethod(BaseModel):
    name: str
    params_sig: str
    return_type: str | None
    action: str            # only methods with non-null action are included
```

`CanonicalClassDiagram` gains `bridge_impls: list[CanonicalBridgeImpl]` (sorted by `(to_domain, name)`).  
`CanonicalStateDiagram` gains `methods: list[CanonicalMethod]` (sorted by `name`).

### YAML → Canonical (`canonical_builder.py`)

- `yaml_to_canonical_class(domain, cd, op_lookup=None)`: iterates `cd.bridges`, for each `ProvidedBridge` iterates `.implementations`, looks up params/return from `op_lookup[to_domain][impl.name]`, populates `CanonicalBridgeImpl`. `op_lookup` type: `dict[str, dict[str, BridgeOperation]] | None`.
- `yaml_to_canonical_state(domain, sd, class_def=None)`: if `class_def` provided, iterates `class_def.methods` where `method.action is not None`, populates `CanonicalMethod`.

### XML → Canonical (`tools/drawio.py`)

**Bridge impl cells** — ID pattern: `{domain}:bridge_impl:{to_domain}:{impl_name}` (4 colon-separated parts, `parts[1] == "bridge_impl"`).  
Parse `value`:
1. Split on first `<br>──` to separate header from body
2. Strip `<b>` / `</b>` tags from header; parse `name(params_sig): return_type` with regex
3. Unescape `<br>` → `\n` and HTML entities in body → `action`

**Method cells** — ID pattern: `{domain}:method:{class_name}:{method_name}` (4 colon-separated parts, `parts[1] == "method"`).  
Same parse strategy (strip leading `{vis_sym} ` from header before name parsing).

### Re-render Triggers

| Change | Effect |
|---|---|
| Bridge impl action body changed | `CanonicalBridgeImpl.action` differs → re-render class diagram |
| `DOMAINS.yaml` op signature changed (params or return) | `params_sig` or `return_type` differs → re-render class diagram |
| Impl added or removed | List length differs → re-render |
| Method action body changed | `CanonicalMethod.action` differs → re-render state diagram |
| Method signature changed | `params_sig` or `return_type` differs → re-render state diagram |
| Method added, removed, or action toggled null↔non-null | List differs → re-render |

### `render_to_drawio_class` Flow

```
load class-diagram.yaml → ClassDiagramFile
load DOMAINS.yaml → DomainsFile  [error if missing]
build op_lookup: dict[to_domain][op_name] → BridgeOperation
validate all bridge impls have a matching op  [error if any missing]
_content_matches_class(domain_path, domain, cd, op_lookup) → skip if true
_build_class_diagram_xml(domain, cd, op_lookup) → write file
```

---

## Error Handling

| Condition | Behavior |
|---|---|
| `DOMAINS.yaml` missing when rendering class diagram | `severity="error"` issue, no output file |
| `BridgeImplementation` has no matching `BridgeOperation` in `DOMAINS.yaml` | `severity="error"` issue, no output file |
| `class-diagram.yaml` missing when rendering state diagram | Silently omit method boxes; state diagram renders normally |
| Class not found in `class-diagram.yaml` when rendering state diagram | Silently omit method boxes; state diagram renders normally |
| Method has `action: null` | Method box omitted |

---

## Tests

All tests added to `tests/test_drawio.py` (or a new `tests/test_drawio_impl_boxes.py`):

**Class diagram:**
- Bridge impl boxes appear in rendered XML with correct cell IDs
- Box value contains expected header (name, params, return) and action body
- Error returned when `DOMAINS.yaml` is missing
- Error returned when impl has no matching operation in `DOMAINS.yaml`
- Re-render triggered when bridge impl action body changes
- Re-render triggered when `DOMAINS.yaml` operation signature changes
- No re-render when nothing changes (skip-if-unchanged)

**State diagram:**
- Method boxes appear for active class with action-bearing methods
- Method boxes absent (no error) when `class-diagram.yaml` is missing
- Methods with `action: null` produce no box
- Re-render triggered when method action body changes
- No re-render when nothing changes (skip-if-unchanged)
