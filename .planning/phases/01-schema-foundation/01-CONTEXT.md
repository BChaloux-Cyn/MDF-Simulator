# Phase 1: Schema Foundation - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Define all locked, versioned contracts for the MDF toolchain: the YAML model schema (Pydantic), canonical Draw.io bijection, and artifact templates. Every tool, agent, and skill in Phases 2-10 depends on these schemas — changes after Phase 1 require cascading updates across all consumers.

</domain>

<decisions>
## Implementation Decisions

### File Structure

The domain model is split across multiple YAML files per domain (not one monolithic file):

```
.design/model/<domain>/
  types.yaml          # Custom type definitions for this domain
  class-diagram.yaml  # Classes, attributes, associations, bridges, subtype partitions
  state-diagrams/
    <ClassName>.yaml  # One file per class with a state machine (exact class name)
.design/model/
  DOMAINS.yaml        # Top-level domain map (replaces DOMAINS.md from TMPL-01)
```

- `read_model(domain)` reads `class-diagram.yaml`
- `read_state_machine(domain, class)` reads `state-diagrams/<ClassName>.yaml`
- Two distinct MCP tool variants — not a single tool with a type flag
- Associations live inside `class-diagram.yaml` (not a separate file)
- Bridge signatures declared once in `DOMAINS.yaml` — single source of truth
- Requiring domain's `class-diagram.yaml` lists operation names only
- Providing domain's `class-diagram.yaml` contains `implementations` with pycca action bodies

### Schema Versioning

- All YAML files include `schema_version` as the first field
- Format: semantic version string, e.g., `schema_version: "1.0.0"`
- Pydantic validates it matches semver pattern
- Applies to: `DOMAINS.yaml`, `types.yaml`, `class-diagram.yaml`, all `state-diagrams/<ClassName>.yaml`

### DOMAINS.yaml

Replaces the originally specified `DOMAINS.md` — machine-parseable, schema-versioned. **Single source of truth for bridge signatures.** Both requiring and providing domains reference operations by name; signatures are declared here only.

```yaml
schema_version: "1.0.0"
domains:
  - name: Hydraulics
    type: application        # application | realized
    description: Controls valve sequencing and pressure management
  - name: Timer
    type: realized
    description: Wraps OS timer primitives
bridges:
  - from: Hydraulics
    to: Timer
    operations:
      - name: start_timer
        params:
          - name: duration
            type: Integer
        return: UniqueID
      - name: cancel_timer
        params:
          - name: timer_id
            type: UniqueID
        return: null
```

Fields: `schema_version`, `domains` (name, type, description), `bridges` (from, to, operations with full signatures). No status field.

### Primitive Types

Standard xtUML primitive types:

| Type | Description |
|------|-------------|
| `Boolean` | true/false |
| `Integer` | whole numbers |
| `Real` | floating point |
| `String` | character sequence |
| `UniqueID` | implementation-defined unique instance identifier |

Note: pycca compiler equivalents need verification against repos.modelrealization.com documentation before Phase 3. TRANSLATION.md (Phase 2+) maps these to target-specific C/pycca types.

### types.yaml

Domain-scoped custom type definitions. Supports three base categories:

**Scalar (base primitive + optional constraints):**
```yaml
schema_version: "1.0.0"
domain: Hydraulics

types:
  - name: Pressure
    base: Real
    units: Pascal
    range: [0.0, 5000.0]
    description: Hydraulic pressure in Pascal
  - name: ValveID
    base: UniqueID
    description: Unique identifier for a valve instance
```

**Enumeration:**
```yaml
  - name: ValveMode
    base: enum
    values: [Manual, Automatic, Maintenance]
    description: Operating mode of a valve
```

**Structure:**
```yaml
  - name: SensorReading
    base: struct
    description: A timestamped sensor value
    fields:
      - name: timestamp
        type: Integer
      - name: value
        type: Pressure
      - name: valid
        type: Boolean
```

All fields except `name` and `base` are optional.

### class-diagram.yaml

**Classes:**
```yaml
schema_version: "1.0.0"
domain: Hydraulics

classes:
  - name: Valve
    stereotype: entity        # entity | active | associative
    attributes:
      - name: valve_id
        type: ValveID
        identifier: true
      - name: position
        type: Real
        identifier: false
      - name: actuator_id     # referential attribute formalizing R1
        type: UniqueID
        identifier: false
        referential: R1
    methods:
      - name: open
        scope: instance       # instance | class
        params:
          - name: target_position
            type: Real
        return: null
        action: |
          self.position = target_position;
          generate PositionChanged to SELF;
      - name: create
        scope: class
        params:
          - name: valve_id
            type: ValveID
        return: Valve
        action: |
          create object of Valve;
```

