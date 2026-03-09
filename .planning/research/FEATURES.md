# Feature Research

**Domain:** Model-Driven Framework (MDF) — developer tooling for xUML/Shlaer-Mellor embedded systems design
**Researched:** 2026-03-05
**Confidence:** HIGH — drawn from detailed project design documents and directly specified requirements

---

## Feature Area 1: Schemas & Templates

These are the file format definitions and folder structure templates that constitute the MDF's data model. Every other feature depends on this foundation.

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| YAML model schema — classes with stereotypes, attributes, identifiers | Without this, MCP tools and agents have no contract to write against; the entire system collapses | MEDIUM | Must cover: stereotype (entity/associative/active), attributes with type/unit/default/identifier, methods with params/returns |
| YAML model schema — associations with verb phrases and multiplicity | Associations are first-class in xUML; omitting them means the model can't express relationships | MEDIUM | Must cover: from/to class, multiplicity (1, 1..*, 0..1), verb phrase, type (association/generalization/reflexive), referential attributes |
| YAML model schema — state machines with pycca action language | Behavioral modeling is the core value of SM-xUML; state machines without action language are decoration | HIGH | Must cover: initial state, states list, transitions with event/guard/action (pycca string blocks) |
| YAML model schema — domain bridges | Bridges are the subsystem interface contract; without them domains are isolated blobs | MEDIUM | Must cover: from domain, to domain, operation name, params, direction (required/provided) |
| DOMAINS.md template | Engineers expect a map of the whole system before diving into individual domains | LOW | Lists all domains, their purpose, realized domains, and bridge index |
| Folder structure (.design/model/, .design/behavior/, .design/research/) | Sessions resume across days; a consistent folder contract is how agents know where to look | LOW | Defined once at project bootstrap by /mdf:new-project |

