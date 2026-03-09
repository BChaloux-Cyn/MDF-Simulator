# Phase 3: Validation Tool - Research

**Researched:** 2026-03-09
**Domain:** Model validation, graph reachability, lark parsing, NetworkX, pycca syntax
**Confidence:** HIGH (core stack), MEDIUM (pycca grammar scope)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tool signatures:**
- `validate_model(report_missing=True)` — validates entire model: DOMAINS.yaml + all domains + all active class state diagrams
- `validate_domain(domain, report_missing=True)` — validates one domain: class-diagram.yaml + state-diagrams/*.yaml
- `validate_class(domain, class_name, report_missing=True)` — validates one ClassDef and its state diagram if active

**Issue format** — all tools return `list[dict]` with fields:
- `issue` — human-readable error message
- `location` — domain-scoped dotted path: `"Domain::file::element.path"`
- `value` — offending value (may be null)
- `fix` — remediation hint (null for schema/type errors)
- `severity` — `"error"` for structural problems, `"warning"` for guard coverage gaps on non-enum types

**Files read per tool:** (fully specified in CONTEXT.md — honor exactly)

**Missing-file logic:**
- DOMAINS.yaml → class-diagram.yaml: every domain entry requires a class-diagram.yaml
- Active classes → state diagram: every `active` class requires state-diagrams/<ClassName>.yaml
- Exception: subtype class with `specializes` pointing to a supertype that has a state diagram — no own file required
- Orphan state diagram files silently ignored
- Missing-file issues always severity `"error"`

**Referential integrity checks:** All named references checked (associations, transition.to, transition.event, attribute.type, bridge operations, subtype.specializes, associative.formalizes, initial_state)

**Graph reachability:** Uses NetworkX BFS/DFS. `initial_state: str` added to `StateDiagramFile` as a **schema change** in Phase 3. Unreachable states = error. Trap states = warning.

**Guard completeness:**
- Strings in guards = error
- Enum guards: all values must appear = error if missing
- Integer/Real with defined range: interval coverage check
- Integer/Real without range: inequality interval analysis
- Multiple unguarded transitions on same (from, event) = error

**Pycca grammar:** Full lark grammar built in Phase 3 in `pycca/grammar.py`. Phase 5 imports this and adds interpreter. No grammar duplication.

**Implementation files:**
- `tools/validation.py` — main implementation (currently a stub)
- `pycca/grammar.py` — new file for lark grammar
- `schema/yaml_schema.py` — add `initial_state: str` to `StateDiagramFile`
- `server.py` — three new `@mcp.tool` registrations
- `tests/test_validation.py` — new test file

### Claude's Discretion

- NetworkX graph construction details (node/edge representation)
- Internal helper structure (separate validator classes vs. flat functions)
- Exact lark grammar rule names and terminal definitions
- Fix hint wording
- Test fixture structure for validation tests

### Deferred Ideas (OUT OF SCOPE)

- Guard completeness for complex boolean expressions (AND/OR compound guards) — complex expressions emit warning, defer to Phase 5
- Polymorphic event dispatch across subtype hierarchies — Phase 5 simulator resolves at runtime
- `initial_state` validation (does the named initial_state exist in the states list?) — NOTE FOR PLANNER: this was listed as deferred but the CONTEXT.md notes it should be added to referential integrity checks; treat as IN SCOPE
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MCP-04 | `validate_model(domain)` returns list of issues: referential integrity, graph reachability (BFS/DFS unreachable states, trap states), pycca syntax pre-check; never pass/fail | NetworkX 3.6.1 for graph analysis; lark 1.x for grammar; existing `_pydantic_errors_to_issues()` pattern extended with `fix` and `severity` fields; three-tool architecture documented |
</phase_requirements>

---

## Summary

Phase 3 implements three MCP validation tools that perform deep structural analysis of the model YAML files beyond what Pydantic schema validation catches. The two primary technical dependencies not yet in pyproject.toml are **NetworkX** (for graph reachability) and **lark** (for pycca grammar parsing). Both are well-established, stable libraries.

The pycca action language is a **critical research finding**: the upstream pycca compiler's action code (inside `{ }` blocks) is **plain C code with PYCCA preprocessor macros** (`PYCCA_generate()`, `PYCCA_createInstance()`, etc.), not a high-level DSL with OAL-style statements. The CONTEXT.md's construct list (generate, select, create, delete, if/end if) describes the *intended domain-specific syntax for this MDF project* — not what the upstream pycca compiler accepts. This means the grammar is being designed from scratch for this project rather than derived from upstream documentation.

The guard completeness checks require interval arithmetic logic that must be implemented manually — no existing library cleanly handles the `(variable, operator, value)` tuple extraction and gap analysis described in CONTEXT.md. This is appropriate to hand-roll since the domain is narrow (simple inequality expressions only; compound boolean expressions are deferred).

**Primary recommendation:** Add `networkx>=3.4` and `lark>=1.1` to pyproject.toml dependencies. Implement `tools/validation.py` with three public tool functions sharing a private issue-accumulation pattern. Write `pycca/grammar.py` as a standalone lark grammar module covering the MDF-specific action language constructs listed in CONTEXT.md (not upstream pycca C macros).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| networkx | >=3.4 (current: 3.6.1) | Directed graph construction, BFS reachability, successor/predecessor queries | Standard Python graph library; `descendants()` and `DiGraph` are exactly what BFS reachability needs |
| lark | >=1.1 (current: 1.2.x) | LALR/Earley parser for pycca action language grammar | Modern lark (not lark-parser) is the maintained package; excellent for DSL grammars; used by many xtUML-adjacent tools |
| pydantic v2 | >=2.12.5 (already installed) | Schema validation + `StateDiagramFile` schema change | Already in project; `initial_state: str` field addition is additive |
| pyyaml | >=6.0.3 (already installed) | YAML loading for all model files | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| itertools.groupby | stdlib | Group transitions by (from, event) for guard checks | Already used in `yaml_schema.py`; same pattern for validator |
| pathlib.Path | stdlib | File system traversal, missing-file checks | Already used throughout; `MODEL_ROOT` pattern |
| collections.defaultdict | stdlib | Accumulating issues by category | Useful for grouping referential integrity checks |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| networkx | igraph, rustworkx | Both faster for large graphs; overkill for model graphs (tens of nodes); networkx has better Python API and docs |
| lark (LALR) | pyparsing, parsimonious | lark is more expressive, generates proper parse trees; better fit for grammar-first design |
| lark (LALR) | lark (Earley) | LALR is faster and sufficient for the deterministic pycca action language; Earley needed only for ambiguous grammars |

**Installation (additions to pyproject.toml):**
```bash
uv add networkx lark
```

---

## Architecture Patterns

### Recommended Project Structure
```
tools/
└── validation.py         # Three public tool functions + private helpers

pycca/
└── grammar.py            # Lark Grammar object, exported as PYCCA_GRAMMAR

schema/
└── yaml_schema.py        # Add initial_state: str to StateDiagramFile (BREAKING)

tests/
└── test_validation.py    # Mirrors test_model_io.py fixture pattern
```

### Pattern 1: Issue Accumulator (Extend Existing Pattern)

**What:** All three tool functions accumulate issues into a `list[dict]` and return it — never raising, never returning a boolean. Each check category has a private `_check_*` function that appends to the list.

**When to use:** Every check in the validator

**Example (extending `_pydantic_errors_to_issues`):**
```python
# Extended issue format — add fix and severity to existing pattern
def _make_issue(
    issue: str,
    location: str,
    value: object = None,
    fix: str | None = None,
    severity: str = "error",
) -> dict:
    return {"issue": issue, "location": location, "value": value, "fix": fix, "severity": severity}
```

### Pattern 2: NetworkX Reachability Check

**What:** Build a `DiGraph` from state diagram states/transitions, run BFS from `initial_state`, find unreachable nodes and trap nodes.

**When to use:** Every `active` class that has a state diagram

**Example:**
```python
# Source: https://networkx.org/documentation/stable/reference/algorithms/
import networkx as nx

def _check_reachability(diagram: StateDiagramFile, domain: str) -> list[dict]:
    issues = []
    G = nx.DiGraph()
    state_names = {s.name for s in diagram.states}
    G.add_nodes_from(state_names)
    for t in diagram.transitions:
        G.add_edge(t.from_state, t.to)

    # Unreachable states: states not in descendants(initial_state) + initial_state itself
    reachable = nx.descendants(G, diagram.initial_state) | {diagram.initial_state}
    for state in state_names - reachable:
        issues.append(_make_issue(
            issue=f"State '{state}' is unreachable",
            location=f"{domain}::state-diagrams/{diagram.class_name}.yaml::states",
            value=state,
            fix=f"Add a transition into '{state}' from a reachable state or remove it",
        ))

    # Trap states: states with no outgoing edges
    for state in state_names:
        if G.out_degree(state) == 0:
            issues.append(_make_issue(
                issue=f"State '{state}' has no outgoing transitions",
                location=f"{domain}::state-diagrams/{diagram.class_name}.yaml::states",
                value=state,
                fix="If this is an intentional final state, this warning can be ignored",
                severity="warning",
            ))
    return issues
```

### Pattern 3: Lark Grammar Module

**What:** `pycca/grammar.py` exports a `Grammar` string and optionally a pre-compiled `Lark` object. Phase 5 imports the grammar string and builds its own parser with transformer attached.

**When to use:** Guard expression parsing for interval analysis; Phase 5 interpreter

**Example structure:**
```python
# pycca/grammar.py
from lark import Lark

PYCCA_GRAMMAR = r"""
    // Implemented in Phase 3 — Phase 5 imports this and adds transformer

    start: statement+

    statement: assignment
             | generate_stmt
             | bridge_call
             | create_stmt
             | delete_stmt
             | select_stmt
             | if_stmt

    assignment: "self" "." NAME "=" expr ";"
    generate_stmt: "generate" NAME "to" ("SELF" | "CLASS") ";"
    bridge_call: NAME "::" NAME "[" arglist? "]" ";"
    create_stmt: "create" "object" "of" NAME ";"
    delete_stmt: "delete" "object" "of" NAME "where" expr ";"
    select_stmt: "select" ("any"|"many") NAME "from" "instances" "of" NAME ("where" expr)? ";"
    if_stmt: "if" expr ";" statement* "end" "if" ";"

    // Guard expression (also used standalone for guard completeness analysis)
    expr: NAME OP NUMBER   -> simple_compare
        | expr "and" expr  -> and_expr
        | expr "or" expr   -> or_expr
        | "(" expr ")"

    OP: "<" | "<=" | ">" | ">=" | "==" | "!="
    NUMBER: /[0-9]+(\.[0-9]+)?/
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
    arglist: expr ("," expr)*

    %ignore /\s+/
    %ignore /\/\/[^\n]*/
