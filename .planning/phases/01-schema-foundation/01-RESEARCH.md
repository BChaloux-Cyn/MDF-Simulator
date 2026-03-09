# Phase 1: Schema Foundation - Research

**Researched:** 2026-03-06
**Domain:** Pydantic v2 YAML schema design, Draw.io XML generation/parsing, artifact template authoring
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**File Structure:**
- `.design/model/<domain>/types.yaml` — custom type definitions
- `.design/model/<domain>/class-diagram.yaml` — classes, attributes, associations, bridges, subtype partitions
- `.design/model/<domain>/state-diagrams/<ClassName>.yaml` — one file per class with a state machine
- `.design/model/DOMAINS.yaml` — top-level domain map (replaces DOMAINS.md from TMPL-01)
- `read_model(domain)` reads `class-diagram.yaml`; `read_state_machine(domain, class)` reads `state-diagrams/<ClassName>.yaml`
- Two distinct MCP tool variants — not a single tool with a type flag
- Associations live inside `class-diagram.yaml`
- Bridge signatures declared once in DOMAINS.yaml — single source of truth
- Requiring domain's `class-diagram.yaml` lists operation names only
- Providing domain's `class-diagram.yaml` contains `implementations` with pycca action bodies

**Schema Versioning:**
- All YAML files include `schema_version` as the first field
- Format: semantic version string, e.g., `schema_version: "1.0.0"`
- Pydantic validates it matches semver pattern
- Applies to: `DOMAINS.yaml`, `types.yaml`, `class-diagram.yaml`, all `state-diagrams/<ClassName>.yaml`

**DOMAINS.yaml:** Replaces DOMAINS.md — machine-parseable, schema-versioned. Single source of truth for bridge signatures.

**Primitive Types:** Boolean, Integer, Real, String, UniqueID (standard xtUML primitives)

**types.yaml:** Supports three base categories: scalar (base primitive + optional constraints), enumeration, structure.

**class-diagram.yaml schema:** Classes with stereotypes (entity | active | associative), attributes with identifier/referential flags, methods with scope (instance | class), associations (bidirectional), subtype partitions, associative classes, bridge stanzas for requiring and providing domains.

**state-diagrams/<ClassName>.yaml schema:** events catalog (typed params), states (name, entry_action), transitions (from, to, event, guard, action).

**Guard rules:** Guard is a pycca boolean expression string or null. If any transition from (from_state, event) has a guard, ALL must. Mutual exclusivity and total coverage required.

**Entry actions only** — exit actions not supported (not a pycca concept).

**Pycca action storage:** All action blocks stored as YAML literal block scalars (`|`).

**Draw.io Round-Trip:**
- Semantic content only survives (not layout/colors)
- `render_to_drawio` merges, not overwrites — existing positions preserved, net-new auto-placed
- Element IDs are deterministic from YAML path (e.g., `hydraulics:class:Valve`)
- `validate_drawio` checks shape type and required labels; colors/fonts are free

**Stereotype enforcement:**
- `active` class must have a state diagram (or inherit from active supertype)
- `entity` class must not have a state diagram (unless has `partitions` block)
- `associative` class must have `formalizes` field pointing to a valid R-number

**Behavior Doc Templates:** Three templates — `behavior-domain.md`, `behavior-class.md`, `behavior-state.md` — with specific sections as defined in CONTEXT.md.

### Claude's Discretion

- Auto-layout algorithm for initial Draw.io element placement
- Internal Pydantic model structure and field aliases
- YAML serialization formatting (indentation, quote style)
- Error message wording in validation issue lists

### Deferred Ideas (OUT OF SCOPE)

