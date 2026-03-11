# Phase 4: Draw.io Tools - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement three MCP tools — `render_to_drawio`, `validate_drawio`, and `sync_from_drawio` — that translate between YAML model files and Draw.io XML using the already-locked canonical bijection schema. The bijection constants and ID generators (in `schema/drawio_schema.py`) are fixed inputs to this phase, not outputs. Simulation (Phase 5), CLI harness (Phase 6), and GUI debugger (Phase 7) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### MCP tool surface

Three top-level MCP tools, all registered:

- `render_to_drawio(domain)` — generates all diagrams for a domain in one call; internally calls the two helpers below
- `render_to_drawio_class(domain)` — generates `class-diagram.drawio` only
- `render_to_drawio_state(domain, class_name)` — generates `state-diagrams/<ClassName>.drawio` only

`validate_drawio(domain, xml)` and `sync_from_drawio(domain, xml)` remain as originally specified (take XML as a string parameter per MCP-06 / MCP-07).

### render_to_drawio output behavior

- Writes `.drawio` files to disk, parallel to YAML files:
  - `.design/model/<domain>/class-diagram.drawio`
  - `.design/model/<domain>/state-diagrams/<ClassName>.drawio` (one per active class)
- **Skip-if-unchanged**: before overwriting, compare the existing `.drawio` model structure against the YAML. If structure matches (same elements, same topology), skip the rewrite and preserve engineer-adjusted layout positions.
- If YAML has changed (elements added/removed/renamed), regenerate and overwrite.
- Returns a structured result list:
  - Per-file entry with `file` and `status` (`"written"` or `"skipped"`)
  - Plus any error issues using the standard issue dict format (`issue`, `location`, `value`, `fix`, `severity`)

### Layout algorithm

- Use **`python-igraph`** (pure pip install, no system dependencies) for all layout.
- Apply **Sugiyama layered layout** (`layout_sugiyama()`) for both class diagrams and state diagrams — minimizes edge crossings.
- Pre-compute bounding boxes from YAML before layout:
  - Class height: `HEADER_H(26) + num_attrs × ROW_H(20) + SEP_H(8) + num_methods × ROW_H(20)`
  - Class width: fixed 220px (or estimated from longest label — Claude's discretion)
  - State size: fixed 160×50px (or scaled to label length — Claude's discretion)
- Scale igraph normalized positions to pixel canvas using bounding boxes.
- Run a nudge pass after scaling to resolve any remaining overlaps.
- Layout is only computed for first-time render (no existing `.drawio`) or when structure has changed. Existing `.drawio` positions are preserved on skip.
- Subtype partition layout is not a priority — Claude's discretion.

### sync_from_drawio writable scope

Topology + labels are written back to YAML. Pycca action bodies are YAML-only and are never represented in or extracted from Draw.io cells.

**What syncs back:**
- Add state/transition/class/association (from new cells in Draw.io)
- Remove state/transition/class/association (cells deleted in Draw.io)
- Rename: state names, class names, event labels on transition edges, association names

**What does NOT sync back:**
- `entry` / `exit` action bodies (pycca)
- `guard` expressions (pycca)
- `action` bodies on transitions (pycca)
- Attribute types, method signatures, bridge implementations
- Cell positions, sizes, styling (cosmetic — ignored)

**New elements from Draw.io** get null placeholders for all YAML-only fields:
```yaml
# New state from Draw.io
name: Opening
entry: null
exit: null

# New transition from Draw.io
event: Open
guard: null
action: null
to: Opening
```

**Unrecognized cells** (style not in BIJECTION_TABLE, malformed label): skip + add to issue list. Do not abort the sync.

### sync_from_drawio merge strategy

- **Merge, not overwrite.** Existing YAML-only fields (pycca bodies, guards, attribute types, method signatures) on matched elements are preserved.
- **Match key**: canonical cell ID (e.g., `hydraulics:state:Valve:Opening`). Elements are matched by ID across YAML and Draw.io.
- **New Draw.io cells** (no matching canonical ID): treated as new YAML elements with null placeholders. On the next `render_to_drawio` call, they receive canonical IDs.
- **Deleted elements**: removed from YAML. Each deletion produces an `info`-severity entry in the returned issue list so the engineer can see what pycca bodies were lost.
- After merge, `validate_model` is run automatically and its issues are appended to the returned list (per MCP-07 spec).

</decisions>

<specifics>
## Specific Ideas

- The skip-if-unchanged check is the key UX feature: engineers lay out their diagrams once in Draw.io and don't lose that work when they edit YAML.
- The three-tool split (`render_to_drawio` / `render_to_drawio_class` / `render_to_drawio_state`) gives Claude fine-grained control — e.g., regenerate just one state diagram after adding a transition without touching the class diagram layout.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets

- `schema/drawio_schema.py`: All bijection constants (`STYLE_*`), `BIJECTION_TABLE`, and ID generator functions (`class_id`, `state_id`, `transition_id`, etc.) — the canonical inputs to all three tools. Do not modify these in Phase 4.
- `render_sample_xml()` in `schema/drawio_schema.py`: Reference implementation for XML generation using `lxml.etree`. Shows the full swimlane structure, separator cell, geometry encoding, and label formatting (HTML `<br>` for multi-line). Phase 4 generalizes this pattern.
- `tools/validation.py`: Issue list format and `validate_model()` — `sync_from_drawio` calls this automatically after merge.
- NetworkX already installed (Phase 3 dependency) — available if needed alongside igraph.

### Established Patterns

- **Stub module**: `tools/drawio.py` is currently a docstring-only stub. Phase 4 implements it.
- **Issue list return**: All tools return `list[dict]` with `issue`, `location`, `value`, `fix`, `severity` — match this for any error returns from render/sync.
- **No exceptions**: Tools never raise — errors go in the issue list.
- **MODEL_ROOT anchored to CWD** (from Phase 2): `.design/model/` is relative to `os.getcwd()`. Drawio file paths follow the same convention.
- **lxml for XML**: already used in `render_sample_xml`. Use `lxml.etree` for both generation and parsing.
- **compressed=false** on `mxfile` element: mandatory — prevents base64/zlib encoding on Draw.io save.

### Integration Points

- `tools/drawio.py` — implement all three MCP functions here
- `server.py` — register `render_to_drawio`, `render_to_drawio_class`, `render_to_drawio_state`, `validate_drawio`, `sync_from_drawio` with `@mcp.tool()`
- `schema/drawio_schema.py` — read-only input; ID functions and style constants consumed by all three tools
- `tools/validation.py` — `sync_from_drawio` calls `validate_model()` (or `validate_domain()`) after writing YAML

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-draw-io-tools*
*Context gathered: 2026-03-11*
