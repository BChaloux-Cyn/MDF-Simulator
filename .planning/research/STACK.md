# Stack Research

**Domain:** MCP server + YAML model tooling + xUML/Shlaer-Mellor methodology framework
**Researched:** 2026-03-05
**Confidence:** HIGH (versions verified from PyPI index; rationale from training knowledge + project context)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13 | Runtime for all MCP server and tooling | Already installed on dev machine; 3.13 is current stable; asyncio improvements benefit MCP's async tool handlers |
| FastMCP | 3.1.0 | MCP server framework | The de facto Python MCP server library; wraps the low-level `mcp` SDK with decorators, type coercion, and stdio/SSE transport; v3.x moved to a stable public API after the 2.x rapid iteration phase |
| mcp | 1.26.0 | Underlying MCP protocol SDK (FastMCP dependency) | Anthropic's official Python MCP SDK; FastMCP depends on it — do not use directly; listed here for version pinning |
| PyYAML | 6.0.3 | YAML read/write for model files | Standard library for YAML in Python; already installed; fast C extension path via LibYAML; safe_load/safe_dump for untrusted input |
| Pydantic | 2.12.5 | Model schema definition and runtime validation | Already installed; v2 is dramatically faster than v1 (Rust core); define YAML model schema as Pydantic models — load YAML, validate with Pydantic, get structured Python objects; better than JSON Schema alone because errors include field paths and types |
| lxml | 6.0.2 | Draw.io XML generation and parsing | Already installed; fastest XML library in Python (C extension); full XPath/XSLT support; use `lxml.etree` directly for generating canonical Draw.io XML — not BeautifulSoup, not stdlib `xml.etree` |
| NetworkX | 3.6.1 | Graph algorithms for state machine reachability | Standard Python graph library; provides BFS, DFS, strongly connected components, unreachable node detection out of the box; use `DiGraph` for state machines (directed); reachability check is `nx.ancestors()` or `nx.is_weakly_connected()` |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ruamel.yaml | 0.19.1 | Round-trip YAML with comment preservation | When YAML files are human-edited and comment preservation matters during write-back; more capable than PyYAML for model files that engineers edit directly; use instead of PyYAML for write operations if comments will be present |
| jsonschema | 4.26.0 | JSON Schema validation for YAML model files | Draft 2020-12 support; use for validating YAML model structure against a machine-readable schema document (complement to Pydantic, not replacement) — enables schema publication and external tooling integration |
| lark | 1.3.1 | Parsing pycca action language embedded in YAML | EBNF grammar → parser generator; cleaner than PLY for this use case; Earley or LALR(1) parsers; pycca is Tcl-based so the grammar is relatively simple (commands, assignments, signal sends, conditionals); use for simulation interpreter |
| defusedxml | 0.7.1 | Safe XML parsing for Draw.io files ingested from disk | Already installed; wraps stdlib and lxml XML parsers to prevent XXE, billion-laughs, and other XML attacks; use when parsing Draw.io files provided by the user via `sync_from_drawio` |
| pytest | 9.0.2 | Test framework for MCP server and schema tooling | Standard Python test framework; use for unit tests on schema validation, graph reachability logic, pycca parsing, and Draw.io generation |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | 0.10.8 (already installed) | Package management and virtual environments | Use `uv init` for project, `uv add` for dependencies, `uv run` for scripts; replaces pip + venv; lockfile via `uv.lock` |
| ruff | 0.15.4 | Linting and formatting | Already on system; replaces flake8 + black + isort; configure in `pyproject.toml` with `[tool.ruff]`; zero config to start |
| mypy | 1.19.1 | Static type checking | Pair with Pydantic v2 — Pydantic generates mypy stubs; configure `mypy.ini` or `pyproject.toml`; strict mode recommended for MCP server code |

---

## Installation

