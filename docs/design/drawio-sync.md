# Draw.io Bidirectional Sync Design

This document describes the design of the Draw.io ↔ YAML synchronization system in `tools/drawio.py`. It is a reference for developers extending the Draw.io tools.

---

## 1. Two Directions

The system supports two operations on each diagram type.

### YAML → Draw.io (render)

**Functions:** `render_to_drawio`, `render_to_drawio_class`, `render_to_drawio_state`

Render reads YAML source files, computes a full layout, and writes a `.drawio` XML file. It is the authoritative path for creating diagrams from scratch or after structural changes to the model.

**When it is used:**
- First-time diagram generation
- After structural changes to the YAML that alter the canonical content (new states, new classes, renamed transitions, etc.)
- Explicitly forced via `force=True`

**What it does:**
1. Loads and validates the YAML source (`ClassDiagramFile` or `StateDiagramFile`)
2. Computes canonical JSON from the YAML (see section 2)
3. Compares canonical JSON against the existing `.drawio` file's canonical JSON
4. If they match: returns `{"status": "skipped"}` without touching the file
5. If they differ (or the file is absent): runs layout, generates XML, writes the file

The diagram file path follows the convention:
```
.design/diagrams/{domain}-class-diagram.drawio
.design/diagrams/{domain}-{ClassName}.drawio
```

`render_to_drawio` is a convenience wrapper that renders the class diagram first, then discovers active classes and renders a state diagram for each.

### Draw.io → YAML (sync)

**Function:** `sync_from_drawio(domain, class_name, xml)`

Sync reads Draw.io XML provided by the caller (e.g., after the user has edited the diagram in Draw.io) and merges structural changes back into the YAML source. It operates only on state diagrams; class diagram sync is out of scope.

**When it is used:**
- After a developer has manually added, removed, or renamed states or transitions in Draw.io and wants those changes reflected in the YAML.

**What it does:**
1. Parses the XML with `defusedxml`
2. Scans `mxCell` elements for recognized state and transition IDs
3. Computes the diff against the existing YAML:
   - States in Draw.io but not YAML → added
   - States in YAML but not Draw.io → deleted
   - Transitions by canonical ID: new IDs added, missing IDs deleted
4. Merges changes into the YAML using ruamel round-trip mode (preserves all existing fields)
5. Writes the updated YAML back to disk
6. Runs `validate_class` and appends any validation issues to the return list

```
Draw.io XML ──parse──> mxCell scan
                            │
                ┌───────────┴───────────┐
           new states             deleted states
           new transitions        deleted transitions
                │                       │
                └───────────┬───────────┘
                        merge into
                      CommentedMap
                            │
                    ruamel write YAML
                            │
                    validate_class
```

---

## 2. Canonical JSON Comparison

### Purpose

Re-rendering a diagram from scratch destroys any manual layout adjustments the developer has made in Draw.io (node positions, custom edge routing, waypoints). The canonical comparison lets the renderer skip re-rendering when the YAML content has not changed in any way that would affect the diagram's structure.

### How it works

Both sides — the YAML source and the existing `.drawio` file — are independently reduced to a canonical JSON string. The strings are compared with `==`.

```
YAML source ──yaml_to_canonical_*──> canonical JSON string ──┐
                                                               compare → skip / render
.drawio XML ──drawio_to_canonical_*──> canonical JSON string ──┘
```

The canonical form (defined in `schema/drawio_canonical.py`) captures only the structural fields that the renderer uses to produce diagram content:

**State diagram:**
```
CanonicalStateDiagram {
  type, domain, class,
  initial_state,
  states: [{ name, entry_action }],          # sorted by name
  transitions: [{ from, to, event, params, guard }]  # sorted by (from, event, to)
}
```

**Class diagram:**
```
CanonicalClassDiagram {
  type, domain,
  classes: [{ name, stereotype, specializes, attributes[], methods[] }],  # sorted by name
  associations: [{ name, point_1, point_2, 1_mult_2, 2_mult_1, 1_phrase_2, 2_phrase_1 }],
  generalizations: [{ name, supertype, subtypes[] }]
}
```