- TRANSLATION.md template — Phase 2+ work
- pycca compiler invocation details — Phase 3+
- Multi-candidate identifier support — deferred to schema v1.1
- Polymorphic event dispatch across subtype hierarchies — Phase 5 simulator concern
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCHEMA-01 | YAML model schema defined — classes (stereotypes, identifiers, attributes, methods), associations (verb phrase, multiplicity), state machines (states, transitions, guards, pycca actions), domain bridges (from/to, operation, params, direction) | Pydantic v2 model hierarchy; field patterns for each construct documented below |
| SCHEMA-02 | `schema_version` field required in all model files from day one | Pydantic `field_validator` with semver regex; required field (no default) as first field in every root model |
| SCHEMA-03 | Canonical Draw.io schema defined — 1:1 bijection with YAML; canonical shape-type-per-element table locked; no freeform shapes without YAML equivalent | Draw.io mxCell style strings for each UML element documented; bijection table provided below |
| SCHEMA-04 | Draw.io round-trip test passes — generate XML, open in real Draw.io, save, sync back; structural equality confirmed before any tool is built | lxml XML generation patterns, deterministic ID strategy, element-by-style parsing on sync |
| SCHEMA-05 | Behavior doc format defined — domain-level, class-level, and state-machine-level templates | Template structure locked in CONTEXT.md; research confirms Markdown section conventions |
| TMPL-01 | `DOMAINS.yaml` template — domain map with realized domains and bridge index | DOMAINS.yaml schema fully specified in CONTEXT.md; template is a populated example |
| TMPL-02 | `CLASS_DIAGRAM.yaml` template — class diagram YAML scaffold | class-diagram.yaml schema fully specified in CONTEXT.md |
| TMPL-03 | `STATE_DIAGRAM.yaml` template — state diagram YAML scaffold | state-diagrams/<ClassName>.yaml schema fully specified in CONTEXT.md |
| TMPL-04 | Behavior doc templates — `behavior-domain.md`, `behavior-class.md`, `behavior-state.md` | Template structure fully specified in CONTEXT.md |
</phase_requirements>

---

## Summary

Phase 1 is entirely a design-and-write phase: no MCP server, no running code. The deliverables are Python module files containing Pydantic model definitions (`yaml_schema.py`, `drawio_schema.py`), a bijection table as a canonical constant, and six template files. All schema decisions are locked in CONTEXT.md — this phase executes those decisions.

The primary technical work is translating the schema specifications in CONTEXT.md into Pydantic v2 `BaseModel` classes that form a type-safe hierarchy. A secondary task is specifying the exact Draw.io mxCell style strings for each model element — these style strings are the contract for Phase 4's `render_to_drawio` and `sync_from_drawio`. The round-trip test (SCHEMA-04) must be executed manually: generate sample XML, open in real Draw.io, save, and verify the diff is within acceptable bounds.

The stack is already locked (Pydantic v2, PyYAML/ruamel.yaml, lxml, defusedxml, NetworkX, lark). No new library choices are needed in Phase 1. The project starts from a greenfield state — `mdf-server/` does not exist yet, `templates/` does not exist yet. Phase 1 creates both directories and their initial contents.

**Primary recommendation:** Write `yaml_schema.py` first (all Pydantic models), validate it manually against sample YAML, then write `drawio_schema.py` (bijection table + style constants), then execute the round-trip test with a minimal example before authoring all six templates.

---

## Standard Stack

### Core (all already locked)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | 2.12.5 | YAML model schema definition and runtime validation | v2 is dramatically faster than v1 (Rust core); `model_validate()` on YAML-loaded dict gives typed objects + error paths |
| PyYAML | 6.0.3 | Load YAML files into dicts for Pydantic validation | `yaml.safe_load()` for read; C extension path via LibYAML |
| ruamel.yaml | 0.19.1 | Write YAML preserving comments and ordering | Use for write-back; PyYAML `safe_dump` destroys field ordering and comments |
| lxml | 6.0.2 | Draw.io XML generation (`lxml.etree`) | Fastest Python XML library; full namespace support; deterministic output |
| defusedxml | 0.7.1 | Safe XML parsing of user-provided Draw.io files | Prevents XXE and billion-laughs attacks on `sync_from_drawio` input |
| pytest | 9.0.2 | Test framework for schema validation and round-trip tests | Standard; already locked |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | stdlib | Semver regex validation for `schema_version` | `field_validator` uses `re.match()` against `r"^\d+\.\d+\.\d+$"` |
| jsonschema | 4.26.0 | Generate schema.json for external tooling | Optional for Phase 1; generate if time permits for downstream tooling |

### Installation

```bash
cd mdf-server
uv add pydantic pyyaml "ruamel.yaml" lxml defusedxml
uv add --dev pytest ruff mypy
```

---

## Architecture Patterns

### Recommended Project Structure (Phase 1 scope)