"""

# Pre-compiled parser for guard expression analysis (Phase 3 use)
GUARD_PARSER = Lark(PYCCA_GRAMMAR, start="expr", parser="earley")

# Full statement parser (Phase 5 use)
STATEMENT_PARSER = Lark(PYCCA_GRAMMAR, start="start", parser="lalr")
```

**Note:** The exact grammar rule names and terminals are Claude's discretion per CONTEXT.md. The above is illustrative. Phase 5 will add a Transformer class in its own module.

### Pattern 4: Missing-File Checks

**What:** Two distinct missing-file sources require separate check logic. Apply `report_missing` flag before appending.

```python
def _check_missing_class_diagram(domain: str, domain_path: Path, report_missing: bool) -> list[dict]:
    issues = []
    cd = domain_path / "class-diagram.yaml"
    if not cd.exists() and report_missing:
        issues.append(_make_issue(
            issue=f"Missing class-diagram.yaml for domain '{domain}'",
            location=f"{domain}::class-diagram.yaml",
            value=None,
        ))
    return issues
```

### Anti-Patterns to Avoid

- **Raising exceptions in tool functions:** Every error path must append to the issue list and continue or return early. The function boundary is the exception firewall.
- **Returning early on first error:** Unless the missing file makes continuation impossible (e.g., DOMAINS.yaml absent for `validate_model`), continue accumulating all issues.
- **Importing `pycca.grammar` at module level in tests:** Use `importlib.reload()` pattern from `test_model_io.py` for any module using `MODEL_ROOT`.
- **Calling `nx.descendants()` when `initial_state` not in graph:** If `initial_state` references a non-existent state, `descendants()` will raise `NetworkXError`. Check referential integrity first.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directed graph traversal | Custom BFS loop | `networkx.DiGraph` + `nx.descendants()` | Handles edge cases (self-loops, disconnected subgraphs) correctly |
| PEG/LALR parser for guard expressions | Regex-based guard parser | `lark.Lark` with LALR | Regex breaks on nested parens, operator precedence; lark handles correctly |
| YAML loading | Custom parser | `pyyaml.safe_load` (already used) | Already established pattern |
| Pydantic validation | Manual field checks | `ClassDiagramFile.model_validate()` (already used) | Already established pattern |

**Key insight:** The guard completeness interval arithmetic (finding gaps between `x < 5` and `x > 5`) IS appropriate to hand-roll because no library exists for this specific domain. The gap: `x == 5`. Build a small `_interval_gap_check()` helper.

---

## Common Pitfalls

### Pitfall 1: NetworkX `descendants()` on Missing Initial State

**What goes wrong:** If `initial_state` references a state name not in the graph, `nx.descendants()` raises `NetworkXError: The node ... is not in the digraph`.

**Why it happens:** `initial_state` is a new required field; referential integrity check for it must run before graph reachability.

**How to avoid:** Run `_check_referential_integrity()` before `_check_reachability()`. If referential integrity finds `initial_state` not in states, skip reachability check for that diagram and emit the referential integrity error only.

**Warning signs:** `KeyError` or `NetworkXError` during validation run.

### Pitfall 2: Pydantic `model_validate` After `initial_state` Schema Change

**What goes wrong:** Existing state diagram YAML files (in tests and fixtures) will fail to parse after adding `initial_state: str` as a required field on `StateDiagramFile`.

**Why it happens:** Required field with no default — absence of default is the enforcement mechanism (same as `schema_version`).

**How to avoid:** Update all existing test fixtures (`test_yaml_schema.py`, any state diagram YAML in tests) to include `initial_state` before running tests. This is a breaking schema change.

**Warning signs:** All `StateDiagramFile` tests fail immediately after schema change.

### Pitfall 3: Guard Interval Analysis Edge Cases

**What goes wrong:** Guard expression `x < N` and `x >= N` covers fully; `x < N` and `x > N` leaves gap at `x == N`. The analysis must use half-open/closed interval logic correctly.

**Why it happens:** Naive "does union cover range" logic misses the difference between `<` and `<=`.

**How to avoid:** Normalize intervals to half-open form `[lo, hi)` before gap analysis. Map: `x < N` → `(-inf, N)`, `x <= N` → `(-inf, N+1)`, `x > N` → `(N+1, +inf)`, `x >= N` → `(N, +inf)`.

**Warning signs:** False positives (flagging complete coverage as gap) or false negatives (missing real gaps).

### Pitfall 4: Pycca Grammar Scope Mismatch

**What goes wrong:** The upstream pycca compiler (repos.modelrealization.com) uses plain C code inside `{ }` action blocks with PYCCA preprocessor macros — not a high-level DSL. The CONTEXT.md construct list (generate, create, select, if/end if) is the **MDF project's own action language design**, not a derivation of upstream pycca.

**Why it happens:** Confusion between the pycca model description language and the MDF-specific action language that happens to use pycca's model structure.

**How to avoid:** Treat the grammar as a fresh design guided by CONTEXT.md constructs. The grammar is for: assignment, generate, bridge_call, create, delete, select, if/end if — as listed in CONTEXT.md. Do not attempt to replicate upstream C macro syntax.

**Warning signs:** Searching pycca docs for OAL-style statement syntax and finding only C code.

### Pitfall 5: `report_missing=False` Not Suppressing All Missing-File Issues

**What goes wrong:** The `report_missing` flag must suppress missing-file issues at the append point, not by skipping file reads. If a file is missing, still run structural checks on files that do exist.

**Why it happens:** Temptation to early-return if any file is missing.

**How to avoid:** Check file existence before loading, append missing-file issue only if `report_missing=True`, then continue with checks on available files.

---

## Code Examples

Verified patterns from project source and official library docs:

### Existing Issue Format (from model_io.py)
```python
# Source: tools/model_io.py — established pattern to extend
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
# Phase 3 extends this format with "fix" and "severity" fields
```

### StateDiagramFile Schema Change
```python
# schema/yaml_schema.py — add initial_state to StateDiagramFile
class StateDiagramFile(SchemaVersionMixin):
    model_config = ConfigDict(populate_by_name=True)

    domain: str
    class_name: str = Field(alias="class")
    initial_state: str          # NEW REQUIRED FIELD — Phase 3 schema change
    events: list[EventDef] = []
    states: list[StateDef]
    transitions: list[Transition] = []
    # ... existing model_validator unchanged
```

### NetworkX Descendants API
```python
# Source: https://networkx.org/documentation/stable/reference/algorithms/
import networkx as nx

G = nx.DiGraph()
G.add_nodes_from(["Idle", "Running", "Faulted"])
G.add_edges_from([("Idle", "Running"), ("Running", "Idle")])

reachable = nx.descendants(G, "Idle") | {"Idle"}
# reachable = {"Idle", "Running"}
# "Faulted" is unreachable

trap_states = [n for n in G.nodes if G.out_degree(n) == 0]
# trap_states = []  (all nodes have outgoing edges)
```

### Lark Guard Expression Parser
```python
# Source: https://lark-parser.readthedocs.io/en/latest/
from lark import Lark, Token, Tree

GUARD_GRAMMAR = r"""
    expr: NAME OP NUMBER   -> simple_compare
    OP: /[<>]=?|==|!=/
    NUMBER: /[0-9]+(\.[0-9]+)?/
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
    %ignore /\s+/
