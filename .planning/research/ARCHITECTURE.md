# Architecture Research

**Domain:** MCP-backed model-driven design framework (MDF v1.0)
**Researched:** 2026-03-05
**Confidence:** HIGH — derived directly from design documents and design decisions already locked

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SKILL LAYER (UX)                            │
│  /mdf:new-project  /mdf:discuss-domain  /mdf:discuss-class          │
│  /mdf:discuss-state  /mdf:review-model  /mdf:verify-model           │
│  /mdf:configure-target  /mdf:pause  /mdf:resume  /mdf:plan-roadmap  │
│  — .claude/skills/mdf/*.md files, invoked by Claude Code —          │
├─────────────────────────────────────────────────────────────────────┤
│                        AGENT LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │Domain Arch.  │  │Class Diagram │  │State Diagram │              │
│  │ Researcher   │  │    Agent     │  │    Agent     │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Domain      │  │  Sim. Test   │  │  Execution   │              │
│  │  Verifier    │  │  Generator   │  │  Domain Agt. │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│   — spawned by skills; agents call MCP tools —                      │
├─────────────────────────────────────────────────────────────────────┤
│                    MCP SERVER (Primitive Tools)                       │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │list_domains│  │read_model  │  │write_model  │  │validate_    │  │
│  │            │  │(domain)    │  │(domain,yaml)│  │model(domain)│  │
│  └────────────┘  └────────────┘  └─────────────┘  └─────────────┘  │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │render_to_  │  │validate_   │  │sync_from_   │  │simulate_    │  │
│  │drawio(dom) │  │drawio(dom) │  │drawio(dom)  │  │state_machine│  │
│  └────────────┘  └────────────┘  └─────────────┘  └─────────────┘  │
│   — Python/FastMCP; standalone package in this repo —               │
├─────────────────────────────────────────────────────────────────────┤
│                     PERSISTENCE LAYER                                │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   .design/model/         │  │   .design/behavior/             │  │
│  │   <domain>/              │  │   <domain>/domain.md            │  │
│  │     class-diagram        │  │   <domain>/<class>.md           │  │
│  │     state-diagrams/      │  │   <domain>/<state-machine>.md   │  │
│  │   DOMAINS.md             │  └─────────────────────────────────┘  │
│  └──────────────────────────┘                                        │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐  │
│  │   .design/research/      │  │   .planning/                    │  │
│  │   FEATURES.md PITFALLS   │  │   PROJECT.md ROADMAP.md         │  │
│  │   STACK.md SUMMARY.md    │  │   STATE.md GUIDELINES.md        │  │
│  │   TRANSLATION.md         │  └─────────────────────────────────┘  │
│  └──────────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| Skills (`/mdf:*`) | UX + workflow sequencing; ask engineering questions, invoke agents, manage session resume | `.claude/skills/mdf/*.md` Markdown skill files |
| Agents | Reasoning over model content; domain questioning, class elicitation, consistency checking | Spawned subagents within skill execution |
| MCP Server | Primitive I/O: YAML CRUD, Draw.io rendering, graph validation, simulation | Python/FastMCP package in `mdf-server/` |
| YAML model files | Single source of truth per domain; one file per subsystem | `.design/model/<domain>/` |
| Draw.io files | Human-facing presentation view only; derived from YAML, never authoritative | `.design/model/<domain>/class-diagram`, `state-diagrams/` |
| Behavior docs | Narrative behavioral specs at domain/class/state-machine granularity | `.design/behavior/<domain>/` |
| `.planning/` | GSD artifacts + GUIDELINES.md; unchanged GSD layout | Standard GSD structure |

---

## Recommended Project Structure

```
model-based-project-framework/
├── mdf-server/                  # Standalone Python/FastMCP MCP package
│   ├── pyproject.toml           # Package definition + dependencies
│   ├── mdf_server/
│   │   ├── __init__.py
│   │   ├── server.py            # FastMCP app; tool registrations
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── model_io.py      # list_domains, read_model, write_model
│   │   │   ├── drawio.py        # render_to_drawio, validate_drawio, sync_from_drawio
│   │   │   ├── validation.py    # validate_model (graph reachability, structural checks)
│   │   │   └── simulation.py    # simulate_state_machine (pycca interpreter)
│   │   ├── schema/
│   │   │   ├── yaml_schema.py   # Pydantic models for YAML domain schema
│   │   │   ├── drawio_schema.py # Canonical Draw.io element definitions
│   │   │   └── validators.py    # Graph traversal, reachability, trap detection
│   │   └── pycca/
│   │       ├── __init__.py
│   │       ├── parser.py        # pycca action language parser
│   │       └── interpreter.py   # Event-driven execution for simulation
│   └── tests/
│       ├── test_model_io.py
│       ├── test_drawio_roundtrip.py
│       ├── test_validation.py
│       └── test_simulation.py
│
├── .claude/
│   └── skills/
│       └── mdf/
│           ├── new-project.md       # Bootstrap .planning/ + .design/; kick off Stage 1
│           ├── discuss-domain.md    # Stage 1: domain questioning → DOMAINS.md
│           ├── discuss-class.md     # Stage 2: class diagram elicitation
│           ├── discuss-state.md     # Stage 3: state diagram elicitation
│           ├── review-model.md      # Human review gate before simulation
│           ├── verify-model.md      # Phase 1: simulation test generation + execution
│           ├── configure-target.md  # Phase 2: execution domain + TRANSLATION.md
│           ├── plan-roadmap.md      # Produce GSD-compatible ROADMAP.md from model
│           ├── pause.md             # Session boundary: save current state
│           ├── resume.md            # Session resume: reconstruct via list_domains()
│           ├── discuss-phase.md     # Phase 3+: model-aware CONTEXT.md (wraps GSD)
│           ├── plan-phase.md        # Phase 3+: model-aware planner (wraps GSD)
│           ├── execute-phase.md     # Phase 3+: + guidelines checker (wraps GSD)
│           ├── verify-work.md       # Phase 3+: model conformance check (wraps GSD)
│           ├── complete-milestone.md
│           ├── new-milestone.md
│           └── update-model.md      # Reactive: model corrections and scope changes
│
├── templates/
│   ├── DOMAINS.md.tmpl          # Domain map template
│   ├── CLASS_DIAGRAM.yaml.tmpl  # Class diagram YAML template
│   ├── STATE_DIAGRAM.yaml.tmpl  # State diagram YAML template
│   ├── behavior-domain.md.tmpl  # Domain behavioral spec template
│   ├── behavior-class.md.tmpl   # Class behavioral spec template
│   ├── behavior-state.md.tmpl   # State machine behavioral spec template
│   └── TRANSLATION.md.tmpl      # Model-to-code mapping template
│
├── docs/
│   └── plans/                   # Design documents (existing)
│
└── .planning/                   # GSD planning artifacts (existing)
    ├── PROJECT.md
    ├── GUIDELINES.md
    ├── ROADMAP.md               # Created at end of Phase 0
    ├── STATE.md
    └── research/
```

**Note on `.design/` location:** `.design/` is created at project root by `/mdf:new-project` at runtime — it is not part of the MDF repo itself. The MDF repo provides the tooling (`mdf-server/`, `.claude/skills/mdf/`, `templates/`); `.design/` is the design workspace output for each project that uses MDF.

### Structure Rationale

- **`mdf-server/`:** Self-contained Python package; can be installed via `pip install -e ./mdf-server` or registered as an MCP server without touching project files.
- **`mdf_server/tools/`:** One module per capability group; matches the tool granularity principle (small composable tools). `model_io.py` is the foundation — all other tools depend on the YAML schema it enforces.
- **`mdf_server/schema/`:** Schema definitions are the contract between YAML and Draw.io. They are written once and referenced by all tools. Pydantic models serve double duty as validation and serialization.
- **`mdf_server/pycca/`:** Isolated parser + interpreter. The parser is needed by both `simulation.py` (runtime) and `validation.py` (static action syntax checks). Keeping it separate avoids circular imports.
- **`.claude/skills/mdf/`:** Skills live in the project repo's `.claude/` directory, scoped to this project. They are the evolving UX layer — they change without touching `mdf-server/`.
- **`templates/`:** Human-readable scaffolding for artifacts that agents produce. Agents fill templates; engineers review them. Keeping templates in the repo means they version alongside the schema.

---

## Architectural Patterns

### Pattern 1: Schema-First Design (Build Order Constraint)

**What:** The YAML schema and canonical Draw.io schema must be designed and frozen before any MCP tool is implemented. Every tool, agent, and skill depends on the schema. This is a hard dependency.

**When to use:** Always — this is the foundational constraint for Milestone 1 Phase 1.

**Trade-offs:** Schema changes after tools are built require updating tools, tests, and potentially existing model files. Invest time in schema design upfront to minimize churn.

**Build order implication:**
```
1. YAML schema (Pydantic models in yaml_schema.py)
   ↓
2. model_io.py (read/write using schema)
   ↓
3. validate_model (structural checks, graph reachability)
   ↓
4. drawio_schema.py (canonical element definitions)
   ↓
5. render_to_drawio (YAML → Draw.io using canonical schema)
   ↓
6. validate_drawio + sync_from_drawio (round-trip)
   ↓
7. pycca parser + simulation
   ↓
8. Skills + agents (depend on all tools being available)
```

### Pattern 2: Read-Reconstruct on Session Resume

**What:** Every skill begins by calling `list_domains()` and selectively calling `read_model(domain)` for relevant domains. Skills never assume in-memory state survives between sessions.

**When to use:** At the start of every skill invocation, unconditionally.

**Trade-offs:** Adds one tool call per session start (negligible). Eliminates an entire class of bugs where stale in-session state drives incorrect model edits.

**Example (skill preamble pattern):**
```markdown
## Session Initialization

Before any action, reconstruct current state from disk:
1. Call list_domains() — get all domain names
2. For the domain being worked on, call read_model(domain)
3. If resuming after /mdf:pause, also read DOMAINS.md to locate the checkpoint
```

### Pattern 3: Validate-After-Write

**What:** Every `write_model()` call is immediately followed by `validate_model()`. The tool description for `write_model` should instruct Claude to do this automatically: "Save and validate a domain YAML model. Call after any structural change. Returns validation errors if present."

**When to use:** After every mutation. After `sync_from_drawio`. After agent edits.

**Trade-offs:** Doubles the tool calls for write operations; catches errors before they propagate across sessions. Correct trade-off for a design tool.

### Pattern 4: Bijective YAML ↔ Draw.io Schema

**What:** The canonical Draw.io schema maps each YAML element type to exactly one Draw.io shape type with fixed style attributes. No YAML element renders to multiple possible shapes; no Draw.io shape parses to ambiguous YAML.

**When to use:** Applied at schema design time. `render_to_drawio` and `sync_from_drawio` both enforce this schema — they are inverse functions of each other.

**Canonical mappings (design-time decision):**

| YAML Element | Draw.io Shape | Required Labels |
|-------------|--------------|-----------------|
| Class | Rectangle with stereotype header | Name, stereotype (`<<entity>>` / `<<associative>>` / `<<active>>`) |
| Attribute | Text row inside class rectangle | Name, type, `[I]` if identifier |
| Association | Connector (orthogonal) | Verb phrase label (center), multiplicity labels (each end) |
| State | Rounded rectangle | Name |
| Transition | Directed edge | `event [guard] / action` label |
| Initial pseudostate | Filled circle | None |
| Terminal state | Circle-in-circle | None |
| Domain bridge | Dashed connector crossing domain boundary | Operation name, direction arrow |

**Trade-offs:** Restricts Draw.io visual freedom. This is intentional — free-form shapes break `sync_from_drawio`. Engineers who want visual customization should customize style (color, font) not shape type.

### Pattern 5: Tools Are Dumb; Skills Are Smart

**What:** MCP tools perform single, deterministic operations (read, write, validate, render, simulate). All workflow logic, questioning sequences, decision trees, and multi-step orchestration live in skills and agents.

**When to use:** When deciding where logic belongs. If it involves "what to do next" — skill. If it involves "operate on the model" — tool.

**Trade-offs:** Skills are Markdown files that evolve quickly; tools are Python code that evolve slowly. This separation means tool releases don't block skill iteration.

---

## Data Flow

### Primary Design Flow (Phase 0)

```
Engineer intent (conversation)
    ↓
Skill (/mdf:discuss-domain) spawns Domain Architect agent
    ↓
Agent asks engineering questions → receives answers
    ↓
Agent calls write_model(domain, yaml) for each domain
    ↓
MCP server validates YAML against schema
    ↓
Agent calls validate_model(domain) → receives issue list
    ↓
Agent resolves issues → calls write_model again
    ↓
Agent calls render_to_drawio(domain) → receives Draw.io XML
    ↓
MCP writes .design/model/<domain>/class-diagram
    ↓
Engineer reviews in Draw.io (visual gate)
    ↓
Engineer edits in Draw.io (optional)
    ↓
Skill calls sync_from_drawio(domain, xml) → YAML updated
    ↓
validate_model(domain) runs → YAML is source of truth again
```

### Simulation Flow (Phase 1)

```
Behavior docs (.design/behavior/)
    ↓
Simulation Test Generator agent reads domain.md + class.md + state-machine.md
    ↓
Agent produces test cases: (class, event_sequence, expected_trace)
    ↓
Agent calls simulate_state_machine(class, events) for each test
    ↓
MCP server: parses pycca actions from YAML → executes event sequence
    ↓
Returns execution trace (state transitions, action calls, attribute changes)
    ↓
Agent compares trace against expected behavioral spec
    ↓
Reports: pass / fail with specific deviation per behavioral spec
```

### YAML → Draw.io Render Flow

```
read_model(domain) → YAML dict
    ↓
yaml_schema.py: validate + deserialize to typed objects
    ↓
drawio_schema.py: map each typed object to canonical Draw.io element
    ↓
Assign stable element IDs (deterministic: domain:class:attribute)
    ↓
Generate Draw.io XML with auto-layout hints
    ↓
Return XML string → skill writes to .design/model/<domain>/
```

### Draw.io → YAML Sync Flow (sync_from_drawio)

```
Draw.io XML input
    ↓
drawio_schema.py: parse by shape type (schema-aware, not interpretation)
    ↓
Extract typed objects: classes, attributes, associations, states, transitions
    ↓
Check: every Draw.io element maps to known canonical type
    ↓  (error if unknown shape found — enforces 1:1 constraint)
yaml_schema.py: serialize typed objects to YAML dict
    ↓
Write to .design/model/<domain>/ YAML files
    ↓
validate_model(domain) runs automatically → return issue list
```

### Key Data Flows Summary

1. **Write → Validate:** Every `write_model` triggers `validate_model`; errors returned as structured issue list, never exceptions.
2. **Session start → Reconstruct:** Every skill calls `list_domains()` first; reads only domains needed for current task.
3. **Draw.io → YAML → Draw.io:** Round-trip must preserve semantic equivalence (same classes, associations, state topology), not byte equality. Layout and style attributes are not round-tripped.
4. **Behavior docs → Simulation → Pass/Fail:** Test generation is driven by behavior specs; inputs enter only through realized domain bridges.

---

## Integration Points

### MCP Server ↔ Skills Interface

The MCP tool contract is the primary integration boundary. Skills call tools by name via the MCP protocol; tool descriptions are the API contract.

| Tool | Called By | Returns | Error Behavior |
|------|-----------|---------|----------------|
| `list_domains()` | Every skill on start | `[str]` — domain names | Empty list if `.design/model/` not initialized |
| `read_model(domain)` | Domain Architect, Class/State agents, Verifier | YAML string | Error if domain not found; lists available domains |
| `write_model(domain, yaml)` | Domain Architect, Class/State agents | Validation issue list | Schema error if YAML malformed |
| `validate_model(domain)` | Domain Verifier, post-write | `[{issue, location, value, fix}]` | Never throws; always returns list (may be empty) |
| `render_to_drawio(domain)` | Review skill, post-write | Draw.io XML string | Error if YAML not yet valid |
| `validate_drawio(domain, xml)` | Review skill (before sync) | `[{issue, element_id, shape_type}]` | Error if unknown shape types found |
| `sync_from_drawio(domain, xml)` | Review skill (after engineer edits) | Validation issue list | Error if non-canonical shapes present |
| `simulate_state_machine(class, events)` | Simulation Test Generator | Execution trace `[{event, from_state, to_state, actions_executed}]` | Error if class not found or pycca parse fails |

### Skills ↔ GSD Integration (Phase 3+)

| MDF Skill | GSD Equivalent | Integration Mode | What Changes |
|-----------|---------------|-----------------|--------------|
| `/mdf:discuss-phase` | `/gsd:discuss-phase` | Full replacement | Phase Researcher reads model; produces model-aware CONTEXT.md with `<model_context>` section |
| `/mdf:plan-phase` | `/gsd:plan-phase` | Wrapper | Receives model-aware CONTEXT.md; GSD planner runs unchanged |
| `/mdf:execute-phase` | `/gsd:execute-phase` | Wrapper + injection | Guidelines Checker agent added per executor chunk in `config.json` |
| `/mdf:verify-work` | `/gsd:verify-work` | Wrapper | GSD verifier + model conformance cross-reference |
| `/mdf:complete-milestone` | `/gsd:complete-milestone` | Thin wrapper | Preserves GSD behavior; adds model archive step |
| `/mdf:new-milestone` | `/gsd:new-milestone` | Thin wrapper | Bootstraps new `.design/` context if multi-milestone model evolves |

### CLAUDE.md Injection (Model Context for GSD Agents)

GSD agents (`gsd-executor`, `gsd-planner`, `gsd-plan-checker`, `gsd-verifier`) pick up model context via CLAUDE.md injection in the project root. MDF appends model reference instructions that tell GSD agents to load relevant domain YAML before implementing or reviewing code. This is the "zero modification to GSD" integration strategy.

```
CLAUDE.md (project root) contains:
  "When implementing any task, first call read_model(<relevant_domain>)
   to load the domain model. All class names, attributes, associations,
   and state machines in the implementation must conform to the model."
```

### config.json Extensions

The project `config.json` is extended to register the Guidelines Checker agent alongside existing GSD workflow agents. GSD's `execute-phase` reads `config.json` to discover which agents to spawn per executor chunk.

```json
{
  "agents": {
    "guidelines_checker": {
      "enabled": true,
      "trigger": "post_executor_chunk",
      "skill": ".claude/skills/mdf/guidelines-checker.md"
    }
  }
}
```

### Internal Module Boundaries (mdf-server)

| Boundary | Communication | Notes |
|----------|--------------|-------|
| `server.py` ↔ `tools/model_io.py` | Direct function calls | `server.py` is thin; all logic in tool modules |
| `tools/drawio.py` ↔ `schema/drawio_schema.py` | Import | `drawio_schema.py` owns all shape-to-YAML mappings |
| `tools/validation.py` ↔ `schema/validators.py` | Import | Graph traversal algorithms isolated in `validators.py` |
| `tools/simulation.py` ↔ `pycca/` | Import | Parser and interpreter are separate; parser is also used by `validation.py` for static syntax checks |
| `tools/model_io.py` ↔ `schema/yaml_schema.py` | Import | All read/write passes through Pydantic models; raw dict never returned to caller |

---

## Scaling Considerations

This is a single-engineer tool with no multi-user or scale concerns. The relevant growth dimension is model complexity (number of domains, classes, state machines).

| Model Scale | Architecture Adjustment |
|-------------|------------------------|
| 1-3 domains | Single session easily handles full model; `list_domains()` + targeted reads sufficient |
| 4-10 domains | Domain-by-domain processing matters; `read_model(domain)` one at a time pattern becomes important |
| 10+ domains | May need simulation partitioned by domain; bridge validation becomes the critical path |

**Primary complexity bottleneck:** `simulate_state_machine` with large pycca action bodies. The pycca interpreter must handle loops and conditional branches; this is where execution time grows. Partition simulation by class, not by domain.

---

## Anti-Patterns

### Anti-Pattern 1: Loading the Entire Model at Once

**What people do:** Read all domain YAML files at session start and hold everything in context.

**Why it's wrong:** Defeats the one-file-per-domain design; bloats context; makes session resume from checkpoint fragile.

**Do this instead:** Call `list_domains()` at start; call `read_model(domain)` only for the domain currently being worked on. Treat domain boundaries as context isolation boundaries.

### Anti-Pattern 2: Writing Draw.io as Source of Truth

**What people do:** Have the engineer edit Draw.io and treat those edits as canonical, skipping `sync_from_drawio`.

**Why it's wrong:** Draw.io layout state diverges from YAML; `validate_model` operates on YAML only; simulation runs on YAML only. The Draw.io file becomes a lie.

**Do this instead:** Engineer edits Draw.io; skill calls `sync_from_drawio` → YAML is updated → `validate_model` confirms structural correctness. YAML is always the runtime representation.

### Anti-Pattern 3: Free-Form Draw.io Shapes

**What people do:** Engineer adds decorative shapes, callout boxes, or custom connectors in Draw.io to annotate the diagram.

**Why it's wrong:** `sync_from_drawio` encounters unknown shape types and either fails or silently drops them. Annotations are lost on next `render_to_drawio` call.

**Do this instead:** Annotations belong in behavior docs (`.design/behavior/`), not in Draw.io. If a shape isn't in the canonical schema, it isn't a model element.

### Anti-Pattern 4: Multi-Purpose MCP Tools

**What people do:** Create `manage_model(action="read" | "write" | "validate")` to reduce tool count.

**Why it's wrong:** Claude selects tools by description; a tool with modes is harder to select correctly than three dedicated tools. Error messages from multi-mode tools are harder to recover from.

**Do this instead:** One tool per operation. `read_model`, `write_model`, `validate_model` are three tools, not one.

### Anti-Pattern 5: Skill Logic in MCP Tools

**What people do:** Embed questioning sequences, decision trees, or "if no YAML exists, create a template" logic in tool implementations.

**Why it's wrong:** Skills evolve fast; tools should evolve slowly. Business logic in tools creates tight coupling. Tool changes require `pip install` redeployment; skill changes are just file edits.

**Do this instead:** Tools do exactly one thing deterministically. Skills handle "what to do if" branching. If a tool needs context about what the engineer wants, that context belongs in the skill's agent prompt, not the tool.

### Anti-Pattern 6: Skipping validate_model After sync_from_drawio

**What people do:** Trust that `sync_from_drawio` produced a valid model because the Draw.io diagram "looked right."

**Why it's wrong:** The engineer may have introduced structural issues during Draw.io editing (deleted a class that associations reference, renamed a state that transitions reference). `sync_from_drawio` is a parse operation, not a validation.

**Do this instead:** `sync_from_drawio` always returns a validation issue list (by calling `validate_model` internally). Skills must surface these issues to the engineer before continuing.

---

## Sources

- Design decisions locked in `docs/plans/2026-03-05-mdf-development-workflow.md` — HIGH confidence (primary source)
- `.planning/GUIDELINES.md` — MCP tool design principles, YAML conventions, Draw.io schema requirements — HIGH confidence
- `.planning/PROJECT.md` — requirements, constraints, key decisions — HIGH confidence
- FastMCP documentation: https://gofastmcp.com — tool registration patterns (verified via design doc technology choice)
- GSD `config.json` template and `execute-phase.md` workflow — HIGH confidence (direct inspection)

---
*Architecture research for: Model-Driven Framework (MDF) v1.0*
*Researched: 2026-03-05*
