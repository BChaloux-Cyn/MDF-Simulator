# Phase 3: Validation Tool - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement three MCP validation tools: `validate_model()` (whole model), `validate_domain(domain)`, and `validate_class(domain, class_name)`. All tools return structured issue lists — never raise exceptions, never return booleans. Also includes a full pycca lark grammar (syntax-only, no evaluation) that Phase 5 will extend with the interpreter. Referential integrity, graph reachability, type cross-references, and guard completeness checks are all in scope. Draw.io tools (Phase 4) and simulation (Phase 5) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Tool signatures

Three MCP tools, all with the same issue-list return format:

- `validate_model(report_missing=True)` — validates the entire model: DOMAINS.yaml + all domains listed there + all state diagrams for active classes
- `validate_domain(domain, report_missing=True)` — validates one domain: class-diagram.yaml + state-diagrams/*.yaml for that domain
- `validate_class(domain, class_name, report_missing=True)` — validates one ClassDef from class-diagram.yaml and its state-diagrams/<ClassName>.yaml if the class is active

`report_missing=True` (default): includes missing-file issues in the returned list.
`report_missing=False`: omits missing-file issues; only structural errors from files that do exist are returned. This supports incremental development where domains and state diagrams are added one at a time.

### Issue format

All tools return `list[dict]` with fields:
- `issue` — human-readable error message
- `location` — domain-scoped dotted path: `"Domain::file::element.path"` (e.g., `"Hydraulics::state-diagrams/Valve.yaml::transitions[2].to"`)
- `value` — the offending value (may be null)
- `fix` — remediation hint for graph/semantic errors where one is computable (e.g., "Add a transition into state 'Idle' from a reachable state"); null for schema/type errors
- `severity` — `"error"` for structural problems, `"warning"` for guard coverage gaps on non-enum types

### Files read per tool

**validate_model():**
- `.design/model/DOMAINS.yaml` (required — if absent, return a missing-file issue and stop)
- `.design/model/<domain>/class-diagram.yaml` for every domain listed in DOMAINS.yaml
- `.design/model/<domain>/state-diagrams/<ClassName>.yaml` for every active class found in each domain's class-diagram.yaml
- `.design/model/<domain>/types.yaml` for each domain (optional — if absent, only primitives are valid types)

**validate_domain(domain):**
- Same files as above but scoped to the one domain

**validate_class(domain, class_name):**
- `.design/model/<domain>/class-diagram.yaml` (to find the ClassDef)
- `.design/model/<domain>/state-diagrams/<class_name>.yaml` if the class is `active`
- `.design/model/<domain>/types.yaml` (optional)
- Does NOT read DOMAINS.yaml or other domain files

### Missing-file logic

Two sources drive expected-file checks:
1. **DOMAINS.yaml → class-diagram.yaml**: every domain entry in DOMAINS.yaml must have a corresponding `.design/model/<domain>/class-diagram.yaml`
2. **active classes → state diagram files**: every `active` class in a domain's class-diagram.yaml must have a `state-diagrams/<ClassName>.yaml`

**Exceptions (no missing-file issue):**
- A subtype class with `specializes` pointing to a supertype that has a state diagram — inherits it, no own file required
- Orphan state diagram files (`.yaml` in state-diagrams/ with no matching active class) — silently ignored

**Missing-file issues are always severity `"error"`** — they are real invalidity, just silenceable via `report_missing=False`.

### Referential integrity checks

Full cross-reference coverage — all named references are checked:

- `association.point_1` / `association.point_2` → class name must exist in classes list
- `transition.to` → target state must exist in the states list
- `transition.event` → event name must exist in the events catalog
- `attribute.type` / `method.return_type` / `method_param.type` → must be one of 5 xtUML primitives OR defined in the domain's types.yaml (if types.yaml absent, only primitives are valid)
- `required_bridge.operations[]` → each operation name must be declared in DOMAINS.yaml for the corresponding bridge
- `provided_bridge.implementations[].name` → each implementation name must match an operation declared in DOMAINS.yaml for the bridge; and every declared operation must have an implementation
- `subtype.specializes` → R-number must exist in the associations list
- `associative.formalizes` → R-number must exist in the associations list

### Graph reachability (state topology)

Uses NetworkX BFS/DFS on the directed graph of states and transitions.

**Initial state:** Determined by an explicit `initial_state` field added to `StateDiagramFile` schema. This is a **schema change** in Phase 3 — `initial_state: str` added as a required field on state diagrams. The validator uses this as the BFS root.

**Unreachable states:** States with no path from `initial_state` via any transition sequence.
Issue format example: `{issue: "State 'Faulted' is unreachable", location: "Hydraulics::state-diagrams/Valve.yaml::states", value: "Faulted", fix: "Add a transition into 'Faulted' from a reachable state or remove it"}`

**Trap states:** States with no outgoing transitions (no way to leave). These may be valid final states — issue is a warning, not an error.
Issue format example: `{issue: "State 'Destroyed' has no outgoing transitions", ..., severity: "warning", fix: "If this is an intentional final state, this warning can be ignored"}`

### Guard completeness checks

Pydantic already enforces all-or-none guard rule (no mix of guarded/unguarded on same (from, event) pair). The validator adds completeness analysis.

**Strings in guards are forbidden.** If a guard expression tests a String-typed variable, return an error.

**Enum-typed guard variable:** All enum values must appear in the guard set for the (from, event) pair. Missing values are flagged as errors with specific missing values named.

**Integer or Real-typed guard variable with defined range** (from types.yaml): Check that the union of intervals covers the declared range. Report specific gaps.

**Integer or Real with no range defined:** Perform inequality interval analysis:
- Parse guard expressions into `(variable, operator, value)` tuples using the pycca grammar
- Collect all intervals for the same variable across the (from, event) pair
- Check for gaps between intervals (e.g., `x < 5` and `x > 5` leaves `x == 5` uncovered — flag the gap)
- `x < N` and `x >= N` = full coverage; `x < N` and `x > N` = gap at `x == N`
- If interval analysis cannot determine completeness (complex expressions), emit a warning

**Multiple unguarded transitions on the same (from, event) pair:** Always an error (ambiguous — no way to determine which fires).

### Pycca grammar

Full lark grammar built in Phase 3. Covers all pycca constructs:
- Assignment statements: `self.x = expr;`
- Generate events: `generate EventName to SELF;` / `generate EventName to CLASS;`
- Bridge calls: `Domain::operation[args];`
- Object lifecycle: `create object of ClassName;` / `delete object of ClassName where ...;`
- Select/where queries: `select any/many <var> from instances of <Class> where <expr>;`
- Cardinality checks: `cardinality <assoc_ref>`
- Conditionals: `if <expr>; ... end if;`

Grammar lives in `mdf_server/pycca/grammar.py` (or `.lark` file). Phase 5 imports this grammar and adds the interpreter/event-runner on top — no grammar duplication.

**Research required:** Grammar scope must be derived from pycca compiler reference (repos.modelrealization.com) before implementation. Researcher should verify construct list above against the actual pycca language spec and document any gaps.

### Claude's Discretion

- NetworkX graph construction details (node/edge representation)
- Internal helper structure (separate validator classes vs. flat functions)
- Exact lark grammar rule names and terminal definitions
- Fix hint wording
- Test fixture structure for validation tests

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `mdf_server/schema/yaml_schema.py` — all Pydantic models ready: `ClassDiagramFile`, `StateDiagramFile`, `DomainsFile`, `TypesFile`, `ClassDef`, `Transition`, `StateDef`, `BridgeStanza`, etc. Phase 3 adds `initial_state: str` field to `StateDiagramFile`.
- `mdf_server/tools/model_io.py::_pydantic_errors_to_issues()` — established pattern for converting Pydantic errors to the `{issue, location, value}` format. Phase 3 extends to `{issue, location, value, fix, severity}`.
- `mdf_server/tools/model_io.py::_resolve_domain_path()` — case-insensitive domain path resolution; reusable in validation tools.
- `mdf_server/tools/validation.py` — currently a docstring stub; implementation goes here.
- `mdf_server/pycca/__init__.py` — stub for Phase 5; lark grammar module (`grammar.py`) added here in Phase 3.

### Established Patterns

- Tools never raise exceptions — all errors returned as structured data
- `MODEL_ROOT = Path(".design/model")` anchored to CWD — follow same pattern in validation module
- Issue format previously: `{issue, location, value}` — Phase 3 extends with `fix` and `severity` fields; existing `write_model` return format is compatible (just missing the new fields, which are optional)
- Flat uv layout: `mdf_server/` directly under `mdf-server/`; `mdf_server/pycca/` already scaffolded

### Integration Points

- `server.py` — three new `@mcp.tool` registrations for `validate_model`, `validate_domain`, `validate_class`
- `yaml_schema.py` — `StateDiagramFile` gets `initial_state: str` added; this is a breaking schema change for any existing state diagram YAML files (must add `initial_state` field)
- `tests/test_model_io.py` — establishes fixture pattern (tmp_path + yaml fixture strings + monkeypatch.chdir); `test_validation.py` follows same structure
- Phase 5 imports `mdf_server/pycca/grammar.py` — grammar must be a standalone importable module

</code_context>

<specifics>
## Specific Ideas

- `report_missing=False` is the intended mode during active development — engineers run validate as they build; "missing domain X" noise is suppressed until the model is structurally complete
- `report_missing=True` (default) is the final verification mode before moving to Phase 4 Draw.io work
- The pycca grammar research flag in STATE.md was written when grammar was Phase 5 scope — it now applies to Phase 3; researcher must tackle grammar derivation as part of Phase 3 research
- Trap states are warnings (not errors) because intentional final states are valid pycca design — Destroyed, Terminated, etc. are legitimate endpoints

</specifics>

<deferred>
## Deferred Ideas

- Guard completeness for complex boolean expressions (AND/OR compound guards) — interval analysis covers simple inequalities; compound expressions emit a warning and defer to Phase 5 simulation
- Polymorphic event dispatch across subtype hierarchies — Phase 5 simulator resolves at runtime
- `initial_state` validation (does the named initial_state exist in the states list?) — this is a referential integrity check that should be added to the referential integrity section above; note for planner: don't forget this one

</deferred>

---

*Phase: 03-validation-tool*
*Context gathered: 2026-03-06*
