# Phase 2: MCP Server + model_io — Research

**Researched:** 2026-03-06
**Domain:** FastMCP Python server, MCP stdio transport, model I/O tools
**Confidence:** HIGH (core stack verified against PyPI + gofastmcp.com; API verified against official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Server transport & launch**
- Transport: stdio — standard for Claude Code/Desktop MCP integration
- Entry point: `mdf-server` → `mdf_server.server:main` in `[project.scripts]`
- MCP protocol server name: `mdf` — tools appear as `mdf/list_domains`, `mdf/read_model`, etc.
- `fastmcp` added as a runtime dependency in `[project] dependencies` (not dev-only)
- `server.py` lives at `mdf_server/server.py`; calls `mcp.run()` in `main()`
- Tools registered directly in `server.py` using `@mcp.tool` decorators — no router/sub-app pattern for Phase 2

**Module scaffold**
- `mdf_server/tools/model_io.py` — all three Phase 2 tool implementations
- Stub files created for future phases (docstring-only + phase reference comment):
  - `mdf_server/tools/drawio.py` — Phase 4
  - `mdf_server/tools/validation.py` — Phase 3
  - `mdf_server/tools/simulation.py` — Phase 5
- `mdf_server/pycca/__init__.py` — stub referencing Phase 5
- Follows the established stub pattern from Phase 1: docstring-only modules with plan reference

**list_domains() behavior**
- Source of truth: directory scan of `.design/model/` — lists any subdirectory containing `class-diagram.yaml`
- Returns a string list of domain names as-is from directory names: `["Hydraulics", "Timer"]`
- Returns `[]` when `.design/model/` does not exist (never errors)
- Domain name = id = label — no separate id/label fields needed

**read_model(domain) behavior**
- Returns the raw YAML string from `class-diagram.yaml` — no round-trip through Pydantic on read
- On success: returns file content as string
- On domain not found: returns `{"error": "Domain 'X' not found", "available": ["Hydraulics", "Timer"]}`
- Scope: `class-diagram.yaml` only — state diagrams are a separate future tool not in Phase 2

**write_model(domain, yaml) behavior**
- Writes `class-diagram.yaml` only — mirrors `read_model` scope
- Validate-before-write: parse YAML, validate against Pydantic schema; only write to disk if valid
- Auto-creates `.design/model/<domain>/` directory if it does not exist
- Returns `[]` (empty list) on success — consistent return type throughout
- Does not touch `DOMAINS.yaml` — managed by a future skill/agent

**Domain name casing & lookup**
- Directory names are title-case: `.design/model/Hydraulics/`, `.design/model/Timer/`
- `write_model` creates directories in title-case matching the `domain` parameter
- Lookup is case-insensitive: `read_model("hydraulics")` finds `Hydraulics/`
- `list_domains()` returns directory names as-is from the filesystem

**Model path**
- `.design/model/` is hardcoded relative to CWD — server is always launched from project root by Claude Code

**Issue list format**
- All tool error returns use: `{"issue": str, "location": str, "value": any}`
- YAML parse errors returned as: `{"issue": "YAML parse error: <msg>", "location": "line N", "value": <offending text>}`
- Tool functions never throw — all errors are returned as structured data

**Tool docstrings**
- Each tool has a full contract docstring: parameters, return value, error behavior
- Docstrings include usage guidance for Claude — sequencing hints
- FastMCP exposes docstrings to Claude as tool descriptions

**Tests**
- `tests/test_model_io.py` created in Phase 2 alongside implementation
- 7 minimum test cases covering all tool behaviors (see CONTEXT.md for full list)

### Claude's Discretion
- Exact FastMCP API usage (version-specific decorator syntax, `mcp.run()` invocation) — researcher will verify against gofastmcp.com docs
- Internal path resolution helpers
- Test fixture structure (tmp_path usage, YAML fixture strings)
- Exact `main()` function body

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within Phase 2 scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-00 | MCP server package scaffolded — `mdf-server/` with `pyproject.toml`, `server.py`, module structure (`tools/`, `schema/`, `pycca/`) | FastMCP 3.1.0 constructor and `[project.scripts]` entry point pattern documented below |
| MCP-01 | `list_domains()` — returns all domain names in `.design/model/` | `pathlib.Path.iterdir()` pattern; directory-scan logic documented below |
| MCP-02 | `read_model(domain)` — returns YAML for one domain; error if not found lists available domains | Raw file read pattern; case-insensitive lookup via `lower()` comparison documented below |
| MCP-03 | `write_model(domain, yaml)` — saves, validates against schema, returns issue list; idempotent | Pydantic v2 ValidationError → issue list extraction pattern documented below |
</phase_requirements>

---

## Summary

Phase 2 scaffolds the `mdf-server` Python package and implements three model I/O tools using FastMCP 3.1.0. The core library is stable, well-documented, and the API is simple: `FastMCP("name")` instantiation, `@mcp.tool` decorator registration, and `mcp.run()` invocation for stdio transport. No breaking API changes are expected between 3.0 and 3.1.

The three tools (`list_domains`, `read_model`, `write_model`) are pure filesystem + Pydantic operations with no network I/O. The existing `yaml_schema.py` from Phase 1 provides all validation models. The only non-trivial implementation concern is converting `pydantic.ValidationError` into the project's `{"issue", "location", "value"}` format — the error structure is well-defined and extractable from `ValidationError.errors()`.

**Primary recommendation:** Use FastMCP 3.1.0 with `@mcp.tool` (no parentheses on the decorator), `mcp.run()` (default stdio), and extract Pydantic errors via `e.errors()` iterating `loc` + `msg` + `input` fields.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastmcp | >=3.1.0 | MCP server framework, tool registration, stdio transport | Official Python MCP framework; 70% of MCP servers use it; maintained by PrefectHQ |
| pydantic | >=2.12.5 | YAML schema validation (already in pyproject.toml) | Already installed; `yaml_schema.py` built on it |
| pyyaml | >=6.0.3 | YAML parsing (already in pyproject.toml) | Already installed; standard Python YAML library |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | Directory scanning, path construction | All file system operations in model_io.py |
| pytest | >=9.0.2 | Test runner (already in dev deps) | `test_model_io.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fastmcp | mcp (official SDK) | fastmcp is a higher-level wrapper; official SDK requires more boilerplate; context decision locked fastmcp |
| pyyaml | ruamel-yaml | ruamel-yaml (also installed) preserves comments/ordering but adds complexity; pyyaml is sufficient for parse-then-validate |

**Installation:**
```bash
uv add fastmcp
# or: add "fastmcp>=3.1.0" to [project] dependencies in pyproject.toml
```

---

## Architecture Patterns

### Recommended Project Structure

```
mdf-server/
├── mdf_server/
│   ├── __init__.py
│   ├── server.py              # FastMCP instance + @mcp.tool registrations
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── model_io.py        # list_domains, read_model, write_model
│   │   ├── drawio.py          # stub — Phase 4
│   │   ├── validation.py      # stub — Phase 3
│   │   └── simulation.py      # stub — Phase 5
│   ├── pycca/
│   │   └── __init__.py        # stub — Phase 5
│   └── schema/
│       ├── __init__.py
│       ├── yaml_schema.py     # already exists (Phase 1)
│       └── drawio_schema.py   # already exists (Phase 1)
├── tests/
│   ├── __init__.py
│   ├── test_model_io.py       # Phase 2 tests (new)
│   ├── test_yaml_schema.py    # already exists
│   ├── test_drawio_schema.py  # already exists
│   ├── test_roundtrip.py      # already exists
│   └── test_templates.py      # already exists
└── pyproject.toml
```

### Pattern 1: FastMCP Server Instantiation and Entry Point

**What:** Create the MCP server object at module level, register tools with `@mcp.tool`, call `mcp.run()` inside `main()`.

**When to use:** All FastMCP servers using stdio transport with a named entry point.

**Example:**
```python
# Source: https://gofastmcp.com/getting-started/quickstart (verified 2026-03-06)
from fastmcp import FastMCP
from mdf_server.tools.model_io import list_domains, read_model, write_model

mcp = FastMCP("mdf")

mcp.tool(list_domains)
mcp.tool(read_model)
mcp.tool(write_model)

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()
```

**Alternative decorator form (also valid):**
```python
@mcp.tool
def my_tool(x: str) -> str:
    """Tool docstring exposed to Claude."""
    return x
```

**Note:** The `@mcp.tool` decorator works with no parentheses. If tools are defined in a separate module (`model_io.py`), use `mcp.tool(function_ref)` in `server.py` to register them after import — this avoids circular import issues and keeps `model_io.py` free of FastMCP imports.

**pyproject.toml entry point:**
```toml
[project.scripts]
mdf-server = "mdf_server.server:main"
```

This registers the `mdf-server` shell command. After `pip install -e .`, running `mdf-server` calls `main()` which calls `mcp.run()` with default stdio transport.

### Pattern 2: Directory-Scan for list_domains()

**What:** Scan `.design/model/` for subdirectories containing `class-diagram.yaml`.

**When to use:** Whenever the domain list must reflect actual filesystem state.

**Example:**
```python
# Source: stdlib pathlib — confirmed pattern
from pathlib import Path

MODEL_ROOT = Path(".design/model")

def list_domains() -> list[str]:
    """
    Returns domain names from .design/model/.
    A domain is any subdirectory containing class-diagram.yaml.
    Returns [] if .design/model/ does not exist.
    Call this before read_model() to discover available domains.
    """
    if not MODEL_ROOT.exists():
        return []
    return [
        d.name
        for d in MODEL_ROOT.iterdir()
        if d.is_dir() and (d / "class-diagram.yaml").exists()
    ]
```

### Pattern 3: Case-Insensitive Domain Lookup

**What:** Find a domain directory by matching lowercased names.

**When to use:** `read_model` and `write_model` to absorb Claude's capitalization drift.

**Example:**
```python
def _resolve_domain_path(domain: str) -> Path | None:
    """Returns Path to domain directory, case-insensitive. None if not found."""
    if not MODEL_ROOT.exists():
        return None
    target = domain.lower()
    for d in MODEL_ROOT.iterdir():
        if d.is_dir() and d.name.lower() == target:
            return d
    return None
```

### Pattern 4: Pydantic ValidationError → Issue List

**What:** Convert `pydantic.ValidationError.errors()` into the project's `{"issue", "location", "value"}` format.

**When to use:** `write_model` after schema validation fails.

**Example:**
```python
# Source: Pydantic v2 docs — errors() returns list of dicts with 'loc', 'msg', 'input'
from pydantic import ValidationError

def _pydantic_errors_to_issues(e: ValidationError) -> list[dict]:
    issues = []
    for err in e.errors():
        loc_parts = [str(p) for p in err["loc"]]
        location = ".".join(loc_parts) if loc_parts else "<root>"
        issues.append({
            "issue": err["msg"],
            "location": location,
            "value": err.get("input"),
        })
    return issues
```

**Note on `err["input"]`:** In Pydantic v2, `err["input"]` is the value that failed validation at the failing field. For nested errors the input may be the parent dict — acceptable for the issue format.

### Pattern 5: write_model Validate-Before-Write

**What:** Parse YAML, validate with Pydantic, write only if both pass. Never throw.

**Example:**
```python
import yaml
from pydantic import ValidationError
from mdf_server.schema.yaml_schema import ClassDiagramFile

def write_model(domain: str, yaml_str: str) -> list[dict]:
    """
    Saves class-diagram.yaml for domain after schema validation.
    Returns [] on success. Returns issue list on any error.
    Never raises exceptions.
    """
    # Step 1: Parse YAML
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = f"line {mark.line + 1}" if mark else "unknown"
        return [{"issue": f"YAML parse error: {exc.problem}", "location": line, "value": yaml_str[:200]}]

    # Step 2: Pydantic validation
    try:
        ClassDiagramFile.model_validate(data)
    except ValidationError as e:
        return _pydantic_errors_to_issues(e)

    # Step 3: Write
    domain_dir = MODEL_ROOT / domain  # title-case from caller
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "class-diagram.yaml").write_text(yaml_str, encoding="utf-8")
    return []