```
model-based-project-framework/
├── mdf-server/
│   ├── pyproject.toml
│   └── mdf_server/
│       ├── __init__.py
│       └── schema/
│           ├── __init__.py
│           ├── yaml_schema.py      # All Pydantic models — PRIMARY DELIVERABLE
│           └── drawio_schema.py    # Bijection table + style constants
├── templates/
│   ├── DOMAINS.yaml.tmpl
│   ├── CLASS_DIAGRAM.yaml.tmpl
│   ├── STATE_DIAGRAM.yaml.tmpl
│   ├── behavior-domain.md.tmpl
│   ├── behavior-class.md.tmpl
│   └── behavior-state.md.tmpl
└── tests/
    └── test_schema_roundtrip.py    # SCHEMA-04 round-trip test
```

**Note:** `mdf-server/tests/` is the long-term home, but a top-level `tests/` is acceptable for Phase 1 since the MCP package doesn't exist yet. Move to `mdf-server/tests/` in Phase 2.

### Pattern 1: Pydantic Model Hierarchy

**What:** Each YAML file type maps to a root Pydantic model. Nested constructs are nested `BaseModel` classes. Every root model has `schema_version` as its first required field.

**Structure:**

```
DomainsFile              ← DOMAINS.yaml root
  DomainEntry            ← domains[*]
  BridgeEntry            ← bridges[*]
    BridgeOperation      ← bridges[*].operations[*]
    OperationParam       ← .params[*]

ClassDiagramFile         ← class-diagram.yaml root
  ClassDef               ← classes[*]
    Attribute            ← .attributes[*]
    Method               ← .methods[*]
    MethodParam          ← .methods[*].params[*]
    SubtypePartition     ← .partitions[*]
  Association            ← associations[*]
  RequiredBridge         ← bridges[*] (direction=required)
  ProvidedBridge         ← bridges[*] (direction=provided)
    BridgeImplementation ← .implementations[*]

TypesFile                ← types.yaml root
  TypeDef                ← types[*] (discriminated union on base)

StateDiagramFile         ← state-diagrams/<Class>.yaml root
  EventDef               ← events[*]
    EventParam           ← .params[*]
  StateDef               ← states[*]
  Transition             ← transitions[*]
```

**When to use:** Always — this is the schema.

### Pattern 2: schema_version Field Validator

**What:** Every root model enforces `schema_version` with a `field_validator` using semver regex. The field has no default — omitting it is a validation error.

**Example:**

```python
# Source: docs.pydantic.dev/latest/concepts/validators/
import re
from pydantic import BaseModel, field_validator

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

class SchemaVersionMixin(BaseModel):
    schema_version: str  # Required — no default

    @field_validator("schema_version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not SEMVER_RE.match(v):
            raise ValueError(
                f"schema_version must be semver (e.g. '1.0.0'), got: {v!r}"
            )
        return v
```

Use as a mixin on all root models: `class DomainsFile(SchemaVersionMixin):`

### Pattern 3: Discriminated Union for TypeDef

**What:** `types.yaml` entries have three shapes (scalar, enum, struct) based on the `base` field. Pydantic v2 discriminated unions handle this cleanly.

**Example:**

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class ScalarType(BaseModel):
    name: str
    base: str  # Boolean | Integer | Real | String | UniqueID
    units: str | None = None
    range: list[float] | None = None
    description: str | None = None

class EnumType(BaseModel):
    name: str
    base: Literal["enum"]
    values: list[str]
    description: str | None = None

class StructType(BaseModel):
    name: str
    base: Literal["struct"]
    description: str | None = None
    fields: list[StructField]

TypeDef = Annotated[
    Union[EnumType, StructType, ScalarType],
    Field(discriminator="base")
]
```

**Note:** ScalarType must be last in the Union since it's the fallback (base is any string not "enum"/"struct"). Use `model_validator` on ScalarType to validate that `base` is one of the five xtUML primitives.

### Pattern 4: Cross-Field Validation with model_validator

**What:** Several constraints require checking relationships between fields. Use `@model_validator(mode='after')` for post-instantiation checks.

**Example — stereotype/state-machine consistency:**

```python
from pydantic import model_validator