The JSON is serialized with `sort_keys=True`, making the comparison order-independent for dict keys. Lists are normalized to a canonical sort order before serialization.

### What triggers a re-render

Any change that alters the canonical JSON causes a re-render:
- Adding, removing, or renaming a state
- Changing `entry_action` on any state
- Adding, removing, or altering `guard` or `event` on a transition
- Adding or removing a class, attribute, method, or association

### What does not trigger a re-render

Changes to YAML fields that are not part of the canonical schema are invisible to the comparison and therefore never trigger a re-render:
- Comments in the YAML

This is intentional: comments do not appear in the diagram and should not cause layout destruction.

### drawio_to_canonical_*

The reverse path parses an existing `.drawio` XML file and reconstructs the canonical JSON from it. It extracts structural information from:
- Cell IDs (deterministic, encode domain/class/name; see section 5)
- Cell `value` attributes (state labels encode `entry_action` after the `<i>entry /</i><br>` marker; transition labels encode event name, params, and guard)
- Cell `source`/`target` attributes (transition endpoints)

If the file is missing or malformed, `_drawio_to_canonical_*` returns `None`, which forces a re-render.

---

## 3. Sync Merge Strategy

`sync_from_drawio` performs a merge, not a replace. The key design constraint is that the YAML is the source of truth for semantic content (action bodies, guard expressions), while Draw.io is the source of truth for diagram topology (which states and transitions exist).

### What sync will write

| Change | Action |
|--------|--------|
| State present in Draw.io, absent in YAML | Add `{name: X, entry_action: null}` to `states` list |
| State present in YAML, absent in Draw.io | Remove from `states` list (only when Draw.io has at least one state cell — prevents accidental total deletion from a malformed XML) |
| Transition ID present in Draw.io, absent in YAML | Add `{from, to, event, guard, action: null}` to `transitions` list |
| Transition ID present in YAML, absent in Draw.io | Remove from `transitions` list |

Transition identity is based on the canonical transition ID embedded in the cell's `id` attribute:
```
{domain}:trans:{ClassName}:{from_state}:{event}:{idx}
```
Two transitions with the same `(from_state, event)` pair but different `idx` values are treated as distinct.

### What sync will not overwrite

- `entry_action` on existing states — the YAML value is preserved even if the state is already present in Draw.io. A newly added state always gets `entry_action: null`; the developer fills it in.
- `guard` on existing transitions — preserved from YAML. A newly added transition gets the guard parsed from the Draw.io label (if present) or `null`.
- `action` on any transition — always `null` on new transitions; existing `action` bodies are never touched.
- Events list (`events:`) — untouched.
- Any other top-level YAML fields.

### Guard handling on new transitions

When a transition is new (its canonical ID is absent in YAML), sync parses its Draw.io label to recover the event name and guard:

```
Label format:
  {trans_id}<br>{EventName}({params})<br>[{guard}]
```

`_parse_trans_label` splits on `<br>`, strips HTML, and extracts line 1 for the event name and line 2 (if wrapped in `[...]`) for the guard. This allows a developer to add a guard directly in Draw.io and have it written to the YAML on sync.

### Unrecognized styles during sync

Cells with styles that are not in `BIJECTION_TABLE` produce a `warning`-severity issue and are skipped. Sync does not abort; it continues processing the remaining cells. This means manually styled cells added by a developer in Draw.io do not corrupt the YAML but are flagged for attention.

---

## 4. ruamel Round-Trip Preservation

### Why ruamel.yaml instead of PyYAML

PyYAML (`yaml.safe_load` / `yaml.dump`) does not preserve:
- Inline comments (`# comment`)
- Key ordering
- Multi-line string styles (literal `|` vs folded `>`)
- Blank lines between blocks

When sync rewrites the YAML file, all of these would be lost if PyYAML were used. State diagrams commonly have entry actions written as multi-line literal strings with meaningful indentation:

```yaml
states:
  - name: Opening
    entry_action: |
      self.target = rcvd_evt.target_position;
      Timer::start_timer(timeout_ms);
```

If this were re-serialized by PyYAML, it could become a quoted single-line string or lose the literal-block indicator, breaking readability.

### How it works