```

### Anti-Patterns to Avoid

- **Raising exceptions from tools:** FastMCP does convert uncaught exceptions to MCP errors, but CONTEXT.md specifies tools must never throw — always return structured data.
- **Importing `mcp` (the FastMCP instance) in `model_io.py`:** Creates circular imports when `server.py` imports `model_io`. Keep tool functions as plain Python callables; register them in `server.py`.
- **Using `yaml.load()` without `Loader`:** Always use `yaml.safe_load()` to avoid arbitrary code execution.
- **Case-sensitive domain matching:** Do not use `MODEL_ROOT / domain` directly for lookups — only for creates in `write_model`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol framing | Custom stdio read/write loop | `fastmcp` / `mcp.run()` | Protocol has framing, content-type negotiation, JSON-RPC envelope — extremely error-prone to hand-roll |
| YAML schema validation | Custom field checkers | `ClassDiagramFile.model_validate()` (Pydantic v2) | Already built in Phase 1; handles all field rules, `model_validator` constraints, alias resolution |
| Tool schema generation | Manual JSON Schema dict | `@mcp.tool` decorator | FastMCP generates tool schema from type annotations and docstring automatically |
| YAML parsing | Custom text parser | `yaml.safe_load()` | pyyaml already installed; handles multi-line, anchors, encoding |

**Key insight:** The MCP wire protocol is non-trivial JSON-RPC over stdio with lifecycle management. FastMCP handles all of it; the tool implementations are pure Python.

---

## Common Pitfalls

### Pitfall 1: @mcp.tool Decorator Import Order

**What goes wrong:** If `model_io.py` imports from `server.py` (or vice versa), circular import at startup.

**Why it happens:** Developers put `@mcp.tool` decorators in `model_io.py` which requires importing the `mcp` instance from `server.py`.

**How to avoid:** Keep `model_io.py` as plain Python. In `server.py`: `from mdf_server.tools.model_io import list_domains, read_model, write_model`, then register with `mcp.tool(list_domains)` etc.

**Warning signs:** `ImportError: cannot import name 'mcp'` or `ImportError: circular import` at startup.

### Pitfall 2: write_model Writing Before Validation Completes

**What goes wrong:** File is partially written if an exception interrupts between write start and flush.

**Why it happens:** Opening a file for write then raising during the write body.

**How to avoid:** Validate fully in memory before opening the file for write. `Path.write_text()` is atomic enough for this use case (single call writes atomically on most OS).

**Warning signs:** Tests find a corrupt `class-diagram.yaml` after a validation failure test case.

### Pitfall 3: MODEL_ROOT Relative to Module, Not CWD

**What goes wrong:** `Path(".design/model")` resolves differently depending on where Python is invoked.

**Why it happens:** Relative paths resolve relative to process CWD, not `__file__` location.

**How to avoid:** CONTEXT.md specifies the server is always launched from project root by Claude Code. Using `Path(".design/model")` relative to CWD is the correct pattern — do NOT anchor to `__file__`.

**Warning signs:** Tests that `os.chdir()` to a tmp directory fail to find `.design/model/`.

### Pitfall 4: pyyaml YAMLError Attribute Access

**What goes wrong:** `exc.problem_mark` or `exc.problem` raises `AttributeError` for some error types.

**Why it happens:** `yaml.YAMLError` is a base class; not all subclasses set `problem_mark`.

**How to avoid:** Use `getattr(exc, "problem_mark", None)` and `getattr(exc, "problem", str(exc))` defensively.

### Pitfall 5: FastMCP Version Pinning

**What goes wrong:** Using `fastmcp>=3.0.0` allows 4.x in future which may have breaking changes.

**Why it happens:** Permissive version constraint in pyproject.toml.

**How to avoid:** Pin to `fastmcp>=3.1.0,<4.0.0` or `fastmcp~=3.1`. The gofastmcp.com installation guide explicitly recommends pinning to exact versions.

---

## Code Examples

Verified patterns from official sources:

### FastMCP Server Boilerplate (server.py)
```python
# Source: https://gofastmcp.com/getting-started/quickstart (verified 2026-03-06)
from fastmcp import FastMCP
from mdf_server.tools.model_io import list_domains, read_model, write_model