class ClassDef(BaseModel):
    name: str
    stereotype: Literal["entity", "active", "associative"]
    formalizes: str | None = None
    partitions: list[SubtypePartition] | None = None

    @model_validator(mode='after')
    def check_associative_has_formalizes(self) -> 'ClassDef':
        if self.stereotype == "associative" and self.formalizes is None:
            raise ValueError(
                f"Class {self.name!r}: stereotype 'associative' requires a 'formalizes' field"
            )
        return self
```

**Example — guard all-or-none rule:**

```python
class StateDiagramFile(SchemaVersionMixin):
    # ...
    transitions: list[Transition]

    @model_validator(mode='after')
    def check_guard_consistency(self) -> 'StateDiagramFile':
        from itertools import groupby
        key = lambda t: (t.from_state, t.event)
        for (from_state, event), group in groupby(
            sorted(self.transitions, key=key), key=key
        ):
            ts = list(group)
            guarded = [t for t in ts if t.guard is not None]
            if guarded and len(guarded) != len(ts):
                raise ValueError(
                    f"Transitions from '{from_state}' on '{event}': "
                    f"mix of guarded and unguarded — all must have guards"
                )
        return self
```

### Pattern 5: Draw.io XML Generation with lxml

**What:** `drawio_schema.py` owns all style string constants and the bijection table. `render_to_drawio` imports from it. Style strings are the contract.

**Canonical mxCell structure:**

```python
# Source: Draw.io mxGraphModel format (stable since 2005, jgraph/drawio)
from lxml import etree

def make_mxfile() -> etree._Element:
    mxfile = etree.Element("mxfile")
    diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
    model = etree.SubElement(
        diagram, "mxGraphModel",
        dx="1034", dy="546", grid="1", gridSize="10",
        guides="1", tooltips="1", connect="1", arrows="1",
        fold="1", page="1", pageScale="1",
        pageWidth="1169", pageHeight="827",
        math="0", shadow="0"
    )
    root = etree.SubElement(model, "root")
    etree.SubElement(root, "mxCell", id="0")
    etree.SubElement(root, "mxCell", id="1", parent="0")
    return mxfile, root

def make_class_cell(root, cell_id: str, name: str, stereotype: str,
                    x: int, y: int, w: int = 160, h: int = 60) -> etree._Element:
    cell = etree.SubElement(
        root, "mxCell",
        id=cell_id,
        value=f"&lt;&lt;{stereotype}&gt;&gt;\n{name}",
        style=STYLE_CLASS,
        vertex="1",
        parent="1"
    )
    etree.SubElement(cell, "mxGeometry",
        x=str(x), y=str(y), width=str(w), height=str(h),
        attrib={"as": "geometry"})
    return cell
```

### Pattern 6: Deterministic Element IDs

**What:** Every Draw.io element gets an ID derived from its YAML path. This enables merge-on-rerender (existing positions preserved).

**ID scheme:**

```python
def class_id(domain: str, class_name: str) -> str:
    return f"{domain.lower()}:class:{class_name}"

def attribute_id(domain: str, class_name: str, attr_name: str) -> str:
    return f"{domain.lower()}:attr:{class_name}:{attr_name}"

def association_id(domain: str, assoc_name: str) -> str:
    return f"{domain.lower()}:assoc:{assoc_name}"

def state_id(domain: str, class_name: str, state_name: str) -> str:
    return f"{domain.lower()}:state:{class_name}:{state_name}"

def transition_id(domain: str, class_name: str,
                  from_state: str, event: str, idx: int) -> str:
    return f"{domain.lower()}:trans:{class_name}:{from_state}:{event}:{idx}"
