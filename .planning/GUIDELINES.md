# Engineering Guidelines: Model-Based Project Framework

These guidelines capture the architectural intuitions, conventions, and design principles that shape *how* this project is built. They apply to MCP tool design, skill design, and the YAML model format.

---

## MCP Tool Design Principles

### Tool descriptions are prompts
The `description` field of each MCP tool is what Claude reads when deciding which tool to call. Write descriptions as prompts — specific, with context about when to use this tool vs. a similar one. Avoid generic labels.

```
# Bad
description: "Write model"

# Good
description: "Save and validate a domain YAML model. Call after any structural change. Returns validation errors if present."
```

### Small, composable tools over large multipurpose ones
Claude selects tools by name and description. A tool with many modes (`manage_model(action="render")`) is harder to select correctly than two dedicated tools (`write_model`, `render_to_drawio`). Keep each tool doing one thing.

### Errors must guide recovery
When a tool fails, the error message is Claude's only signal. Make errors actionable — include what was wrong, where it is, and what valid options are.

```
# Bad
"KeyError: Controller"

# Good
"Class 'Controller' not found in domain 'motor'. Available classes: ['Motor', 'Sensor', 'Actuator']"
```

### Every mutation must be inspectable
After any write operation, Claude should be able to verify state with a read operation. Tools that mutate silently make debugging across sessions very hard. Design write→read as a verifiable pair.

### Idempotent operations where possible
Claude retries when uncertain. If calling `render_to_drawio` twice produces the same output, that's safe. Avoid tools that append, duplicate, or accumulate on repeated calls.

### Return only what's needed
Claude works in a context window. `read_model(domain)` returns one domain's YAML — not the entire model. `list_domains()` returns names — not full content. Design for progressive disclosure: survey first, drill in on demand.

### Validation output is a list, not a boolean
`validate_model` must return a list of specific, fixable issues — not pass/fail. Claude needs to address each issue in turn.

```json
[
  {"issue": "Undefined class reference", "location": "associations[0].to", "value": "Controler", "fix": "Did you mean 'Controller'?"},
  {"issue": "Unreachable state", "location": "Motor.state_machine.states[2]", "value": "Fault", "fix": "No transition leads to 'Fault'"}
]
```

### `validate_model` must include graph reachability checks
State machine behavioral completeness is a graph problem, not an AI problem. `validate_model` must perform:
- **Reachability**: BFS/DFS from the initial state — any state not visited is dead (unreachable)
- **Trap detection**: Any state with no outgoing transitions that is not declared terminal is a trap state
- **Event coverage**: For each state, list events with no handler (informational — not always an error)

These are deterministic checks computable from the YAML alone. They do not require simulation.

---

## Skill Design Principles

### Skills are the UX layer; MCP tools are primitives
MCP tools are generic and reusable. The skill (`/design:start`) is where sequencing, questioning, and workflow logic lives. Keep tools dumb and skills smart. This separation lets the skill evolve without touching the MCP package.

### Ask engineering questions GSD doesn't ask
GSD asks product questions: "what do you want to build?" and "who is it for?" This framework's skill must ask the engineering questions GSD skips:
- What are the domains / subsystems?
- What classes exist in each domain?
- What attributes and methods does each class have?
- What are the associations between classes (multiplicity, verb phrase)?
- Which classes have state machines? What are the states and transitions?
- What are the interfaces between subsystems?

### Guidelines checker agent follows the GSD plan-checker pattern
Soft guidelines adherence cannot be mechanically enforced, but it can be reviewed by an agent. After each phase execution, a guidelines checker agent reads `GUIDELINES.md` and the produced code/plans and verifies adherence — the same pattern GSD uses for plan checking (agent reviews plan against phase goals). This is composable with GSD's existing verification hooks, not a new invention.

### Design for session boundaries
Claude loses context between conversations. Every skill should assume it may be resumed in a fresh session. The YAML files on disk are the source of truth — the skill should always start by calling `list_domains()` to reconstruct current state.

---

## YAML Model Conventions

### One file per domain subsystem
Never load the entire model in one call. Keep domains small enough that their YAML fits comfortably in context alongside the conversation.

### Follow xUML / Shlaer-Mellor conventions
- Identifiers marked with `identifier: true`
- Associations carry verb phrases and multiplicity
- State machines declare initial state, states list, and transitions with guards and actions
- Stereotypes: `entity`, `associative`, `active`
- Domain bridges declared explicitly — `from`, `to`, `operation`, `params`, `direction` (required/provided)

### Action language: pycca
Method bodies and transition actions are expressed in pycca action language syntax, embedded as YAML string blocks. This enables:
- Simulation via `simulate_state_machine` (event sequence → execution trace)
- Code generation via YAML → pycca DSL → pycca compiler → C

Pycca was chosen over Scrall because the target implementation language is C and pycca's action language maps directly to embedded C semantics.

### Draw.io schema must be canonical (1:1 constraint)
The YAML ↔ Draw.io conversion must be a bijection — not an approximation. This requires defining a canonical Draw.io schema at design time:
- Each semantic element maps to a specific shape type (class = rectangle with stereotype label, association = connector with verb phrase + multiplicity labels, state = rounded rectangle, transition = directed edge with guard/action label)
- No freeform shapes that lack a YAML equivalent
- `sync_from_drawio` is a structured schema-aware parse, not an interpretation problem

If the canonical schema is maintained, `sync_from_drawio` is deterministic. The 1:1 constraint must be enforced at schema design time — once defined, round-trip fidelity is a property of the schema, not a runtime concern.

### Structural equality, not byte equality
When validating round-trips, check semantic equivalence — not byte equality:
- Same set of classes
- Same attributes and method signatures per class
- Same associations (endpoints, multiplicity, verb phrase)
- Same state machine topology (states and transitions — ignore layout, style, order)

Layout, color, and ordering are presentation concerns and must never be treated as semantic.

---

## Soft Guidelines Document Template

When producing a guidelines document for a project using this framework, use this structure. Any section may be skipped if not applicable; any section may be added if needed.

```markdown
# Engineering Guidelines: [Project Name]

## Architecture
[Subsystem boundaries, layer responsibilities, what talks to what]

## Coding Conventions
[Naming, file structure, module organization, formatting rules]

## Anti-Patterns
[Things to explicitly avoid, with reasoning]

## Technology Choices
[Selected libraries/tools and why; what was rejected and why]

## Non-Functional Requirements
[Performance targets, extensibility expectations, memory constraints, etc.]

## Domain Model Notes
[Any conventions specific to the YAML model for this project]
```

---

*Last updated: 2026-03-04 after design review — graph reachability, canonical Draw.io schema, guidelines checker agent pattern*
