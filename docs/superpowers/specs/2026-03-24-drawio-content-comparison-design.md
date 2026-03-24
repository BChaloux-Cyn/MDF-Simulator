# DRAWIO-003: Content-Based Comparison for Diagram Re-render

**Date:** 2026-03-24
**Status:** Approved
**Issue:** DRAWIO-003 — Render overwrites user layout changes on state diagrams

## Problem

When `render_to_drawio` is called, it regenerates diagrams from scratch,
discarding any manual layout changes (node positions, box sizes, edge
routing, anchor points) the user made in Draw.io. The current skip check
(`_structure_matches`) only compares element IDs — it misses content
changes like updated entry actions, guards, attributes, or method signatures.

Additionally, if the user edits semantic content in the drawio file directly
(e.g., changes a label), the system cannot detect that the drawio no longer
represents the YAML source.

## Solution

Replace the ID-only comparison with a **canonical JSON intermediate
representation**. Both the YAML source and the existing drawio file are
independently decomposed into the same JSON structure. If the two JSON
strings are identical, the diagram is up-to-date and rendering is skipped
(preserving user layout). If they differ, a full redraw is triggered.

### Decision Flow

```
1. Build canonical JSON from YAML source
2. Build canonical JSON from existing drawio XML
3. Compare the two JSON strings
4. Identical → skip (drawio represents the YAML, user layout preserved)
5. Different → full redraw
```

This catches all change directions:
- **YAML changed** → YAML JSON differs from drawio JSON → redraw
- **User edited drawio content** → drawio JSON differs from YAML JSON → redraw
- **User only moved nodes** (geometry-only change) → JSON identical → skip

The `force=True` flag bypasses the comparison entirely, as it does today.

## Canonical JSON Schemas

The JSON is a semantic snapshot of diagram content, stripped of all
geometry (positions, sizes, waypoints, anchor points). It uses sorted
keys and deterministic ordering so string comparison is reliable.

### State Diagram Canonical JSON

```json
{
  "type": "state_diagram",
  "domain": "Elevator",
  "class": "Elevator",
  "initial_state": "Idle",
  "states": [
    {
      "name": "Idle",
      "entry_action": null
    },
    {
      "name": "Departing",
      "entry_action": "if (self.next_stop_floor > self.current_floor) {\n    self.direction = Up;\n} else {\n    self.direction = Down;\n}\ngenerate Ready to self;\n"
    }
  ],
  "transitions": [
    {
      "from": "Idle",
      "to": "Departing",
      "event": "Floor_assigned",
      "params": "floor_num: FloorNumber",
      "guard": null,
      "action": "self.next_stop_floor = rcvd_evt.floor_num;"
    }
  ]
}
```

**Field rules:**
- `states` sorted by `name`
- `transitions` sorted by `(from, event, to)` tuple
- `entry_action`: raw text from YAML, or null
- `params`: comma-separated `name: type` string, or null if no params
- `guard` and `action`: raw text, or null

### Class Diagram Canonical JSON

```json
{
  "type": "class_diagram",
  "domain": "Elevator",
  "classes": [
    {
      "name": "Elevator",
      "stereotype": "active",
      "specializes": null,
      "attributes": [
        "- elevator_id: UniqueID {I1}",
        "- current_floor: FloorNumber"
      ],
      "methods": [
        "- _get_lit_buttons(): Set<DestFloorButton>"
      ]
    }
  ],
  "associations": [
    {
      "name": "R1",
      "point_1": "Elevator",
      "point_2": "Shaft",
      "1_mult_2": "1",
      "2_mult_1": "1",
      "1_phrase_2": "moves within",
      "2_phrase_1": "carries"
    }
  ],
  "generalizations": [
    {
      "name": "R9",
      "supertype": "Door",
      "subtypes": ["CarDoor", "ShaftDoor"]
    }
  ]
}
```

**Field rules:**
- `classes` sorted by `name`
- `attributes` and `methods` are formatted label strings (using `_attr_label`
  and `_method_label` output), preserving the exact text that appears in drawio
- `associations` sorted by `name`
- `generalizations` sorted by `name`, `subtypes` sorted alphabetically

## Pydantic Models

The canonical JSON structures are defined as Pydantic models in
`schema/drawio_schema.py`. These serve as the single source of truth
for the intermediate representation and provide runtime validation.