```

### Anti-Patterns to Avoid

- **Free-form classes in schema:** Don't use `dict` or `Any` types in Pydantic models — lose validation. Every field must be typed.
- **Schema_version with default:** Setting `schema_version: str = "1.0.0"` defeats SCHEMA-02. No default — missing field must be a validation error.
- **Mutable style constants:** Don't build style strings dynamically from many small strings at render time — define them as module-level constants in `drawio_schema.py` and never vary them. Consistency is the bijection.
- **Float geometry for Draw.io positions:** Use integer pixel positions for deterministic output; floats cause diff noise when Draw.io saves the file.
- **ruamel.yaml for read:** Use PyYAML (`yaml.safe_load`) for reading model files into dicts; ruamel.yaml is only needed when writing back to preserve human-authored comments.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semver validation | Custom semver parser | `re.compile(r"^\d+\.\d+\.\d+$")` in `field_validator` | Simple enough for regex; don't add a semver library |
| YAML schema validation | JSON Schema document | Pydantic models directly | Pydantic is the runtime schema; JSON Schema can be derived later if needed |
| XML builder | String concatenation | `lxml.etree` SubElement tree | String concat produces broken XML with special characters; lxml escapes correctly |
| XML safe-parsing | `xml.etree.ElementTree` | `defusedxml` wrapping `lxml` | stdlib parser is vulnerable to XXE; always use defusedxml for user-provided XML |
| Association graph validation | Custom BFS | `networkx.DiGraph` | NetworkX already handles reachability, cycles, and strongly-connected components |

**Key insight:** Pydantic v2 handles 90% of the "validation plumbing" — the developer's job is to define the model hierarchy correctly, not to write validation loops.

---

## Common Pitfalls

### Pitfall 1: schema_version Not First in YAML

**What goes wrong:** PyYAML does not enforce field ordering; Pydantic receives the dict regardless of key order. However, the specification says `schema_version` is the first field for human readability — ruamel.yaml's `CommentedMap` preserves insertion order on write-back.

**Why it happens:** PyYAML `safe_load` returns a regular dict (unordered in Python 3.7+ it preserves insertion order of the source YAML). `safe_dump` does NOT preserve source order — it sorts alphabetically.

**How to avoid:** Use `ruamel.yaml` for all write operations to preserve `schema_version` as the first key. When writing initial templates, explicitly order keys using `ruamel.yaml`'s `CommentedMap`.

**Warning signs:** `schema_version` appears in the middle or at the end of a regenerated YAML file.

### Pitfall 2: Draw.io Saves Reformat XML

**What goes wrong:** Real Draw.io compresses the `<diagram>` content (base64+deflate) by default when saving. The round-trip test (SCHEMA-04) will fail if comparing raw XML bytes — Draw.io's saved file won't match the generated XML.

**Why it happens:** Draw.io has two XML modes: uncompressed (editable XML as `mxGraphModel` children) and compressed (diagram content is a base64-encoded deflated string). The browser app saves compressed by default; `File > Properties > Compressed` can disable it, but this is a user setting.

**How to avoid:**
1. Generate uncompressed XML for the round-trip test (set `compressed="false"` on `mxfile` element)
2. The sync parser must handle both compressed and uncompressed input
3. Accept that `render_to_drawio` generates uncompressed XML; Draw.io may save compressed
4. Use `defusedxml` + Python's `zlib` to decompress on `sync_from_drawio` input

**Detection:** If Draw.io-saved XML has `<diagram>eJy...` (base64 content) instead of `<mxGraphModel>` as a child, it's compressed.

### Pitfall 3: Pydantic v2 Union Discrimination Failure

**What goes wrong:** Pydantic can't discriminate `TypeDef` union members if the discriminator field `base` is `"struct"` or `"enum"` but also matches the `ScalarType` (which accepts any string for `base`).

**Why it happens:** Discriminated unions in Pydantic v2 require `Literal` types on the discriminator field for all members except the catch-all. `ScalarType.base: str` is too broad.

**How to avoid:** Use `model_validator` on `ScalarType` to validate that `base` is one of the five xtUML primitives after the union resolves. Alternatively, define `ScalarBase = Literal["Boolean", "Integer", "Real", "String", "UniqueID"]` and use that type.

### Pitfall 4: Guard Mutual Exclusivity Is a Schema Validator, Not Runtime

**What goes wrong:** The guard all-or-none rule (if any transition from `(from, event)` has a guard, all must) is structural and must be caught in the Pydantic model validator, not at simulation time.

**Why it happens:** Without the validator, malformed state diagrams reach Phase 5 simulation and produce runtime crashes rather than design-time errors.

**How to avoid:** Add `@model_validator(mode='after')` on `StateDiagramFile` that groups transitions by `(from_state, event)` and checks the all-or-none constraint. See code example above.

### Pitfall 5: Bridge Cross-Reference Cannot Be Validated in One Model

**What goes wrong:** `class-diagram.yaml` bridges for a requiring domain list only operation names — the validator must check those names exist in `DOMAINS.yaml`. But Pydantic models validate single files in isolation.

**Why it happens:** Cross-file validation requires both files loaded simultaneously. Pydantic `model_validate()` on a single file cannot access another file's contents.

**How to avoid:** In Phase 1, define the schema so each file validates its own structure correctly. The cross-reference check (requiring domain ops exist in DOMAINS.yaml) is a `validate_model` concern (Phase 2/3 MCP tool), not a Pydantic schema concern. Document this boundary clearly in `yaml_schema.py`.

### Pitfall 6: lxml Special Characters in Cell Values

**What goes wrong:** Class names or attribute values containing `<`, `>`, `&` break XML if inserted as raw strings into `mxCell.value`.

**Why it happens:** lxml's SubElement `value` attribute is set as a Python string; lxml will escape it correctly in `etree.tostring()`. However, if you use `etree.fromstring()` to parse XML and then inspect `.get("value")`, you get the unescaped string — this is correct behavior but can surprise you in tests.

**How to avoid:** Always use lxml's tree API (not string manipulation) and let lxml handle escaping. Test round-trip with names containing special characters.

---

## Code Examples

### Loading and Validating a YAML File

```python
# Source: PyYAML docs + Pydantic v2 model_validate pattern
import yaml
from mdf_server.schema.yaml_schema import ClassDiagramFile