"""
parser = Lark(GUARD_GRAMMAR, start="expr", parser="earley")
tree = parser.parse("pressure >= 100")
# Tree('simple_compare', [Token('NAME', 'pressure'), Token('OP', '>='), Token('NUMBER', '100')])
```

### Test Fixture Pattern (mirrors test_model_io.py)
```python
# tests/test_validation.py — follow established pattern
import importlib
import pytest
from pathlib import Path

VALID_STATE_DIAGRAM_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
states:
  - name: Idle
  - name: Open
events:
  - name: Open_valve
transitions:
  - from: Idle
    to: Open
    event: Open_valve
"""

def test_validate_class_unreachable_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from tools import validation
    importlib.reload(validation)
    # ... setup files, call validate_class, assert issues
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `lark-parser` package name | `lark` package name | ~2021 (v0.12+) | Install `lark`, not `lark-parser` — different PyPI package |
| OAL/MASL for xtUML actions | pycca uses C + macros for upstream; MDF project defines its own DSL | Project design decision | Grammar is a fresh design, not a derivation |
| Existing issue format `{issue, location, value}` | Extended to `{issue, location, value, fix, severity}` | Phase 3 | `fix` and `severity` are new; backward compatible (old callers get extra fields) |

**Deprecated/outdated:**
- `lark-parser` PyPI package: use `lark` instead. `lark-parser` is unmaintained.