**Associations (bidirectional, symmetric):**
```yaml
associations:
  - name: R1
    point_1: Valve
    point_2: ActuatorPosition
    1_mult_2: "1..M"        # from one Valve, how many ActuatorPositions
    2_mult_1: "1"            # from one ActuatorPosition, how many Valves
    1_phrase_2: "controls"
    2_phrase_1: "is controlled by"
```

Multiplicity values: `"1"`, `"1..M"`, `"0..1"`, `"M"` (string notation).

**Subtype partitions:**
```yaml
  - name: Actuator
    stereotype: entity
    attributes:
      - name: actuator_id
        type: UniqueID
        identifier: true
      - name: actuator_type
        type: ActuatorType   # enum defined in types.yaml
    partitions:
      - name: R2
        discriminator: actuator_type
        subtypes: [Valve, Motor]

  - name: Valve
    stereotype: active
    specializes: R2
    attributes:
      - name: stroke_count
        type: Integer
```

Rules:
- Supertype can be `entity` or `active` (active = has state machine)
- If subtype declares its own state diagram, it **overrides** the supertype's completely
- If subtype has no state diagram, it **inherits** the supertype's state machine
- Validator flags if a subtype is `active` but has neither its own nor an inherited state machine

**Associative classes:**
```yaml
  - name: ValveAssignment
    stereotype: associative
    formalizes: R1            # R-number of the association this class formalizes
    attributes:
      - name: assigned_at
        type: Integer
```

**Bridges — requiring domain** (Hydraulics calls Timer):
```yaml
bridges:
  - to_domain: Timer
    direction: required
    operations: [start_timer, cancel_timer]   # names only — signatures in DOMAINS.yaml
```

**Bridges — providing domain** (Timer implements the operations):
```yaml
bridges:
  - to_domain: Hydraulics
    direction: provided
    implementations:
      - name: start_timer
        action: |
          create object of TimerInstance;
          self.timer_id = generate_id();
      - name: cancel_timer
        action: |
          delete object of TimerInstance where timer_id = rcvd_evt.timer_id;
```

Rules:
- Signatures (name, params, return) declared once in DOMAINS.yaml — never repeated in class-diagram.yaml
- Requiring domain lists operation names only; `validate_model` checks they exist in DOMAINS.yaml
- Providing domain supplies a pycca `action` body per operation in an `implementations` block
- `validate_model` cross-checks that every operation declared in DOMAINS.yaml for a bridge has a matching implementation in the providing domain's file

### state-diagrams/<ClassName>.yaml

```yaml
schema_version: "1.0.0"
domain: Hydraulics
class: Valve

events:
  - name: Open
    params:
      - name: target_position
        type: Real
  - name: Close
    params: []
  - name: Timeout
    params: []

states:
  - name: Idle
    entry_action: null
  - name: Opening
    entry_action: |
      self.target = rcvd_evt.target_position;
      Timer::start_timer[timeout_ms];

transitions:
  - from: Idle
    to: Opening
    event: Open
    guard: "self.pressure < max_pressure"
    action: null
  - from: Idle
    to: Faulted
    event: Open
    guard: "self.pressure >= max_pressure"
    action: |
      generate FaultDetected to SELF;
```

**Guard rules:**
- Guard is a pycca boolean expression string, or `null` for unconditional
- If any transition from `(from_state, event)` has a guard, ALL transitions on that pair must have guards — mixing guarded and unguarded on the same event/source is invalid
- Mutual exclusivity and total coverage are required — enforced by `validate_model` structurally, and by simulator at runtime (coverage gap = error in trace)

**Entry actions:**
- `entry_action` executes when the state is entered
- Exit actions are not supported (not a pycca concept)

**Events catalog:**
- Events defined once per state machine with typed parameters
- Transitions reference events by name
- `validate_model` checks that all transition event names exist in the events catalog
- `rcvd_evt.<param_name>` accesses event parameters in action blocks and guards

### Pycca action storage

All action blocks (transition actions, entry actions, method bodies) stored as YAML literal block scalars (`|`). Raw pycca text — the lark parser handles parsing at validation/simulation time.

### Draw.io Round-Trip