mcp = FastMCP("mdf")

mcp.tool(list_domains)
mcp.tool(read_model)
mcp.tool(write_model)


def main() -> None:
    mcp.run()  # default transport = stdio


if __name__ == "__main__":
    main()
```

### pyproject.toml Additions
```toml
[project]
dependencies = [
    "defusedxml>=0.7.1",
    "lxml>=6.0.2",
    "pydantic>=2.12.5",
    "pyyaml>=6.0.3",
    "ruamel-yaml>=0.19.1",
    "fastmcp>=3.1.0,<4.0.0",   # add this line
]

[project.scripts]
mdf-server = "mdf_server.server:main"   # add this section
```

### Test Fixture Pattern (consistent with existing tests)
```python
# Source: tests/test_yaml_schema.py inline dict pattern from Phase 1
import pytest
from pathlib import Path

VALID_CLASS_DIAGRAM_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
    attributes:
      - name: valve_id
        type: UniqueID
        identifier: true
associations: []
bridges: []
"""

def test_list_domains_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .design/model/ created
    from mdf_server.tools.model_io import list_domains
    assert list_domains() == []

def test_list_domains_with_domain(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model_dir = tmp_path / ".design" / "model" / "Hydraulics"
    model_dir.mkdir(parents=True)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    from mdf_server.tools.model_io import list_domains
    assert list_domains() == ["Hydraulics"]
```

**Note on test isolation:** Use `monkeypatch.chdir(tmp_path)` rather than `os.chdir()` — pytest's monkeypatch resets CWD after each test. This is critical because `MODEL_ROOT` is relative to CWD.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| mcp SDK directly (low-level) | fastmcp 3.x wrapper | 2024-2025 | Much less boilerplate; automatic schema gen from type hints |
| fastmcp 0.x (pre-PrefectHQ) | fastmcp 3.x (PrefectHQ fork became canonical) | Late 2024 / early 2025 | 3.x is the official maintained version; 0.x tutorials are stale |
| `@mcp.tool()` with parentheses | `@mcp.tool` without parentheses | fastmcp 2.x → 3.x | Both still work in 3.x; no-parens is the idiomatic form |

**Deprecated/outdated:**
- fastmcp 0.x / 1.x examples: The original jlowin/fastmcp repo merged into PrefectHQ. Version 3.x is the current stable line.
- SSE transport: Still supported but stdio is the standard for Claude Code/Desktop local integration.

---

## Open Questions

1. **`mcp.tool(fn)` vs `@mcp.tool` for externally-defined functions**
   - What we know: `@mcp.tool` (no parens) works on inline definitions; `mcp.tool(fn)` registration call also works per docs
   - What's unclear: Whether `mcp.tool(fn)` returns the function unmodified (important if `model_io.py` exports the plain function for testing)
   - Recommendation: Use `mcp.tool(list_domains)` in `server.py` after import; `model_io.py` functions remain plain callables. This is the safest pattern for testability.

2. **`mcp.run()` transport parameter**
   - What we know: Default transport is stdio. `mcp.run(transport="stdio")` also valid.
   - What's unclear: Whether omitting the transport parameter is guaranteed to default to stdio in all 3.x minor versions.
   - Recommendation: Call `mcp.run()` without arguments (stdio is the documented default). Acceptable given locked decision; can add explicit `transport="stdio"` as defensive measure.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2+ |
| Config file | `mdf-server/pyproject.toml` → `[tool.pytest.ini_options] testpaths = ["tests"]` |
| Quick run command | `cd mdf-server && uv run pytest tests/test_model_io.py -x` |
| Full suite command | `cd mdf-server && uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-00 | `pip install -e ./mdf-server` succeeds; `mdf-server` entry point exists | smoke | `cd mdf-server && uv run python -c "import mdf_server.server"` | ❌ Wave 0 |
| MCP-00 | Server module structure exists (tools/, pycca/ stubs) | unit | `pytest tests/test_model_io.py::test_imports -x` | ❌ Wave 0 |
| MCP-01 | `list_domains()` returns `[]` when `.design/model/` absent | unit | `pytest tests/test_model_io.py::test_list_domains_empty -x` | ❌ Wave 0 |
| MCP-01 | `list_domains()` returns domain names from filesystem | unit | `pytest tests/test_model_io.py::test_list_domains_with_domains -x` | ❌ Wave 0 |
| MCP-02 | `read_model()` returns YAML string for known domain | unit | `pytest tests/test_model_io.py::test_read_model_known -x` | ❌ Wave 0 |
| MCP-02 | `read_model()` returns error dict for unknown domain | unit | `pytest tests/test_model_io.py::test_read_model_unknown -x` | ❌ Wave 0 |
| MCP-03 | `write_model()` writes valid YAML and returns `[]` | unit | `pytest tests/test_model_io.py::test_write_model_valid -x` | ❌ Wave 0 |
| MCP-03 | `write_model()` returns parse error for invalid YAML syntax | unit | `pytest tests/test_model_io.py::test_write_model_bad_yaml -x` | ❌ Wave 0 |
| MCP-03 | `write_model()` returns issue list for schema-invalid YAML | unit | `pytest tests/test_model_io.py::test_write_model_schema_invalid -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd mdf-server && uv run pytest tests/test_model_io.py -x`
- **Per wave merge:** `cd mdf-server && uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `mdf-server/tests/test_model_io.py` — covers MCP-00 through MCP-03 (all 9 cases above)
- [ ] `mdf-server/mdf_server/server.py` — FastMCP instance + tool registration
- [ ] `mdf-server/mdf_server/tools/__init__.py` — package init
- [ ] `mdf-server/mdf_server/tools/model_io.py` — three tool implementations
- [ ] `mdf-server/mdf_server/tools/drawio.py` — stub
- [ ] `mdf-server/mdf_server/tools/validation.py` — stub
- [ ] `mdf-server/mdf_server/tools/simulation.py` — stub
- [ ] `mdf-server/mdf_server/pycca/__init__.py` — stub
- [ ] pyproject.toml update: add `fastmcp` to dependencies + `[project.scripts]` entry

---

## Sources

### Primary (HIGH confidence)
- https://gofastmcp.com/getting-started/quickstart — FastMCP server instantiation, `@mcp.tool` decorator, `mcp.run()` pattern
- https://gofastmcp.com/servers/tools — Full tool definition API: decorator options, parameter annotations, return types, error handling
- https://gofastmcp.com/getting-started/installation — Version pinning guidance, `uv add fastmcp`
- https://pypi.org/project/fastmcp/ — Latest version confirmed as 3.1.0 (released 2026-03-03); Python >=3.10 required
- Pydantic v2 docs (`ValidationError.errors()`) — error structure is `{"loc", "msg", "input", "type", ...}`

### Secondary (MEDIUM confidence)
- https://mcpcat.io/guides/building-mcp-server-python-fastmcp/ — `mcp.run(transport="stdio")` explicit form verified; default is stdio
- Phase 1 existing code (`yaml_schema.py`, `tests/test_yaml_schema.py`) — established patterns for Pydantic models and inline YAML fixture dicts; directly reusable

### Tertiary (LOW confidence)
- None — all critical claims verified with primary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — FastMCP 3.1.0 verified on PyPI (2026-03-03 release); API verified on gofastmcp.com
- Architecture: HIGH — patterns derived directly from official docs + Phase 1 established conventions
- Pitfalls: MEDIUM — circular import and CWD pitfalls are standard Python; YAML error attributes are pyyaml-specific (verified from stdlib pattern knowledge, not separately fetched)
- Test patterns: HIGH — `monkeypatch.chdir` is documented pytest stdlib; existing Phase 1 tests confirm inline fixture approach

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (FastMCP 3.x is in active development; re-verify if >30 days pass)