---

## Open Questions

1. **`initial_state` validation in deferred section vs. in-scope**
   - What we know: CONTEXT.md `<deferred>` section lists `initial_state` validation (does the named initial_state exist in states list?) but adds "note for planner: don't forget this one"
   - What's unclear: Is this actually in scope or deferred?
   - Recommendation: Treat as IN SCOPE. It is a straightforward referential integrity check (one additional check among many). The deferred note is a planning reminder, not a deferral decision.

2. **`initial_state` required vs. optional for non-active classes**
   - What we know: `initial_state` is being added to `StateDiagramFile`. State diagrams only exist for active classes.
   - What's unclear: Should `initial_state` be `str` (required) or `str | None` (optional)?
   - Recommendation: `str` required — if a state diagram file exists, it must have an initial state. The schema change is only for `StateDiagramFile`, which only appears for active classes.

3. **Cardinality check syntax in pycca grammar**
   - What we know: CONTEXT.md lists `cardinality <assoc_ref>` as a pycca construct
   - What's unclear: Is `cardinality` a statement (returning a value) or an expression? How is it used?
   - Recommendation: Treat as an expression that can appear in guard conditions. Parse as `cardinality NAME`. If Phase 5 integration reveals otherwise, the grammar can be extended.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_validation.py -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-04 | `validate_model()` returns issue list, never raises | unit | `uv run pytest tests/test_validation.py::test_validate_model_no_raise -x` | Wave 0 |
