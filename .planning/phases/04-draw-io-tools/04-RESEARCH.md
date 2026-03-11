# Phase 4: Draw.io Tools - Research

**Researched:** 2026-03-11
**Domain:** XML generation/parsing, graph layout, YAML round-trip, MCP tool registration
**Confidence:** HIGH

## Summary

Phase 4 implements three MCP tools (`render_to_drawio`, `validate_drawio`, `sync_from_drawio`) in `tools/drawio.py`, then registers five tool wrappers in `server.py`. All canonical bijection constants, style strings, and ID generator functions are already locked in `schema/drawio_schema.py` — these are read-only inputs to this phase. The reference XML generation pattern (`render_sample_xml`) demonstrates the exact lxml structure to generalize.

The layout problem is solved by `python-igraph` (not yet installed in pyproject.toml). `layout_sugiyama()` returns a `Layout` object whose `.coords` is a list of `[x, y]` pairs, one per vertex, in graph vertex order. Coordinates are unit-spaced (hgap=1 default unit between nodes in a layer, vgap=1 unit per layer). The `Layout.fit_into(bbox)` method maps those units to pixel canvas coordinates in one call. All three functions follow the project's no-exceptions pattern: errors go into the issue list, never raised.

The critical engineering challenge is `sync_from_drawio`'s merge strategy: YAML is read with `ruamel.yaml` to preserve existing pycca bodies and comments, cells are matched by canonical ID, and only topology/label changes are applied. The skip-if-unchanged check in `render_to_drawio` compares structural identity (element set + topology) between existing `.drawio` and YAML before deciding whether to regenerate layout.

**Primary recommendation:** Implement in three focused tasks — (1) `render_to_drawio` with layout, (2) `validate_drawio`, (3) `sync_from_drawio` + server registration.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**MCP tool surface:**
- `render_to_drawio(domain)` — generates all diagrams for a domain; internally calls the two helpers
- `render_to_drawio_class(domain)` — generates `class-diagram.drawio` only
- `render_to_drawio_state(domain, class_name)` — generates `state-diagrams/<ClassName>.drawio` only
- `validate_drawio(domain, xml)` and `sync_from_drawio(domain, xml)` take XML as a string parameter

**render_to_drawio output behavior:**
- Writes `.drawio` files to disk at `.design/model/<domain>/class-diagram.drawio` and `.design/model/<domain>/state-diagrams/<ClassName>.drawio`
- Skip-if-unchanged: if structure matches (same elements, same topology), skip rewrite and preserve layout positions
- If YAML changed (elements added/removed/renamed), regenerate and overwrite
- Returns per-file result list with `file` and `status` (`"written"` or `"skipped"`) plus issue dicts