`_read_yaml_roundtrip` and `_write_yaml_roundtrip` use `ruamel.yaml` in round-trip mode (`YAML()`), which returns a `CommentedMap`/`CommentedSeq` tree that records comments, ordering, and string style as metadata attached to the nodes. When the tree is serialized back, this metadata is replayed faithfully.

Only the structural nodes that sync touches (the `states` and `transitions` lists) are mutated. The rest of the document is written back unchanged.

### What would break without it

- All `entry_action` multi-line strings would be re-serialized with PyYAML's default style (quoted or flow), making them unreadable.
- Inline comments documenting state purpose or action rationale would be silently discarded.
- Key ordering within dicts would be randomized, producing noisy diffs in version control.

---

## 5. Style Bijection

### BIJECTION_TABLE

`schema/drawio_schema.py` defines a mapping from canonical element-type names to their exact mxCell style strings:

```python
BIJECTION_TABLE: dict[str, str] = {
    "class":          STYLE_CLASS,          # swimlane, blue fill
    "class_active":   STYLE_CLASS_ACTIVE,   # swimlane, green fill
    "attribute":      STYLE_ATTRIBUTE,      # text cell inside swimlane
    "separator":      STYLE_SEPARATOR,      # horizontal rule between attrs/methods
    "association":    STYLE_ASSOCIATION,    # orthogonal edge, no arrowheads
    "assoc_label":    STYLE_ASSOC_LABEL,    # floating edge label (mult/phrase)
    "generalization": STYLE_GENERALIZATION, # orthogonal edge, hollow-triangle arrowhead
    "state":          STYLE_STATE,          # rounded rectangle, Courier New
    "initial_pseudo": STYLE_INITIAL_PSEUDO, # filled black ellipse
    "transition":     STYLE_TRANSITION,     # orthogonal edge
    "bridge":         STYLE_BRIDGE,         # dashed open-arrow edge
    "separator":      STYLE_SEPARATOR,
}
```

These are immutable constants. The bijection is strict: each element type maps to exactly one style string, and each style string maps to exactly one element type.

### ID scheme

Cell IDs are deterministic, constructed by functions in `drawio_schema.py`:

| Element | ID pattern |
|---------|-----------|
| Class | `{domain}:class:{ClassName}` |
| Attribute cell | `{domain}:attr:{ClassName}:{attr_name}` |
| Separator | `{domain}:sep:{ClassName}` |
| Association | `{domain}:assoc:{Rname}` |
| Assoc label | `{domain}:assoc_mult:{Rname}:{src\|tgt}` |
| State | `{domain}:state:{ClassName}:{StateName}` |
| Transition | `{domain}:trans:{ClassName}:{from}:{event}:{idx}` |

The domain portion is always lowercased. IDs are used as the primary key by `_drawio_to_canonical_*` and `sync_from_drawio` to identify elements without relying on label text.

### Validation

`validate_drawio` iterates all `mxCell` elements and checks each `style` attribute against the set of values in `BIJECTION_TABLE`. The check is tolerant of:
- A trailing semicolon on an otherwise valid style
- Port tokens appended to an edge style (`exitX=...;exitY=...;entryX=...;entryY=...`)
- Dynamic alignment properties appended to label styles (`align=...;verticalAlign=...`)

If none of those normalization passes produce a match, the cell is flagged with an `error`-severity issue. The cell IDs `"0"` and `"1"` (the two mandatory container cells in every Draw.io file) are always skipped.

Validation never raises; it returns an empty list for a fully valid file.

---

## 6. Geometry

### Layout pipeline

For both diagram types, the layout pipeline follows the same sequence:

```
1. Build vertex + edge lists
2. Run graph layout (igraph) → raw (x, y) per vertex
3. Scale so closest pair of centers is >= min_dist apart
4. Iterative overlap removal (SAT min-axis push)
5. Optimize edge routing (port selection + waypoints)
```

For class diagrams, igraph's Kamada-Kawai force-directed layout is used. For state diagrams, also Kamada-Kawai with per-edge weights proportional to the combined box sizes, so large state boxes are placed further apart.