def load_class_diagram(path: str) -> ClassDiagramFile:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return ClassDiagramFile.model_validate(raw)
    # Raises pydantic.ValidationError with field paths if invalid
```

### Generating Draw.io XML for a Class

```python
# Source: lxml.etree pattern + Draw.io mxGraphModel format
from lxml import etree
from mdf_server.schema.drawio_schema import STYLE_CLASS, STYLE_ATTRIBUTE, STYLE_ASSOCIATION

def render_class(root: etree._Element, domain: str, cls_def) -> None:
    class_cell_id = f"{domain.lower()}:class:{cls_def.name}"
    cell = etree.SubElement(
        root, "mxCell",
        id=class_cell_id,
        value=f"<<{cls_def.stereotype}>>\n{cls_def.name}",
        style=STYLE_CLASS,
        vertex="1",
        parent="1"
    )
    geom = etree.SubElement(cell, "mxGeometry",
        x="100", y="100", width="200", height="60",
        attrib={"as": "geometry"})
    # Attributes as child cells
    for i, attr in enumerate(cls_def.attributes or []):
        attr_id = f"{domain.lower()}:attr:{cls_def.name}:{attr.name}"
        label = f"{'[I] ' if attr.identifier else ''}{attr.name}: {attr.type}"
        attr_cell = etree.SubElement(
            root, "mxCell",
            id=attr_id,
            value=label,
            style=STYLE_ATTRIBUTE,
            vertex="1",
            parent=class_cell_id
        )
        etree.SubElement(attr_cell, "mxGeometry",
            y=str(60 + i * 20), width="200", height="20",
            attrib={"as": "geometry"})
```

### Serializing back to YAML with ruamel.yaml

```python
# Source: ruamel.yaml docs — comment-preserving write
from ruamel.yaml import YAML