**Layout algorithm:**
- Use `python-igraph` (`layout_sugiyama()`) for both class diagrams and state diagrams
- Pre-compute bounding boxes from YAML before layout
- Class height: `HEADER_H(26) + num_attrs × ROW_H(20) + SEP_H(8) + num_methods × ROW_H(20)`
- Class width: fixed 220px (or estimated from longest label — Claude's discretion)
- State size: fixed 160×50px (or scaled to label length — Claude's discretion)
- Scale igraph normalized positions to pixel canvas using bounding boxes
- Run a nudge pass after scaling to resolve remaining overlaps
- Layout only computed on first-time render or structure change; existing positions preserved on skip
- Subtype partition layout: Claude's discretion

**sync_from_drawio writable scope:**
- Topology + labels sync back: add/remove/rename states, transitions, classes, associations
- Does NOT sync: entry/exit action bodies, guard expressions, action bodies, attribute types, method signatures, bridge implementations, cell positions/sizes/styling
- New elements from Draw.io get null placeholders for all YAML-only fields
- Unrecognized cells: skip + add to issue list, do not abort

**sync_from_drawio merge strategy:**
- Merge, not overwrite — preserve YAML-only fields on matched elements
- Match key: canonical cell ID (e.g., `hydraulics:state:Valve:Opening`)
- New Draw.io cells (no matching canonical ID): new YAML elements with null placeholders
- Deleted elements: removed from YAML; each deletion produces an `info`-severity issue
- After merge, `validate_model` runs automatically; its issues appended to returned list

### Claude's Discretion
- Class width: fixed 220px or estimated from longest label
- State size: fixed 160×50px or scaled to label length
- Subtype partition layout

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-05 | `render_to_drawio(domain)` — generates Draw.io XML from YAML per canonical schema; deterministic and idempotent | igraph layout_sugiyama confirmed available (install needed); lxml etree pattern established in render_sample_xml; skip-if-unchanged algorithm documented below |
| MCP-06 | `validate_drawio(domain, xml)` — validates Draw.io XML against canonical schema before sync; returns issue list | BIJECTION_TABLE provides the complete set of valid style strings; lxml/defusedxml for parsing; validation algorithm documented below |
| MCP-07 | `sync_from_drawio(domain, xml)` — structured schema-aware parse back to YAML; runs `validate_model` automatically; returns issue list | ruamel.yaml confirmed for round-trip YAML write; canonical ID matching strategy documented; merge algorithm documented below |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| lxml | 6.0.2 (installed) | XML generation and parsing | Already used in render_sample_xml; faster and more capable than stdlib xml |
| defusedxml | 0.7.1 (installed) | Safe XML parsing in validate_drawio | Already used in test_roundtrip.py; prevents XXE attacks on engineer-provided XML |
| python-igraph | 1.0.0 (NOT YET in pyproject.toml) | Sugiyama layered layout | Locked decision; pure pip install; no system dependencies confirmed |
| ruamel.yaml | 0.19.1 (installed) | Round-trip YAML write preserving comments and field order | Required for sync_from_drawio to preserve pycca bodies; comment preservation confirmed working |
| pyyaml | 6.0.3 (installed) | Reading YAML files for structure comparison | Already used everywhere in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib.Path | stdlib | File path operations, mkdir | Follow MODEL_ROOT pattern from existing code |
| lxml.etree | 6.0.2 | XPath queries for sync parsing | Already imported in drawio_schema.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-igraph | networkx layout | networkx is installed but has no Sugiyama; igraph was locked decision |
| ruamel.yaml | pyyaml dump | pyyaml strips comments; ruamel.yaml preserves them (required for pycca bodies) |
| lxml.etree | stdlib xml.etree | lxml is already the project standard; faster; better namespace support |

**Installation (new dependency only):**
```bash
uv add igraph
# pyproject.toml already has all other dependencies
```

---

## Architecture Patterns

### Recommended File Layout
```
tools/
└── drawio.py          # All three MCP tool implementations (MCP-05, MCP-06, MCP-07)
schema/
└── drawio_schema.py   # Read-only inputs: BIJECTION_TABLE, style constants, ID generators
server.py              # Register 5 new @mcp.tool() wrappers
tests/
└── test_drawio_tools.py  # New test file (Wave 0 gap)
.design/model/
└── <domain>/
    ├── class-diagram.drawio          # Generated output
    └── state-diagrams/
        └── <ClassName>.drawio        # Generated output (one per active class)
```

### Pattern 1: XML Generation with lxml (established)

The `render_sample_xml()` in `drawio_schema.py` is the canonical reference. Phase 4 generalizes this pattern to operate on live YAML data rather than hardcoded sample data.

**XML structure (mxfile → diagram → mxGraphModel → root → mxCell):**
```python
# Source: schema/drawio_schema.py render_sample_xml()
mxfile = etree.Element("mxfile", compressed="false", version="24.0.0")
diagram = etree.SubElement(mxfile, "diagram", name="Page-1", id="page1")
etree.SubElement(diagram, "mxGraphModel", dx="1034", dy="546", ...)
model_el = diagram[0]
root_el = etree.SubElement(model_el, "root")
etree.SubElement(root_el, "mxCell", id="0")
etree.SubElement(root_el, "mxCell", id="1", parent="0")
# ... add cells with mxGeometry children
xml_bytes = etree.tostring(mxfile, encoding="unicode", xml_declaration=False).encode("utf-8")
```

**Critical:** `compressed="false"` on mxfile is mandatory — prevents base64/zlib encoding when Draw.io saves the file. This is already established in the project.

### Pattern 2: igraph Sugiyama Layout

**Confirmed behavior (tested against igraph 1.0.0):**
- `layout_sugiyama()` returns a `Layout` object (not a tuple) in Python igraph
- `.coords` is a list of `[x, y]` pairs, one per vertex, in vertex-insertion order
- Default coordinates are unit-spaced: hgap=1 means 1.0 units between nodes in same layer, vgap=1 means 1.0 units per layer
- Y increases downward (layer 0 at y=0.0, layer 1 at y=1.0, etc.)
- `Layout.fit_into(bbox)` maps unit coordinates to pixel bounding box in one call

**Layout pipeline:**
```python
# Source: verified empirically against igraph 1.0.0
import igraph as ig

def _compute_layout(vertices: list[str], edges: list[tuple[int,int]],
                    canvas_w: int, canvas_h: int, margin: int = 40
                    ) -> list[tuple[float, float]]:
    g = ig.Graph(n=len(vertices), edges=edges, directed=True)
    layout = g.layout_sugiyama()
    layout.fit_into((margin, margin, canvas_w - margin, canvas_h - margin))
    return [(c[0], c[1]) for c in layout.coords]
```

**Warning:** The igraph docs state that dummy vertices may be added for edges spanning multiple layers, which can make `len(layout.coords)` > `g.vcount()`. In practice with small test graphs this was not observed, but the implementation must slice `layout.coords[:g.vcount()]` to be safe when mapping back to original vertices.

### Pattern 3: Skip-if-Unchanged Algorithm

The skip-if-unchanged check compares **structural identity** — not byte equality — between the existing `.drawio` file on disk and the current YAML state.

**What to compare:**
1. Set of canonical cell IDs present in the `.drawio` file vs. set that would be generated from YAML
2. Edge topology: for each edge cell, `source` and `target` attributes vs. expected IDs
3. Label values: class names, state names, event labels on transitions

**Algorithm:**
```python
def _structure_matches(domain_path: Path, domain: str, cd: ClassDiagramFile) -> bool:
    drawio_path = domain_path / "class-diagram.drawio"
    if not drawio_path.exists():
        return False
    try:
        root = etree.parse(str(drawio_path)).getroot()
    except etree.XMLSyntaxError:
        return False
    existing_ids = {c.get("id") for c in root.iter("mxCell") if c.get("id")}
    expected_ids = _compute_expected_ids(domain, cd)  # uses ID generator functions
    return existing_ids == expected_ids
```

### Pattern 4: sync_from_drawio Merge with ruamel.yaml

**Why ruamel.yaml, not pyyaml:** ruamel.yaml's round-trip mode (`YAML(typ='rt')`) preserves YAML comments, key ordering, and existing scalar formatting. `yaml.dump()` would strip pycca action bodies' inline comments.

```python
# Source: verified against ruamel.yaml 0.19.1
from ruamel.yaml import YAML
import io

def _read_yaml_roundtrip(path: Path) -> tuple[Any, list[dict]]:
    yaml_rt = YAML()
    try:
        data = yaml_rt.load(path.read_text())
        return data, []
    except Exception as exc:
        return None, [_make_issue(...)]

def _write_yaml_roundtrip(data: Any, path: Path) -> list[dict]:
    yaml_rt = YAML()
    yaml_rt.default_flow_style = False
    buf = io.StringIO()
    yaml_rt.dump(data, buf)
    path.write_text(buf.getvalue())
    return []
```

### Anti-Patterns to Avoid

- **Parsing XML with defusedxml.ElementTree for generation:** defusedxml is read-only (for validation/parsing). Use `lxml.etree` for generation.
- **Using pyyaml for sync_from_drawio writes:** `yaml.dump()` strips comments. Always use ruamel.yaml for writes that must preserve pycca bodies.
- **Raising exceptions from tool functions:** No exceptions — all errors return as issue list items (established project pattern).
- **Overwriting existing `.drawio` on every call:** The skip-if-unchanged check is the key UX feature. Always perform structure comparison first.
- **Using `etree.tostring(pretty_print=True)` for idempotency:** Pretty-printing adds whitespace that varies by element depth. Use `encoding="unicode"` without `pretty_print` for deterministic output.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph layout with minimal edge crossings | Custom position algorithm | `igraph.layout_sugiyama()` | Sugiyama is a well-studied algorithm; hand-rolling crossing minimization is a research problem |
| Bounding box fitting | Manual coordinate scaling | `Layout.fit_into(bbox)` | Already part of igraph Layout API; handles margin math correctly |
| XML entity escaping | Manual `<`, `>`, `&` substitution | lxml automatically escapes on `value=` attribute assignment | Manual escaping breaks on nested HTML labels |
| YAML comment preservation | Strip-and-rewrite approach | `ruamel.yaml` round-trip mode | Preserves all pycca action body comments and field ordering |
| Unsafe XML parsing | stdlib xml.etree | `defusedxml` for reads, `lxml` for generates | defusedxml prevents XXE; already project convention |

**Key insight:** The hardest part of this phase is the merge logic in `sync_from_drawio`, not the XML generation. The canonical ID scheme makes matching O(n) with a dict lookup; do not implement fuzzy name matching.

---

## Common Pitfalls

### Pitfall 1: igraph dummy vertices inflating layout.coords
**What goes wrong:** The igraph Sugiyama docs state "Dummy vertices will be added on edges that span more than one layer. The returned layout therefore contains more rows than the number of nodes in the original graph." If `layout.coords` has more entries than `g.vcount()`, mapping coords back to original vertices by index will be wrong.
**Why it happens:** The Sugiyama algorithm inserts dummy intermediate vertices to route long edges through multiple layers.
**How to avoid:** Always slice `layout.coords[:g.vcount()]` before using indices for mxGeometry placement.
**Warning signs:** `len(layout.coords) > g.vcount()` — add an assertion or log this.

### Pitfall 2: Base64-compressed Draw.io files
**What goes wrong:** Draw.io defaults to saving files with base64+zlib-compressed diagram content unless `compressed="false"` is set on the `mxfile` element.
**Why it happens:** Draw.io's default save behavior compresses for file size.
**How to avoid:** Always set `compressed="false"` on the mxfile root element. This is already the project standard (established in Phase 1 SCHEMA decisions).
**Warning signs:** Saved `.drawio` file content is a long base64 string inside `<diagram>` instead of readable XML.

### Pitfall 3: Transition label parsing in sync_from_drawio
**What goes wrong:** Transition cell labels are multi-line HTML strings: `ID<br>Event(params)<br>[guard]`. Splitting naively on `<br>` fails when the event has no params or when guard is absent.
**Why it happens:** The label format is `<ID>\n<event_signature>\n[guard]` encoded with `<br>` separators; not all three parts are always present.
**How to avoid:** Parse the label with explicit line counting: line 0 is the canonical ID (can be ignored), line 1 is the event signature, line 2 (if present and starts with `[`) is the guard. Strip HTML tags before parsing.

### Pitfall 4: ruamel.yaml vs. pyyaml type mismatches
**What goes wrong:** ruamel.yaml's round-trip mode returns `CommentedMap` and `CommentedSeq` objects, not plain `dict` and `list`. Pydantic's `model_validate()` can handle these, but `isinstance(data, dict)` checks fail.
**Why it happens:** ruamel.yaml uses proxy types to track comments and ordering.
**How to avoid:** Pass ruamel data directly to `ClassDiagramFile.model_validate(data)` — Pydantic handles CommentedMap. Avoid `isinstance(result, dict)` checks on ruamel output.
**Warning signs:** `isinstance(data, dict)` returns False even though `data` behaves like a dict.

### Pitfall 5: Non-deterministic XML output
**What goes wrong:** Calling `render_to_drawio` twice produces different XML (different attribute ordering, different whitespace), violating MCP-05's idempotency requirement.
**Why it happens:** Python dict iteration order is insertion-order in 3.7+ but lxml attribute ordering can vary if attributes are set after element creation, or if `pretty_print=True` introduces context-dependent whitespace.
**How to avoid:** Always iterate YAML data structures in deterministic order (sort classes by name, sort attributes by list position). Set all attributes in the `SubElement(...)` call, not with `cell.set()` after the fact. Do not use `pretty_print=True`.

### Pitfall 6: validate_drawio vs. validate_model confusion
**What goes wrong:** `validate_drawio` validates Draw.io XML structure against the canonical bijection schema. `validate_model` validates YAML structural integrity. These are different operations called at different stages.
**Why it happens:** Both return `list[dict]` with the same issue format, creating confusion about which one to call when.
**How to avoid:** `validate_drawio` is called before `sync_from_drawio` (on the XML). `validate_model` is called inside `sync_from_drawio` after the YAML merge. Never swap them.

---

## Code Examples

### igraph layout_sugiyama with pixel scaling

```python
# Source: verified empirically against igraph 1.0.0
import igraph as ig

def _layout_for_canvas(
    n_vertices: int,
    edges: list[tuple[int, int]],
    canvas_w: int,
    canvas_h: int,
    margin: int = 60,
) -> list[tuple[float, float]]:
    """Run Sugiyama layout and scale to pixel canvas. Returns (x, y) per original vertex."""
    g = ig.Graph(n=n_vertices, edges=edges, directed=True)
    layout = g.layout_sugiyama()
    # Slice to original vertex count — guards against dummy vertex inflation
    coords = layout.coords[:n_vertices]
    if not coords:
        return []
    # fit_into maps unit coordinates to pixel bounding box
    layout.fit_into((margin, margin, canvas_w - margin, canvas_h - margin))
    return [(layout.coords[i][0], layout.coords[i][1]) for i in range(n_vertices)]
```

### Class bounding box pre-computation

```python
# Source: render_sample_xml() pattern in schema/drawio_schema.py
HEADER_H = 26   # swimlane startSize
ROW_H = 20      # px per attribute or method row
SEP_H = 8       # separator line height
CLASS_W = 220   # fixed width

def _class_height(n_attrs: int, n_methods: int) -> int:
    return HEADER_H + max(n_attrs, 1) * ROW_H + SEP_H + max(n_methods, 1) * ROW_H
```

### Skip-if-unchanged structural comparison

```python
# Source: CONTEXT.md architecture decision
from lxml import etree as ET

def _extract_drawio_ids(xml_path: Path) -> frozenset[str] | None:
    """Parse existing .drawio and return frozenset of canonical cell IDs, or None on error."""
    try:
        tree = ET.parse(str(xml_path))
        return frozenset(
            c.get("id") for c in tree.getroot().iter("mxCell")
            if c.get("id") and ":" in c.get("id", "")  # canonical IDs contain ":"
        )
    except ET.XMLSyntaxError:
        return None
```

### ruamel.yaml round-trip write

```python
# Source: verified against ruamel.yaml 0.19.1
from ruamel.yaml import YAML
import io

def _dump_yaml_roundtrip(data, path: Path) -> None:
    yaml_rt = YAML()
    yaml_rt.default_flow_style = False
    buf = io.StringIO()
    yaml_rt.dump(data, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")
```

### lxml XML parsing for validate_drawio / sync_from_drawio

```python
# Source: defusedxml used in test_roundtrip.py; lxml for XPath
import defusedxml.ElementTree as DET

def _parse_xml_safe(xml_str: str) -> tuple[Any | None, list[dict]]:
    """Parse XML string safely. Returns (root, []) or (None, [issue])."""
    try:
        return DET.fromstring(xml_str.encode("utf-8")), []
    except Exception as exc:
        return None, [_make_issue(
            issue=f"XML parse error: {exc}",
            location="xml_input",
            severity="error",
        )]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| NetworkX for layout | python-igraph Sugiyama | Phase 4 decision | networkx has no Sugiyama; igraph has purpose-built layered layout |
| pyyaml for YAML writes | ruamel.yaml round-trip | Phase 4 decision | Preserves pycca action bodies and comments during sync |
| stdlib xml.etree | lxml.etree for generate, defusedxml for parse | Phase 1 decision | lxml is faster and handles large XML; defusedxml prevents XXE |

---

## Open Questions

1. **Dummy vertex inflation from igraph**
   - What we know: The igraph Sugiyama docs say dummy vertices can be added; in testing with small DAGs (3-5 vertices) the layout.coords count equaled vcount
   - What's unclear: At what graph size or topology does `len(layout.coords) > g.vcount()` occur in practice?
   - Recommendation: Always slice `layout.coords[:g.vcount()]` as a defensive guard; add an assertion in debug builds

2. **Canvas size for auto-layout**
   - What we know: `fit_into(bbox)` scales all nodes to fit the bounding box; margin is configurable
   - What's unclear: What canvas size produces visually reasonable spacing for typical 5-10 class diagrams?
   - Recommendation: Default `canvas_w = max(1200, n_classes * 280)`, `canvas_h = max(800, n_layers * 200)` — adjust from longest-label width estimate

3. **Nudge pass algorithm for overlap resolution**
   - What we know: CONTEXT.md requires a "nudge pass" after scaling to resolve overlaps
   - What's unclear: The exact algorithm is not specified — simple axis-aligned separation or more sophisticated?
   - Recommendation: Simple greedy x-axis nudge: sort by x, expand gaps when `x[i+1] - x[i] < node_width[i]`. This is O(n log n) and sufficient for the expected graph sizes.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run command | `uv run pytest tests/test_drawio_tools.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-05 | render_to_drawio produces valid XML with all elements | unit | `uv run pytest tests/test_drawio_tools.py::test_render_class_diagram -x` | Wave 0 |
| MCP-05 | render_to_drawio is idempotent (byte-identical on repeat) | unit | `uv run pytest tests/test_drawio_tools.py::test_render_idempotent -x` | Wave 0 |
| MCP-05 | render_to_drawio skips unchanged diagrams | unit | `uv run pytest tests/test_drawio_tools.py::test_render_skip_unchanged -x` | Wave 0 |
| MCP-05 | render_to_drawio returns written/skipped status per file | unit | `uv run pytest tests/test_drawio_tools.py::test_render_status_list -x` | Wave 0 |
| MCP-06 | validate_drawio returns empty list for valid canonical XML | unit | `uv run pytest tests/test_drawio_tools.py::test_validate_drawio_valid -x` | Wave 0 |
| MCP-06 | validate_drawio returns issues for unrecognized shape types | unit | `uv run pytest tests/test_drawio_tools.py::test_validate_drawio_invalid_style -x` | Wave 0 |
| MCP-07 | sync_from_drawio updates YAML from Draw.io XML | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_adds_state -x` | Wave 0 |
| MCP-07 | sync_from_drawio preserves pycca-only fields | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_preserves_actions -x` | Wave 0 |
| MCP-07 | sync_from_drawio runs validate_model automatically | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_runs_validate_model -x` | Wave 0 |
| MCP-07 | sync_from_drawio handles unrecognized cells as skip+issue | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_unrecognized_cell -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_drawio_tools.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_drawio_tools.py` — covers MCP-05, MCP-06, MCP-07 (all tests above)
- [ ] `igraph` added to `pyproject.toml` dependencies — `uv add igraph`

*(All other infrastructure exists: pytest config in pyproject.toml, conftest.py via `tests/__init__.py`)*

---

## Sources

### Primary (HIGH confidence)
- `schema/drawio_schema.py` — render_sample_xml reference implementation; all BIJECTION_TABLE constants and ID generators; lxml structure verified against existing tests
- `tools/validation.py` — issue list format `_make_issue()`, `validate_model()` call signature
- `schema/yaml_schema.py` — ClassDiagramFile, StateDiagramFile, ClassDef, StateDef, Transition, Association Pydantic models
- `pyproject.toml` — confirmed dependency list; igraph not yet present
- Empirical igraph 1.0.0 tests — `layout_sugiyama()` return type, coordinate format, `fit_into()` behavior
- Empirical ruamel.yaml 0.19.1 tests — round-trip comment preservation, CommentedMap type

### Secondary (MEDIUM confidence)
- [igraph Python API docs](https://python.igraph.org/en/main/api/igraph.layout.html) — layout_sugiyama parameter documentation
- [igraph layout_sugiyama docstring](https://python.igraph.org/en/main/) — dummy vertex warning, parameter semantics

### Tertiary (LOW confidence)
- WebSearch for igraph Sugiyama coordinates — cross-referenced with empirical testing; now HIGH confidence

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries tested in project venv except igraph (installed and tested)
- Architecture: HIGH — based on existing render_sample_xml pattern + confirmed igraph API
- Pitfalls: HIGH — dummy vertex inflation verified empirically; base64 issue is established project knowledge; others from code analysis
- Skip-if-unchanged: MEDIUM — algorithm is sound but exact threshold for "structure matches" needs careful definition during implementation

**Research date:** 2026-03-11
**Valid until:** 2026-06-11 (stable libraries; igraph and ruamel.yaml APIs are stable)