| MCP-04 | `validate_domain()` returns issue list, never raises | unit | `uv run pytest tests/test_validation.py::test_validate_domain_no_raise -x` | Wave 0 |
| MCP-04 | `validate_class()` returns issue list, never raises | unit | `uv run pytest tests/test_validation.py::test_validate_class_no_raise -x` | Wave 0 |
| MCP-04 | Unreachable states detected and reported | unit | `uv run pytest tests/test_validation.py::test_unreachable_state -x` | Wave 0 |
| MCP-04 | Trap states detected as warnings | unit | `uv run pytest tests/test_validation.py::test_trap_state_warning -x` | Wave 0 |
| MCP-04 | Referential integrity: bad association class reported | unit | `uv run pytest tests/test_validation.py::test_bad_association_class -x` | Wave 0 |
| MCP-04 | Referential integrity: bad transition.to reported | unit | `uv run pytest tests/test_validation.py::test_bad_transition_target -x` | Wave 0 |
| MCP-04 | Missing class-diagram.yaml reported when report_missing=True | unit | `uv run pytest tests/test_validation.py::test_missing_class_diagram -x` | Wave 0 |
| MCP-04 | Missing-file issues suppressed when report_missing=False | unit | `uv run pytest tests/test_validation.py::test_report_missing_false -x` | Wave 0 |
| MCP-04 | Guard string type = error | unit | `uv run pytest tests/test_validation.py::test_guard_string_type_error -x` | Wave 0 |
| MCP-04 | Guard enum completeness check | unit | `uv run pytest tests/test_validation.py::test_guard_enum_completeness -x` | Wave 0 |
| MCP-04 | Pycca grammar imports and parses guard expression | unit | `uv run pytest tests/test_validation.py::test_pycca_grammar_import -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_validation.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_validation.py` — covers all MCP-04 behaviors above; does not exist yet
- [ ] `pycca/grammar.py` — lark grammar module; stub exists in `pycca/__init__.py` only
- [ ] `networkx` and `lark` packages — not in pyproject.toml or .venv; must be added via `uv add networkx lark`
- [ ] Update all existing state diagram YAML fixtures in existing tests to add `initial_state` field (breaking schema change)