def write_class_diagram(path: str, model: ClassDiagramFile) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = model.model_dump(mode='python', exclude_none=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
```

---

## Draw.io Canonical Bijection Table

This table is the SCHEMA-03 deliverable. It must be implemented as constants in `drawio_schema.py`.

| YAML Element | Draw.io Shape Style | Required Cell Attributes | Parent |
|-------------|---------------------|--------------------------|--------|
| Class (entity/active/associative) | `swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;startSize=26;fillColor=#dae8fc;strokeColor=#6c8ebf;rounded=0;` | `value="<<stereotype>>\nName"` | root (id=1) |
| Attribute row | `text;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;spacingLeft=4;` | `value="[I] name: type"` | parent class cell |
| Association (connector) | `edgeStyle=orthogonalEdgeStyle;rounded=0;` | `source=class1_id, target=class2_id` | root |
| Association verb phrase label | `edgeLabel;align=center;` | `value="verb phrase"` | association cell |
| Association multiplicity (end) | `edgeLabel;align=center;` | `value="1..M"` at each end | association cell |
| State (normal) | `rounded=1;whiteSpace=wrap;html=1;arcSize=50;` | `value="StateName"` | state diagram root |
| Initial pseudostate | `ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#000000;strokeColor=#000000;` | `value=""` | state diagram root |
| Transition (directed edge) | `edgeStyle=orthogonalEdgeStyle;exitX=0;exitY=0.5;entryX=0;entryY=0.5;` | `value="EventName [guard] / action"`, source/target | state diagram root |
| Domain bridge (dashed connector) | `dashed=1;endArrow=open;endFill=0;` | `value="operation_name"` | root |

**Note on swimlane style:** Draw.io's native UML class shape uses `swimlane` with `childLayout=stackLayout`. Attribute rows are child mxCells with the parent set to the class cell ID. This is the canonical approach — it produces the standard UML class box with compartments.

**Style strings (define as constants in `drawio_schema.py`):**

```python
STYLE_CLASS = (
    "swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;"
    "startSize=26;fillColor=#dae8fc;strokeColor=#6c8ebf;rounded=0;"
)
STYLE_ATTRIBUTE = (
    "text;strokeColor=none;fillColor=none;align=left;"
    "verticalAlign=middle;spacingLeft=4;spacingRight=4;"
)
STYLE_ASSOCIATION = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
STYLE_STATE = "rounded=1;whiteSpace=wrap;html=1;arcSize=50;"
STYLE_INITIAL_PSEUDO = (
    "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    "fillColor=#000000;strokeColor=#000000;"
)
STYLE_TRANSITION = "edgeStyle=orthogonalEdgeStyle;html=1;"
STYLE_BRIDGE = "dashed=1;endArrow=open;endFill=0;html=1;"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `@validator` | Pydantic v2 `@field_validator` / `@model_validator` with `mode=` | Pydantic v2 (2023) | Different decorator signature — do not use v1 patterns |
| `@root_validator` (v1) | `@model_validator(mode='before'/'after')` | Pydantic v2 | `@root_validator` removed in v2 |
| PyYAML for all YAML ops | PyYAML for read, ruamel.yaml for write | Community standard | PyYAML `safe_dump` sorts keys alphabetically — destroys schema_version ordering |
| `xml.etree.ElementTree` for XML | `lxml.etree` | Long-standing recommendation | lxml is faster, namespace-correct, and produces deterministic output |

**Deprecated/outdated:**
- `pydantic.validator` decorator: replaced by `field_validator` in v2 — do not use
- `dict()` method on Pydantic models: replaced by `model_dump()` in v2
- `parse_obj()` method: replaced by `model_validate()` in v2

---

## Open Questions

1. **Draw.io compressed XML handling**
   - What we know: Draw.io browser app saves compressed XML (base64+zlib) by default; uncompressed mode can be enabled per diagram
   - What's unclear: Whether there's a reliable way to detect compression and decompress — needs a sample file to verify the exact byte format
   - Recommendation: In the round-trip test (SCHEMA-04), explicitly disable compression by setting `compressed="false"` on the mxfile element. Document compression handling as Phase 4 work.

2. **ruamel.yaml `CommentedMap` and Pydantic `model_dump()`**
   - What we know: `model_dump()` returns a regular Python dict; ruamel.yaml needs `CommentedMap` to preserve key ordering
   - What's unclear: Whether ruamel.yaml will preserve ordering when dumping a plain dict or if it requires `CommentedMap` conversion
   - Recommendation: Test by dumping a plain dict through ruamel.yaml and checking key order in the output. If plain dict sorting is wrong, convert to `CommentedMap` with explicit ordering in the write path.

3. **Attribute parent-child relationship in Draw.io**
   - What we know: The swimlane pattern uses `parent=class_cell_id` for attribute rows, and the class cell uses `childLayout=stackLayout`
   - What's unclear: Whether lxml-generated swimlane cells with child cells render correctly in current Draw.io (version drift since documentation was written)
   - Recommendation: Validate during SCHEMA-04 round-trip test. If swimlane auto-layout doesn't work, fall back to absolute positioning (no childLayout, fixed y-offsets per attribute).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `mdf-server/pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 |
| Quick run command | `cd mdf-server && uv run pytest tests/ -x -q` |
| Full suite command | `cd mdf-server && uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCHEMA-01 | Valid YAML accepted by Pydantic models | unit | `uv run pytest tests/test_yaml_schema.py -x` | Wave 0 |
| SCHEMA-02 | YAML without `schema_version` rejected | unit | `uv run pytest tests/test_yaml_schema.py::test_missing_schema_version -x` | Wave 0 |
| SCHEMA-02 | YAML with invalid semver rejected | unit | `uv run pytest tests/test_yaml_schema.py::test_invalid_semver -x` | Wave 0 |
| SCHEMA-03 | Bijection table is complete (all YAML elements have a style entry) | unit | `uv run pytest tests/test_drawio_schema.py -x` | Wave 0 |
| SCHEMA-04 | Generated XML → Draw.io → saved XML → sync parser → same structure | integration | `uv run pytest tests/test_roundtrip.py -x` | Wave 0 |
| SCHEMA-05 | Template files exist and contain required sections | smoke | `uv run pytest tests/test_templates.py -x` | Wave 0 |
| TMPL-01..04 | Template files exist at correct paths | smoke | `uv run pytest tests/test_templates.py -x` | Wave 0 |

**Note on SCHEMA-04:** The "open in real Draw.io" step is manual (cannot automate without a headless Draw.io driver). The automated test covers: generate XML → parse with defusedxml → re-parse → structural equality. The human step (open in Draw.io, save, check diff) is a checklist item in the verification plan.

### Sampling Rate

- **Per task commit:** `cd mdf-server && uv run pytest tests/ -x -q`
- **Per wave merge:** `cd mdf-server && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `mdf-server/` package — does not exist; must be initialized with `uv init`
- [ ] `mdf-server/mdf_server/schema/__init__.py` — empty init file
- [ ] `mdf-server/mdf_server/schema/yaml_schema.py` — Pydantic models
- [ ] `mdf-server/mdf_server/schema/drawio_schema.py` — bijection constants
- [ ] `mdf-server/tests/__init__.py`
- [ ] `mdf-server/tests/test_yaml_schema.py` — covers SCHEMA-01, SCHEMA-02
- [ ] `mdf-server/tests/test_drawio_schema.py` — covers SCHEMA-03
- [ ] `mdf-server/tests/test_roundtrip.py` — covers SCHEMA-04
- [ ] `mdf-server/tests/test_templates.py` — covers SCHEMA-05, TMPL-01..04
- [ ] Framework install: `cd mdf-server && uv init && uv add pydantic pyyaml "ruamel.yaml" lxml defusedxml && uv add --dev pytest ruff mypy`

---

## Sources

### Primary (HIGH confidence)
- CONTEXT.md (2026-03-05) — all schema decisions locked; source of truth for this phase
- `.planning/research/STACK.md` (2026-03-05) — library versions and rationale
- `.planning/research/ARCHITECTURE.md` (2026-03-05) — module structure, file layout, tool contracts
- [Pydantic v2 Validators docs](https://docs.pydantic.dev/latest/concepts/validators/) — `field_validator`, `model_validator` decorator signatures and modes
- [Pydantic v2 Models docs](https://docs.pydantic.dev/latest/concepts/models/) — `model_validate()`, `model_dump()`, required vs optional fields

### Secondary (MEDIUM confidence)
- [Draw.io mxGraphModel format](https://www.drawio.com/doc/faq/diagram-source-edit) — stable XML format; swimlane/mxCell patterns verified against training knowledge and community examples
- [Draw.io GitHub discussions on shape styles](https://github.com/jgraph/drawio/discussions/2536) — mxCell style string patterns for UML elements

### Tertiary (LOW confidence)
- WebSearch results on Draw.io XML generation — style string exact values need validation against actual Draw.io output during SCHEMA-04 round-trip test

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all library choices locked in STACK.md with version verification
- Pydantic v2 patterns: HIGH — verified against current official docs
- Draw.io style strings: MEDIUM — patterns known but exact strings must be verified during round-trip test (SCHEMA-04)
- Architecture: HIGH — derived directly from locked ARCHITECTURE.md and CONTEXT.md decisions
- Pitfalls: HIGH — most are mechanical consequences of the locked decisions; Draw.io compression pitfall is MEDIUM (needs empirical confirmation)

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable libraries; Draw.io format has never broken backward compatibility)