```bash
# Initialize project with uv
uv init mdf-server
cd mdf-server

# Core runtime dependencies
uv add fastmcp pyyaml "ruamel.yaml" pydantic lxml networkx defusedxml

# Parsing
uv add lark

# Validation
uv add jsonschema

# Development dependencies
uv add --dev pytest ruff mypy
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastMCP 3.1.0 | Raw `mcp` SDK (1.26.0) | Never — FastMCP is purpose-built for building servers; the raw SDK is for protocol-level work or custom transport needs |
| Pydantic v2 | marshmallow, attrs, dataclasses | If Python 3.13 type annotations are insufficient; but Pydantic v2 handles nested models, optional fields, and custom validators better than alternatives for this use case |
| lark | PLY 3.11, ANTLR4 4.13.2, TatSu 5.17.1 | PLY is adequate if grammar is simple and team knows LEX/YACC; ANTLR4 is better for complex grammars with tooling needs; for pycca specifically, lark's EBNF syntax is most readable for a small grammar |
| lxml | stdlib `xml.etree.ElementTree` | stdlib is fine for simple read operations; lxml is required when generating large Draw.io XML with namespace handling, or when XPath queries on the generated graph are needed |
| NetworkX | igraph, graph-tool | igraph is faster for very large graphs (millions of nodes); for state machine graphs (typically <100 nodes), NetworkX's API clarity wins; graph-tool requires system package install, not pip |
| ruamel.yaml | PyYAML only | PyYAML is fine if YAML files are only machine-written; ruamel.yaml becomes necessary when the model files contain human-written comments that must survive a read-modify-write cycle |
| jsonschema | yamale 6.1.0 | yamale is simpler for basic structural validation; jsonschema provides Draft 2020-12 compliance and error paths that integrate with Pydantic; prefer jsonschema for publishable schema documents |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `xml.etree.ElementTree` (stdlib) for Draw.io generation | No namespace-aware attribute handling; whitespace behavior differs from Draw.io's expected format; no XPath; slower | lxml.etree |
| Pydantic v1 | Dead path — v2 is the active release; v1 compatibility shim exists but adds overhead; no reason to start new code on v1 | pydantic 2.x |
| `drawio-python` (PyPI) | Only one version (0.1.0), abandoned, no activity — not a maintained library | Hand-generate Draw.io XML with lxml using the canonical schema defined in this project |
| PLY for pycca parsing | Older LEX/YACC Python binding; requires separate lexer and parser files; less readable grammar; lark's EBNF approach handles pycca's command syntax more naturally | lark |
| TatSu for pycca parsing | More powerful than needed; PEG grammar, not EBNF; steeper learning curve for a small grammar | lark |
| FastAPI as MCP transport | MCP servers communicate over stdio with Claude Code, not HTTP; FastAPI solves a different problem; FastMCP handles the stdio transport | FastMCP |
| Any existing xUML/Shlaer-Mellor Python tooling (modelint, etc.) | Leon Starr's modelint tools are for a different workflow (Tcl-based, Micca-targeted); they use a different model representation format incompatible with this project's YAML schema; pycca compiler at repos.modelrealization.com is a separate C tool invoked via subprocess, not a Python library | Write schemas from scratch; invoke pycca compiler as subprocess |

---

## Stack Patterns by Component

**MCP Server tools (CRUD, validation, simulation):**
- FastMCP `@mcp.tool()` decorator on each of the 8 tools
- Pydantic models for input validation and return types
- PyYAML for reading model files; ruamel.yaml for write-back
- Tools are stateless: each call reads from disk, operates, writes to disk
- No in-memory state between tool calls — this keeps the server simple and crash-safe

**YAML model schema:**
- Pydantic models are the schema: `DomainModel`, `ClassDef`, `Association`, `StateMachine`, `State`, `Transition`, `DomainBridge`
- `model_validate()` called on load; `model_dump()` for round-trip back to YAML
- jsonschema for generating a machine-readable schema file (`.design/model/schema.json`) for tooling integration

**Draw.io XML generation (`render_to_drawio`):**
- lxml.etree builds the XML tree programmatically
- Canonical schema: each YAML construct maps to a fixed Draw.io cell type/style
- Output is deterministic: same YAML always produces same XML (enables diff)
- defusedxml wraps parse on ingest (`sync_from_drawio`)

**State machine graph reachability (`validate_model`):**
- Load state machine from Pydantic model → build `nx.DiGraph`
- Nodes: states (including `[*]` entry/exit pseudostates)
- Edges: transitions
- Check: every state reachable from entry state (BFS via `nx.descendants()`)
- Check: no transitions to undefined states
- Returns list of issues, not pass/fail

**pycca action language simulation (`simulate_state_machine`):**
- lark grammar defines pycca command syntax (signal sends, assignments, conditionals, bridge calls)
- Interpreter walks AST, tracks object instances and their current state
- Event sequence drives transitions; execution trace is the output
- Simulation does not invoke the real pycca compiler — it's an interpreter over the AST

**pycca compiler invocation (code generation, Phase 2+):**
- The real pycca compiler (from repos.modelrealization.com) is a separate C binary
- Invoke via `subprocess.run(["pycca", ...])` — no Python binding needed
- Simulator (above) is distinct from code generation — it's for behavioral verification only

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|----------------|-------|
| fastmcp 3.1.0 | mcp 1.26.0 | FastMCP 3.x depends on mcp 1.x; pin both in lockfile |
| pydantic 2.12.5 | Python 3.13 | Full support; pydantic-core Rust extension compiles for 3.13 |
| lxml 6.0.2 | Python 3.13 | Binary wheels available for 3.13 on Windows; no compile needed |
| networkx 3.6.1 | Python 3.13 | Pure Python; no compatibility concerns |
| lark 1.3.1 | Python 3.13 | Pure Python; no compatibility concerns |
| ruamel.yaml 0.19.1 | Python 3.13 | C extension optional; pure Python fallback works |

---

## xUML/Shlaer-Mellor Ecosystem Assessment

**Finding: No usable Python library exists for this methodology.**

Leon Starr's `modelint` GitHub (https://github.com/modelint) contains Tcl-based tooling targeting the Micca compiler, not pycca, and uses a proprietary model representation incompatible with the YAML schema being defined here. The pycca compiler (http://repos.modelrealization.com) is a C binary — useful as a code generation target (invoked via subprocess) but not as a Python library.

**Implication:** The YAML schema, Pydantic models, and lark grammar for pycca are all original work. There is no existing library to build on. This is expected and acceptable — the schema is the core artifact of Milestone 1.

**Confidence:** MEDIUM — modelint assessed from training knowledge; could not verify current state of repos without WebFetch access. Risk: low — even if modelint has Python tooling, the schema mismatch means building from scratch is correct regardless.

---

## Sources

- PyPI index queries (pip index versions) — version numbers for all libraries: HIGH confidence
- Training knowledge — FastMCP API, NetworkX graph algorithms, lxml XML generation, Pydantic v2 model architecture: MEDIUM confidence (training cutoff August 2025; FastMCP 3.x released after cutoff — verify FastMCP 3.x API against gofastmcp.com before implementing)
- Project context (PROJECT.md, 2026-03-05-mdf-development-workflow.md) — architecture constraints, tool list, pycca/simulation requirements: HIGH confidence

---

*Stack research for: MDF v1.0 — MCP server, schema tooling, Phase 0 skills*
*Researched: 2026-03-05*