### Differentiators (What Makes This Schema Distinct)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Canonical Draw.io schema (1:1 bijection with YAML) | Enables deterministic sync_from_drawio — a structured parse, not an interpretation problem; eliminates "which version is canonical?" ambiguity | HIGH | Each semantic element maps to a specific shape type; no freeform shapes without YAML equivalents; defined at schema design time, not runtime |
| pycca action language embedded in YAML string blocks | Bridges the gap from model to compiled embedded C; enables simulation and code generation without a separate DSL file | MEDIUM | Requires documenting pycca syntax subset supported in YAML context; guards as predicate expressions, actions as pycca statements |
| Structural equality semantics (not byte equality) | Round-trip validation checks semantic equivalence — same classes/attributes/associations/state topology — ignoring layout, color, order; engineers can freely reposition in Draw.io without breaking sync | LOW | Documented as a schema property, enforced at validation time |
| Behavior doc format (domain / class / state machine granularity) | Mirrors model structure for discoverability; more granular scope takes precedence on conflict; feeds simulation test generation | MEDIUM | Three template variants: domain.md, class.md, state-machine.md |
| TRANSLATION.md template | Per-target implementation guide for the execution domain contract; allows same model to target embedded C and Python simulation | MEDIUM | Sections: pycca-to-target mapping, execution domain API, code generation patterns |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Single monolithic YAML file for entire model | Simpler to think about; one file to open | Exceeds context window for any real system; agents must load more than they need; slows all tool operations | One YAML file per domain — agents call read_model(domain) for the specific domain they need |
| Draw.io as source of truth | Engineers are comfortable in visual tools | Draw.io XML is not stable as a parse target (layout changes affect XML); agent-written Draw.io is fragile; bidirectional authority creates conflicts | YAML is always source of truth; Draw.io is a generated presentation view that can be synced back structurally |
| Freeform Draw.io schema (engineer can use any shapes) | Maximum drawing flexibility | sync_from_drawio becomes an interpretation problem, not a parse problem; round-trip fidelity breaks | Canonical schema: specific shape types for each semantic element; layout freedom, schema discipline |
| Scrall action language instead of pycca | Scrall is more modern and standardized (part of Leon Starr's modelint toolkit) | Target language is embedded C; pycca maps directly to embedded C semantics and has a working compiler; Scrall tooling is less mature for this path | pycca in YAML string blocks; Scrall as future consideration if tooling matures |
| Generic Markdown tables for model content | Engineers know Markdown | No schema enforcement; agents produce inconsistent formats across sessions; no structural validation possible | YAML with defined schema; Markdown behavior docs are prose layered on top of the YAML model, not replacements |

---

## Feature Area 2: MCP Server (Python/FastMCP)

Eight tools forming the read/write/validate/render/simulate API that all agents and skills call. These are primitives — dumb, composable, single-responsibility.

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| read_model(domain) | Agents need to inspect a domain model before modifying it; without read, write is blind | LOW | Returns YAML string for named domain; error if domain not found |
| write_model(domain, yaml) | Core mutation operation; agents produce YAML and must persist it | LOW | Saves file, runs validate_model immediately, returns validation errors if present; idempotent |
| list_domains() | Skills resume in fresh sessions; agents must reconstruct current state without knowing what exists | LOW | Returns list of domain names; does NOT return content; enables progressive disclosure |
| validate_model(domain) | Structural consistency is a graph problem, not an AI problem; must be mechanically checked | HIGH | Returns list of specific fixable issues — not pass/fail; must include: undefined class references, missing identifier, unreachable states (graph reachability BFS/DFS from initial), trap states (no outgoing, not declared terminal), duplicate class names, malformed multiplicity |
| render_to_drawio(domain) | Visual review is required before simulation; engineers need Draw.io output to inspect and hand off for review | HIGH | Generates Draw.io XML from YAML using canonical schema; deterministic for same YAML input; idempotent |
| simulate_state_machine(class, events) | Behavioral verification before code is the core value of the framework; simulation proves the model behaves as specified | HIGH | Interprets pycca action language from YAML; takes event sequence, returns execution trace (state transitions, guards evaluated, actions executed, final state) |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| validate_drawio(domain, xml) | Validates user-edited Draw.io XML against the canonical schema before syncing; catches schema violations early | MEDIUM | Returns list of issues: unrecognized shape types, missing labels, connections without valid endpoints; separate from structural equality check |
| sync_from_drawio(domain, xml) | Closes the visual editing loop — engineer repositions shapes in Draw.io, structural changes (renamed class, added association) merge back to YAML | HIGH | Depends on canonical schema being defined; structured parse not interpretation; returns YAML diff for review before write; validate_drawio must pass first |
| Graph reachability in validate_model | Catches dead states and trap states that are structurally valid but behaviorally wrong — cannot be detected by AI review alone | MEDIUM | BFS/DFS from initial state; unreachable = never visited; trap = no outgoing transitions and not declared terminal; event coverage = informational list of unhandled events per state |
| Actionable error messages | Engineers act on tool errors directly; vague errors require a debug loop that wastes context | LOW | Each error: issue type, location (e.g., "Motor.state_machine.states[2]"), value found, suggested fix; "Did you mean 'Controller'?" style suggestions for typos |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| manage_model(action="render") — multipurpose tool | Fewer tools to discover; simpler API surface | Claude selects tools by name and description; a multi-action tool is harder to select correctly than two dedicated tools; incorrect action selection produces silent wrong behavior | Dedicated tools: render_to_drawio, sync_from_drawio, validate_drawio — one responsibility each |
| validate_model returning pass/fail boolean | Simpler to parse in agent code | Claude needs to address each issue in turn; a boolean gives no recovery path; agents retry blindly rather than fixing the specific problem | Return list of {issue, location, value, fix} objects; agent can iterate through and fix each one |
| Tools that append or accumulate on repeated calls | Natural for some operations (append log) | Claude retries when uncertain; accumulating tools produce duplicates across retries; debugging cross-session state becomes a nightmare | Idempotent writes: write_model overwrites, render_to_drawio regenerates, list_domains always reflects current state |
| Batch tool (process_domain(read=True, validate=True, render=True)) | Fewer round-trips | Loses granularity for error diagnosis; if batch fails partway, Claude can't tell which step failed; retry logic is ambiguous | Composable single-responsibility tools; skills sequence them with explicit error handling between steps |
| Tool descriptions as generic labels ("Write model") | Less verbose | Tool descriptions are prompts — Claude reads them to decide which tool to call; generic labels cause wrong tool selection | Write descriptions as specific prompts with when-to-use context and what distinguishes from similar tools |

---

## Feature Area 3: Phase 0 Skills (/mdf: commands)

Skills are the UX layer — where workflow sequencing, agent orchestration, and session state reconstruction live. They call MCP tools as primitives. They ask the engineering questions GSD never asks.

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| /mdf:new-project | Every workflow needs a bootstrap; without it the engineer must manually create directory structure and templates | LOW | Creates .design/ and .planning/ structure; initializes DOMAINS.md; appends model reference block to CLAUDE.md; kicks off Stage 1 domain questioning |
| /mdf:discuss-domain | Stage 1 is domain questioning — the foundational step; without domain boundaries, class diagrams have nowhere to go | MEDIUM | Spawns Questioner agent (extracts domain structure) + Domain-Verifier (consistency check at end); outputs DOMAINS.md update and domain.md behavior docs; also spawns Researcher and Architect agents for research/ and initial domain map |
| /mdf:discuss-class | Stage 2 class diagram planning — engineers need to define classes before state machines can be modeled | MEDIUM | Spawns Class Diagram Agent + Domain-Verifier; takes DOMAINS.md and behavior docs as input; outputs class diagram per domain and extended class.md behavior docs |
| /mdf:discuss-state | Stage 3 state diagram planning — state machines are the behavioral heart of SM-xUML | MEDIUM | Spawns State Diagram Agent + Domain-Verifier; takes class diagrams and behavior docs as input; outputs state diagrams and state-machine.md behavior docs |
| /mdf:review-model | Engineers need a human-reviewable visual before committing to simulation | LOW | Calls render_to_drawio for all domains; opens or surfaces Draw.io files for review; validates structural equality after engineer edits via validate_drawio + sync_from_drawio |
| /mdf:verify-model | Phase 1 model verification — simulation proves behavioral correctness before any code is written | HIGH | Spawns Simulation Test Generator (reads behavior docs → test suite from realized bridge inputs); runs simulate_state_machine per test; reports pass/fail per behavioral spec; Domain-Verifier runs full-model consistency check |
| /mdf:pause / /mdf:resume | Sessions end; engineers context-switch; the workflow must survive a closed browser tab | LOW | pause: commits current state to git with checkpoint message; resume: calls list_domains(), reads DOMAINS.md, reconstructs current stage and next action; no context is assumed from previous session |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| /mdf:configure-target | Phase 2 target configuration — generates the execution domain (the runtime substrate) for a specific target; this is what enables C code generation | HIGH | Spawns Execution Domain Agent; reads verified model + STACK.md + board specs; outputs updated STACK.md, TRANSLATION.md, execution domain implementation, target repo structure; minimal user input required for target-specific decisions |
| /mdf:plan-roadmap | Translates the verified model and target config into a GSD-compatible ROADMAP.md + MILESTONES.md for Phase 3+ | MEDIUM | Produces milestone boundaries based on domain dependency order (domain bridges drive sequencing); each milestone maps to a domain or a bridge implementation wave |
| Domain-Verifier integration at end of each step | Catches inconsistencies before they propagate; structural errors caught at Stage 2 are far cheaper to fix than at Stage 3 or simulation | MEDIUM | Verifier runs automatically at end of discuss-domain, discuss-class, discuss-state; reports to calling agent: pass or list of specific inconsistencies; does not produce a persistent artifact |
| Bridge consistency check once both referenced class diagrams are complete | Bridge validation only makes sense when both endpoints exist; this is the right trigger, not a fixed schedule | LOW | Domain-Verifier checks bridge once the last of the two referenced domains has its class diagram; avoids false positives during construction |
| Session state reconstruction from disk | Claude has no memory across sessions; the skill must always behave correctly in a fresh context | LOW | Every skill starts with list_domains() + read DOMAINS.md; infers current stage from what artifacts exist; presents engineer with current state before asking what to do next |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Single /mdf:start skill covering all three stages | Simpler UX; one command to start everything | Stage boundaries matter — engineer may want to complete one domain before moving to the next; a single skill forces a fixed sequence that doesn't match real design iteration | Composable stage skills (discuss-domain, discuss-class, discuss-state) that can be called in the order the engineer needs; /mdf:new-project bootstraps, stage skills iterate |
| GSD's discuss-phase for model-based context gathering | Reuse existing tooling; less to build | GSD asks product questions ("what do you want to build?"); MDF Phase 0 needs engineering questions ("what are the domains, classes, state machines, bridges?"); GSD's discuss-phase would produce the wrong artifact | Custom agents (Questioner, Class Diagram Agent, State Diagram Agent) that ask the right questions; GSD discuss-phase is only used in Phase 3+ for implementation gaps |
| Domain-Verifier producing a persistent artifact | Natural to save verification output for audit trail | Verifier output is only valid at the moment it runs; stale verifier reports are misleading; the model is the ground truth, not a snapshot of validation state | Verifier reports to the calling agent inline; engineer sees results in the conversation; if issues exist, they are fixed before moving forward |
| Freezing the model after Phase 0 | Immutable model = simpler implementation | Implementation reveals model errors; bugs during testing may indicate model inconsistencies; scope changes require model revision; a frozen model produces technically correct but wrong code | Model is never frozen; Model Updater agent handles revisions; simulation re-runs automatically after model updates |
| Generating code directly from skills (without MCP tools) | Fewer layers; simpler implementation | Skills that generate and write files directly cannot verify what was written; round-trip requires reading back; MCP tools provide the inspectable state layer | Skills orchestrate; MCP tools persist and validate; agents use tools to write model files, not direct filesystem writes |

---

## Feature Dependencies

```
[YAML Schema]
    └──required by──> [write_model / read_model / validate_model]
                          └──required by──> [render_to_drawio]
                          └──required by──> [simulate_state_machine]
                          └──required by──> [/mdf:discuss-domain]

[Canonical Draw.io Schema]
    └──required by──> [render_to_drawio]
    └──required by──> [validate_drawio]
    └──required by──> [sync_from_drawio]

[validate_model (with graph reachability)]
    └──required by──> [/mdf:verify-model]
    └──required by──> [/mdf:review-model (post-sync check)]

[simulate_state_machine]
    └──required by──> [/mdf:verify-model]

[/mdf:new-project]
    └──required before──> [/mdf:discuss-domain]

[/mdf:discuss-domain]
    └──required before──> [/mdf:discuss-class]

[/mdf:discuss-class]
    └──required before──> [/mdf:discuss-state]

[/mdf:discuss-state]
    └──required before──> [/mdf:verify-model]

[/mdf:verify-model]
    └──required before──> [/mdf:configure-target]

[/mdf:configure-target]
    └──required before──> [/mdf:plan-roadmap]

[pycca in YAML]
    └──enables──> [simulate_state_machine]
    └──enables──> [TRANSLATION.md template (code generation path)]

[DOMAINS.md template]
    └──enables──> [/mdf:discuss-class (knows which domains to model)]
    └──enables──> [bridge consistency check in Domain-Verifier]
```

### Dependency Notes

- **YAML Schema required by all MCP tools:** The schema is the contract; tools written before the schema is finalized will need rework. Schema must be built and locked first.
- **Canonical Draw.io Schema required by render/validate/sync:** The bijection constraint must be defined at schema design time. If sync_from_drawio is built before the canonical schema is locked, it becomes an interpretation problem instead of a parse problem.
- **validate_model required by verify-model:** Structural validation is a prerequisite for simulation; simulating a structurally invalid model (unreachable initial state, undefined class in transition) produces meaningless results.
- **discuss-domain required before discuss-class:** Class diagrams belong to domains; without DOMAINS.md established, class diagrams have no home.
- **pycca in YAML enables two paths:** Simulation (verify behavior before code) and code generation (YAML → pycca DSL → pycca compiler → C). Both paths require pycca to be embedded correctly in the schema.

---

## MVP Definition

### Launch With (v1.0 — Milestone 1)

Minimum set that delivers the core value: a verified behavioral model ready for code generation.

- [ ] YAML model schema (classes, associations, state machines, bridges, pycca) — without this nothing else works
- [ ] Canonical Draw.io schema (1:1 with YAML) — required for deterministic sync; define before building render/sync tools
- [ ] read_model, write_model, list_domains — foundational read/write primitives
- [ ] validate_model with graph reachability — structural correctness cannot be delegated to AI review
- [ ] render_to_drawio — visual review before simulation is required in the workflow
- [ ] simulate_state_machine — behavioral verification before code is the core value statement; not optional
- [ ] validate_drawio, sync_from_drawio — closes the visual editing loop; without sync, Draw.io review is read-only and its value drops significantly
- [ ] /mdf:new-project — bootstrap is required for any workflow to start
- [ ] /mdf:discuss-domain, /mdf:discuss-class, /mdf:discuss-state — the three-stage design conversation produces the model
- [ ] /mdf:review-model — surfaces Draw.io for visual review and handles sync-back
- [ ] /mdf:verify-model — Phase 1; the milestone 1 exit criterion
- [ ] /mdf:pause, /mdf:resume — sessions end; without these the workflow is single-session only
- [ ] DOMAINS.md, behavior doc templates — agents need templates to produce consistent artifacts
- [ ] Folder structure bootstrapped by /mdf:new-project — consistent layout required for session-agnostic state reconstruction

### Add After Validation (v1.x — Phase 2 capabilities)

Features that extend the framework after the design→verify loop is proven.

- [ ] /mdf:configure-target — generates execution domain for a specific target; add once the design workflow is stable
- [ ] /mdf:plan-roadmap — GSD handoff; add once target configuration is working
- [ ] TRANSLATION.md template — needed for configure-target; blocked on Phase 2 work

### Future Consideration (v2+)

- [ ] Multi-target support in a single project (submodule orchestration) — deferred until Phase 3 integration is stable
- [ ] Micca DSL output path — Micca is more modern than pycca but tooling is less public-facing; evaluate after pycca path is proven
- [ ] Model diff/merge tooling — useful for multi-session conflict resolution; not needed for single-engineer v1
- [ ] Scrall action language support — Leon Starr's preferred choice; deferred until Scrall tooling matures for C targets

---

## Feature Prioritization Matrix

### Schemas & Templates

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| YAML model schema (core) | HIGH | MEDIUM | P1 |
| Canonical Draw.io schema | HIGH | HIGH | P1 |
| DOMAINS.md template | HIGH | LOW | P1 |
| Behavior doc templates (domain/class/state-machine) | MEDIUM | LOW | P1 |
| TRANSLATION.md template | MEDIUM | MEDIUM | P2 |

### MCP Tools

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| read_model / write_model / list_domains | HIGH | LOW | P1 |
| validate_model (with graph reachability) | HIGH | MEDIUM | P1 |
| render_to_drawio | HIGH | HIGH | P1 |
| simulate_state_machine | HIGH | HIGH | P1 |
| validate_drawio | MEDIUM | MEDIUM | P1 |
| sync_from_drawio | MEDIUM | HIGH | P1 |

### Phase 0 Skills

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| /mdf:new-project | HIGH | LOW | P1 |
| /mdf:discuss-domain | HIGH | MEDIUM | P1 |
| /mdf:discuss-class | HIGH | MEDIUM | P1 |
| /mdf:discuss-state | HIGH | MEDIUM | P1 |
| /mdf:review-model | HIGH | LOW | P1 |
| /mdf:verify-model | HIGH | MEDIUM | P1 |
| /mdf:pause / /mdf:resume | HIGH | LOW | P1 |
| /mdf:configure-target | HIGH | HIGH | P2 |
| /mdf:plan-roadmap | MEDIUM | MEDIUM | P2 |

**Priority key:**
- P1: Must have for Milestone 1
- P2: Phase 2 / configure-target milestone
- P3: v2+ consideration

---

## Cross-Area Dependencies (Schema / MCP / Skills)

These are the critical sequencing constraints between the three feature areas. Violating these in roadmap ordering causes rework.

| Dependency | Explanation |
|------------|-------------|
| Schema must be defined before MCP tools are built | MCP tools are schema-aware; building tools against an undefined schema means rewriting them when the schema stabilizes |
| Canonical Draw.io schema must be locked before render_to_drawio is implemented | render_to_drawio produces Draw.io XML; if the schema changes after implementation, every generated file becomes invalid |
| validate_model must exist before any skill calls it | /mdf:discuss-domain (via Domain-Verifier) calls validate_model; the Domain-Verifier chain depends on MCP tools being available |
| YAML read/write primitives must exist before stage skills | /mdf:discuss-domain writes DOMAINS.md and behavior docs; write_model is how model files are persisted from agent output |
| simulate_state_machine must exist before /mdf:verify-model | /mdf:verify-model is the Milestone 1 exit criterion; blocking on simulation being complete |
| render_to_drawio must exist before /mdf:review-model | /mdf:review-model calls render_to_drawio to surface Draw.io files |

---

## Sources

- `.planning/PROJECT.md` — requirements, key decisions, constraints (HIGH confidence)
- `docs/plans/2026-03-05-mdf-development-workflow.md` — Phase 0–2 workflow design, agent responsibilities, skill list (HIGH confidence)
- `docs/plans/2026-03-04-model-based-project-framework-design.md` — MCP tool design, YAML schema examples, approach rationale (HIGH confidence)
- `.planning/GUIDELINES.md` — MCP tool design principles, skill design principles, YAML conventions (HIGH confidence)
- `docs/plans/milestone2-flow.md` — Phase 3+ agent analysis, GSD integration contract (HIGH confidence)

---

*Feature research for: Model-Driven Framework (MDF) v1.0 — Schemas, MCP Server, Phase 0 Skills*
*Researched: 2026-03-05*