---

## Sources

### Primary (HIGH confidence)
- NetworkX 3.6.1 official docs — `descendants()`, `DiGraph`, `bfs_tree()` API verified
- Lark grammar reference — `https://lark-parser.readthedocs.io/en/latest/grammar.html` — rule/terminal syntax, EBNF operators, `%ignore`, `%import` directives
- Project source: `schema/yaml_schema.py` — all Pydantic models read directly
- Project source: `tools/model_io.py` — `_pydantic_errors_to_issues()`, `_resolve_domain_path()`, `MODEL_ROOT` patterns read directly

### Secondary (MEDIUM confidence)
- `http://repos.modelrealization.com/cgi-bin/fossil/tcl-cm3/doc/trunk/pycca/doc/pycca.html` — pycca model description language doc: confirmed action CODE blocks are plain C with PYCCA macros, not a DSL
- PyPI lark 1.x — active package (`lark`, not `lark-parser`); version confirmed from PyPI page
- PyPI networkx 3.6.1 — current version confirmed from PyPI search

### Tertiary (LOW confidence)
- Interval arithmetic gap analysis approach — derived from CONTEXT.md specification and standard interval math; not verified against a reference implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — NetworkX and lark are well-documented, stable libraries; versions confirmed from PyPI
- Architecture: HIGH — patterns derived directly from existing project source code
- Pycca grammar scope: MEDIUM — upstream pycca confirmed as C-based; MDF grammar is a fresh design per CONTEXT.md constructs; no external reference exists
- Guard interval analysis: MEDIUM — logic is sound but no reference implementation to verify against
- Pitfalls: HIGH — breaking schema change and nx.descendants() edge case are deterministic

**Research date:** 2026-03-09
**Valid until:** 2026-06-09 (stable libraries; networkx and lark APIs change slowly)
