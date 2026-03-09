# Phase 2: MCP Server + model_io - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Scaffold the FastMCP server package and implement the three foundational model I/O tools: `list_domains()`, `read_model(domain)`, `write_model(domain, yaml)`. The server must be installable, connectable via MCP protocol, and the three tools must be functional. Validation (Phase 3), Draw.io tools (Phase 4), simulation (Phase 5), and the full test suite (Phase 6) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Server transport & launch
- Transport: **stdio** — standard for Claude Code/Desktop MCP integration
- Entry point: `mdf-server` → `mdf_server.server:main` in `[project.scripts]`
- MCP protocol server name: **`mdf`** — tools appear as `mdf/list_domains`, `mdf/read_model`, etc.
- `fastmcp` added as a **runtime dependency** in `[project] dependencies` (not dev-only)
- `server.py` lives at `mdf_server/server.py`; calls `mcp.run()` in `main()`
- Tools registered directly in `server.py` using `@mcp.tool` decorators — no router/sub-app pattern for Phase 2

### Module scaffold
- `mdf_server/tools/model_io.py` — all three Phase 2 tool implementations
- Stub files created for future phases (docstring-only + phase reference comment):
  - `mdf_server/tools/drawio.py` — Phase 4
  - `mdf_server/tools/validation.py` — Phase 3
  - `mdf_server/tools/simulation.py` — Phase 5
- `mdf_server/pycca/__init__.py` — stub referencing Phase 5
- Follows the established stub pattern from Phase 1: docstring-only modules with plan reference

### list_domains() behavior
- Source of truth: **directory scan** of `.design/model/` — lists any subdirectory containing `class-diagram.yaml`
- Returns a **string list** of domain names as-is from directory names: `["Hydraulics", "Timer"]`
- Returns `[]` when `.design/model/` does not exist (never errors)
- Domain name = id = label — no separate id/label fields needed

### read_model(domain) behavior
- Returns the **raw YAML string** from `class-diagram.yaml` — no round-trip through Pydantic on read
- On success: returns file content as string
- On domain not found: returns `{"error": "Domain 'X' not found", "available": ["Hydraulics", "Timer"]}`
- Scope: `class-diagram.yaml` only — state diagrams (`state-diagrams/<ClassName>.yaml`) are a separate future tool not in Phase 2

### write_model(domain, yaml) behavior
- Writes **`class-diagram.yaml` only** — mirrors `read_model` scope
- **Validate-before-write**: parse YAML, validate against Pydantic schema; only write to disk if valid
- **Auto-creates** `.design/model/<domain>/` directory if it does not exist
- Returns **`[]`** (empty list) on success — consistent return type throughout
- Does **not** touch `DOMAINS.yaml` — that file is managed by a future skill/agent

### Domain name casing & lookup
- Directory names are **title-case**: `.design/model/Hydraulics/`, `.design/model/Timer/`
- `write_model` creates directories in title-case matching the `domain` parameter
- Lookup is **case-insensitive**: `read_model("hydraulics")` finds `Hydraulics/`
- `list_domains()` returns directory names as-is from the filesystem

### Model path
- `.design/model/` is **hardcoded relative to CWD** — server is always launched from project root by Claude Code

### Issue list format
- All tool error returns use: `{"issue": str, "location": str, "value": any}`
  - `issue` — human-readable error message
  - `location` — field path (e.g., `"classes[1].stereotype"`) or resource path (e.g., `"Hydraulics::class-diagram.yaml"`)
  - `value` — the rejected value
- YAML parse errors are caught before Pydantic validation and returned as: `{"issue": "YAML parse error: <msg>", "location": "line N", "value": <offending text>}`
- Tool functions **never throw** — all errors are returned as structured data
- Note for Phase 3: `validate_model` will use `{"issue", "location", "value", "fix"}` — the `fix` field is added only for graph/semantic errors where a remediation hint is computable (e.g., unreachable states, trap states). Schema errors from `write_model` do not need a fix hint.

### Tool docstrings
- Each tool has a **full contract docstring**: parameters, return value, error behavior
- Docstrings include **usage guidance for Claude** — sequencing hints like "call `list_domains()` to discover available domains before calling `read_model()`"
- FastMCP exposes docstrings to Claude as tool descriptions — these are the primary mechanism for Claude to understand correct tool use

### Tests
- `tests/test_model_io.py` created in Phase 2 alongside implementation
- Minimum test coverage:
  - `list_domains()` with no `.design/model/` directory → returns `[]`
  - `list_domains()` with one or more domain directories → returns names
  - `read_model()` with known domain → returns YAML string
  - `read_model()` with unknown domain → returns error + available list
  - `write_model()` with valid YAML → writes file, returns `[]`
  - `write_model()` with invalid YAML syntax → returns parse error issue, no file written
  - `write_model()` with schema-invalid YAML → returns Pydantic issue list, no file written

### Claude's Discretion
- Exact FastMCP API usage (version-specific decorator syntax, `mcp.run()` invocation) — researcher will verify against gofastmcp.com docs
- Internal path resolution helpers
- Test fixture structure (tmp_path usage, YAML fixture strings)
- Exact `main()` function body

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `mdf_server/schema/yaml_schema.py` — full Pydantic v2 models for all YAML file types; `write_model` validation runs the incoming YAML through these models
- `mdf_server/schema/drawio_schema.py` — canonical bijection table; not used in Phase 2 but present

### Established Patterns
- Flat uv layout: `mdf_server/` directly under `mdf-server/`, uv auto-discovers without explicit packages declaration
- `populate_by_name=True` on all Pydantic models — allows both Python field names and YAML key names
- Stub pattern: docstring-only modules with plan reference comment + `@pytest.mark.skip(reason='Implemented in plan NN')` for future tests
- `pyproject.toml` dev group has: mypy, pytest, ruff — add fastmcp to main `dependencies`

### Integration Points
- `yaml_schema.py` Pydantic models consumed directly by `write_model` for validation
- `tools/model_io.py` imported by `server.py` for tool registration
- `.design/model/` directory is the live model store — created on first `write_model` call if absent
- Phase 1 test suite lives in `tests/` — `test_model_io.py` follows same structure

</code_context>

<specifics>
## Specific Ideas

- The MCP server name `mdf` keeps tool names short in Claude's tool list: `mdf/list_domains`, `mdf/read_model`, `mdf/write_model`
- Case-insensitive domain lookup makes Claude resilient to capitalization drift without requiring exact-match calls
- `list_domains()` returns `[]` not an error when `.design/model/` is absent — natural state for a new project before any domains are written

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within Phase 2 scope.

</deferred>

---

*Phase: 02-mcp-server-model-io*
*Context gathered: 2026-03-06*