### State Diagram Models

```python
class CanonicalState(BaseModel):
    name: str
    entry_action: str | None

class CanonicalTransition(BaseModel):
    from_state: str = Field(alias="from")
    to: str
    event: str
    params: str | None
    guard: str | None
    action: str | None

class CanonicalStateDiagram(BaseModel):
    type: Literal["state_diagram"]
    domain: str
    class_name: str = Field(alias="class")
    initial_state: str
    states: list[CanonicalState]
    transitions: list[CanonicalTransition]
```

### Class Diagram Models

```python
class CanonicalClassEntry(BaseModel):
    name: str
    stereotype: str
    specializes: str | None
    attributes: list[str]
    methods: list[str]

class CanonicalAssociation(BaseModel):
    name: str
    point_1: str
    point_2: str
    mult_1_2: str = Field(alias="1_mult_2")
    mult_2_1: str = Field(alias="2_mult_1")
    phrase_1_2: str = Field(alias="1_phrase_2")
    phrase_2_1: str = Field(alias="2_phrase_1")

class CanonicalGeneralization(BaseModel):
    name: str
    supertype: str
    subtypes: list[str]

class CanonicalClassDiagram(BaseModel):
    type: Literal["class_diagram"]
    domain: str
    classes: list[CanonicalClassEntry]
    associations: list[CanonicalAssociation]
    generalizations: list[CanonicalGeneralization]
```

## Implementation Changes

### New Functions (tools/drawio.py)

1. **`_yaml_to_canonical_state(domain, sd) -> str`**
   Build canonical JSON string from a `StateDiagramFile`.

2. **`_yaml_to_canonical_class(domain, cd) -> str`**
   Build canonical JSON string from a `ClassDiagramFile`.

3. **`_drawio_to_canonical_state(drawio_path) -> str | None`**
   Parse existing state diagram drawio XML, extract semantic content
   into canonical JSON. Returns None if file missing or malformed.

4. **`_drawio_to_canonical_class(drawio_path) -> str | None`**
   Parse existing class diagram drawio XML, extract semantic content
   into canonical JSON. Returns None if file missing or malformed.

### Modified Functions

5. **`_structure_matches_state`** → renamed to `_content_matches_state`.
   Replaces ID comparison with:
   `_yaml_to_canonical_state(domain, sd) == _drawio_to_canonical_state(drawio_path)`

6. **`_structure_matches_class`** → renamed to `_content_matches_class`.
   Replaces ID comparison with:
   `_yaml_to_canonical_class(domain, cd) == _drawio_to_canonical_class(drawio_path)`

### Removed Functions

7. `_compute_expected_class_ids` — replaced by canonical JSON
8. `_compute_expected_state_ids` — replaced by canonical JSON
9. `_extract_drawio_ids` — replaced by `_drawio_to_canonical_*`

### Drawio→JSON Extraction Strategy

**State diagrams:**
- State names: from `mxCell` `value` where ID matches `*:state:*` (exclude `__initial__`)
- Entry actions: parsed from the state cell's HTML `value` — content after the `entry /` separator
- Transitions: from edge cells where ID matches `*:trans:*` — `value` contains event, params, guard

**Class diagrams:**
- Class headers: `value` of swimlane cells (stereotype + name)
- Attributes: `value` of `:attrs` child cells (HTML `<br>`-joined labels)
- Methods: `value` of `:methods` child cells
- Associations: edge `value` (R-number) plus child label cells for multiplicities and phrases
- Generalizations: edges with open-arrow style matching partition patterns

### Unchanged

- `_build_class_diagram_xml` / `_build_state_diagram_xml` — rendering untouched
- Public API signatures — same `force` flag behavior
- `force=True` bypasses comparison entirely

## Testing

- Unit tests for `_yaml_to_canonical_state` and `_yaml_to_canonical_class`
  with known YAML inputs, asserting expected JSON output
- Unit tests for `_drawio_to_canonical_state` and `_drawio_to_canonical_class`
  with known drawio XML inputs
- Round-trip test: render a diagram, extract canonical JSON from the result,
  compare to YAML canonical JSON — must match
- Integration test: render, modify drawio label, verify `_content_matches`
  returns False
- Integration test: render, modify only geometry, verify `_content_matches`
  returns True