- **What survives:** Semantic content only — classes, attributes, associations (with multiplicity and verb phrases), states, transitions, guards, actions. Layout/colors do not need to be preserved in the YAML.
- **Re-render behavior:** `render_to_drawio` merges, not overwrites. If a Draw.io file already exists, existing element positions are preserved; net-new elements are auto-placed; removed elements are deleted.
- **Element IDs:** Deterministic from YAML path — e.g., `hydraulics:class:Valve`, `hydraulics:state:Valve:Idle`. Same YAML always produces same Draw.io element ID.
- **Canonical schema enforcement:** `validate_drawio` checks shape type and required labels (name, stereotype, multiplicity, verb phrases). Colors and fonts are free for engineers to customize.
- **File structure:** One `.drawio` file per diagram type, mirroring the YAML layout exactly:
  - `class-diagram.yaml` → `class-diagram.drawio`
  - `state-diagrams/Valve.yaml` → `state-diagrams/Valve.drawio`
  - `DOMAINS.yaml` → `DOMAINS.drawio`
  Not one file per domain with multiple pages.

### Stereotype enforcement

- `active` class: must have a corresponding `state-diagrams/<ClassName>.yaml` (or inherit from an active supertype)
- `entity` class: must not have a state diagram (unless it has a `partitions` block, in which case subtypes handle state machines)
- `associative` class: must have a `formalizes` field pointing to a valid R-number; can be `active` if it has its own lifecycle

### Behavior Doc Templates

**behavior-domain.md:**
```markdown
# Domain: <DomainName>

## Purpose
[One-paragraph statement of this domain's responsibility]

## Scope
### Does
- [Responsibility 1]

### Does Not
- [Out of scope 1]

## Bridge Contracts
### R: <OtherDomain>::<operation_name>
- Input: <param> (<type>)
- Output: <return_type>
- Behavior: [what happens]

### P: <operation_name>
- Input: <param> (<type>)
- Output: <return_type>
- Behavior: [what this domain provides when called]
```

**behavior-class.md:**
```markdown
# Class: <ClassName>

## Purpose
[What this class represents and its role in the domain]

## Attributes
### <attribute_name>
- Type: <type>
- Changes when: [what causes this value to change]
- Triggers: [events, transitions, or bridge calls that result from a change]

## Lifecycle
[Does this class have a state machine? Key states, what drives transitions.
If none: 'No state machine.']

## Methods
### <method_name>(<params>) -> <return>
[What this method does; pre/post conditions if relevant]
```

**behavior-state.md:**
```markdown
# State Machine: <ClassName>

## Purpose
[What behavioral role this state machine plays]

## States
### <StateName>
- Invariant: [what is true while in this state]
- Transitions out:
  - <EventName> [<guard>] -> <TargetState>

## Event Catalog
### <EventName>
- Accepted in: [list of states]
- Effect: [what happens]
```

### Claude's Discretion

- Auto-layout algorithm for initial Draw.io element placement
- Internal Pydantic model structure and field aliases
- YAML serialization formatting (indentation, quote style)
- Error message wording in validation issue lists

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

None — greenfield project. No existing Python code.

### Established Patterns

- Stack locked in `.planning/research/STACK.md`: Pydantic v2, PyYAML/ruamel.yaml, lxml, NetworkX, lark, defusedxml
- Architecture locked in `.planning/research/ARCHITECTURE.md`: module structure (`mdf_server/schema/yaml_schema.py`, `drawio_schema.py`), file layout, tool contracts

### Integration Points

- `yaml_schema.py` is the output of this phase — consumed by every MCP tool in Phases 2-10
- `drawio_schema.py` canonical table is the output — consumed by `render_to_drawio`, `validate_drawio`, `sync_from_drawio` in Phase 4
- Templates land in `templates/` — consumed by `/mdf:new-project` skill in Phase 9
- `DOMAINS.yaml` schema consumed by `list_domains()` in Phase 2

</code_context>

<specifics>
## Specific Ideas

- DOMAINS.yaml replaces DOMAINS.md — machine-parseable from day one (came up during versioning discussion)
- Subtype state machine inheritance is override-not-append: subtype state diagram replaces supertype's entirely; no merging
- Guard mutual exclusivity is required — validator enforces structural rule (all-or-none guards on same from/event pair); simulator catches runtime coverage gaps
- Method scope (`instance` | `class`) maps directly to C instance vs. static function at code generation time
- pycca primitive type names need verification against repos.modelrealization.com before Phase 3 — TRANSLATION.md handles the mapping

</specifics>

<deferred>
## Deferred Ideas

- TRANSLATION.md template — Phase 2+ work; not in Phase 1 requirements
- pycca compiler invocation details — Phase 3+ (code generation path)
- Multi-candidate identifier support (multiple candidate keys per class) — current schema supports one primary identifier; deferred to schema v1.1 if needed
- Polymorphic event dispatch across subtype hierarchies — Phase 5 simulator concern; schema stores what's there, simulator resolves at runtime

</deferred>

---

*Phase: 01-schema-foundation*
*Context gathered: 2026-03-05*