Node dimensions are computed from content: state width from the longest text line (`_state_width`), state height from entry-action line count (`_state_height`), class width from the longest attribute/method label (`_estimate_class_width`).

### Edge routing: Liang-Barsky slab test

After layout, edges are routed around intervening boxes. The key sub-problem is: does the straight line from anchor A to anchor B pass through box k?

This is answered with the Liang-Barsky parametric line-AABB intersection test (`_route_edges_around_boxes`, `_route_path`). The segment is parameterized as `P(t) = A + t*(B-A)`, and each axis-aligned slab of box k gives one constraint on `t`. If the surviving `[t_min, t_max]` interval is non-empty, the segment intersects the box.

**Intent:** find the first blocking box so a single perpendicular detour waypoint can be inserted to route around it. The waypoint is placed at the midpoint of A–B, displaced perpendicular to the edge direction by `2 * (half_extent + gap)` px, on the side away from the blocking box's center.

Only the first blocker is handled per edge. The assumption is that the overlap-removal step has already ensured boxes are well-separated, so multi-blocker chains are rare after layout.

**Key constraint solved:** without this, edges on dense diagrams would visually pass through unrelated boxes, making the diagram unreadable.

### Edge port selection

For each non-self-loop edge, `_optimize_edge_routing` tries all 16 combinations of (exit side × entry side) on the source and target boxes. Each combination is scored:

```
score = 10000 * box_crossings + 1000 * edge_crossings + path_length
```

Box crossings and edge crossings with already-routed edges are counted using the same slab test. Three iterative passes let later routing decisions inform earlier ones.

After side selection, anchors are spread along each side to avoid multiple edges landing on the same pixel (pooled spreading preserves the spatial order of endpoints to minimize crossings at the boundary).

Bidirectional pairs (A→B and B→A) get additional treatment: port fractions are nudged apart and midpoint waypoints are added so the two anti-parallel edges run as visibly separated parallel lines.

### Self-loops

Self-loops (transitions where source == target) are handled separately because igraph layout does not place them, and the general routing logic returns an empty waypoint list for them.

`_self_loop_corner` picks which of four corners (top-right, bottom-right, bottom-left, top-left) to use for a self-loop. It scores each corner by:
1. The combined count of non-self-loop edges already using that corner's two adjacent sides (lower is better)
2. The proximity of nearby boxes in that corner's outward quadrant (penalizes corners pointing toward other nodes)

Multiple self-loops on the same state cycle through the scored corner list.

`_self_loop_waypoints` computes three exterior waypoints that force four right-angle segments:
```
exit → WP1 → WP2 → WP3 → entry
```
WP1 is directly outside the exit anchor; WP3 is directly outside the entry anchor; WP2 connects them at the exterior corner. The `offset` parameter (default 40 px) controls how far outside the box the loop extends.

**Key constraint solved:** without explicit waypoints, Draw.io's orthogonal router folds self-loops back across the box interior, producing invisible or degenerate arrows.

---

## 7. Never-Raise Contract

All public functions return `list[dict]` and never raise exceptions. Errors are surfaced as issue dicts with the following structure (matching `tools/validation.py`):

```python
{
    "issue":    str,          # human-readable description
    "location": str,          # file path or "domain=X, class=Y" or "xml:cell:{id}"
    "value":    object,       # the offending value, or None
    "fix":      str | None,   # suggested remediation
    "severity": str,          # "error" | "warning" | "info"
}
```

Callers can distinguish:

| severity | meaning |
|----------|---------|
| `error` | Operation failed or partially failed; output may be incomplete |
| `warning` | Recognized problem; operation continued (e.g., unrecognized cell skipped during sync) |
| `info` | Informational; reports structural changes made during sync |

A successful render returns `[{"file": "...", "status": "written"}]` or `[{"file": "...", "status": "skipped"}]` — neither of these has a `severity` key. Callers can check `any(r.get("severity") == "error" for r in results)` to detect failures.

`sync_from_drawio` appends `validate_class` issues after writing the YAML, so its return list may contain `error`-severity issues from validation even if the sync itself succeeded.

XML parse failures return immediately with a single `error` issue. Domain-path-not-found and YAML-load failures return immediately. No partial writes occur before a fatal error.
