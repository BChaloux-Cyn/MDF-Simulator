<!-- generated-by: gsd-doc-writer -->
# Configuration

mdf-simulator has no runtime environment variables or external config files. All configuration
is structural — it lives in YAML model files under `.design/model/` and in the Python runtime
parameters passed directly to the engine and tools.

---

## Model Directory Structure

All tools operate relative to the current working directory. A valid project
must contain a `.design/model/` directory with the following layout:

```
.design/model/
  DOMAINS.yaml
  <DomainName>/
    class-diagram.yaml
    types.yaml                   (optional)
    state-diagrams/
      <ClassName>.yaml           (one per active class)
```

The `model_io` and `validation` tools resolve domain names case-insensitively against the
subdirectory names found under `.design/model/`.

**Running tools from the correct directory is required.** For the elevator example:

```bash
cd examples/elevator
python -c "from tools.validation import validate_model; print(validate_model())"
```

---

## DOMAINS.yaml

**Location:** `.design/model/DOMAINS.yaml`  
**Schema version field:** `schema_version` — required, must be semver (e.g. `"1.0.0"`)

Declares all domains in the model and the bridge operations between them.

```yaml
schema_version: "1.0.0"
domains:
  - name: Elevator
    type: application          # "application" or "realized"
    description: Core elevator control logic
  - name: Building
    type: realized
    description: Physical building infrastructure
bridges:
  - from: Elevator
    to: Building
    operations:
      - name: IsTopFloor
        params:
          - name: floor_num
            type: Integer
        return: Boolean
```

| Field | Required | Description |
|-------|----------|-------------|
| `schema_version` | Required | Semver string; must match `^\d+\.\d+\.\d+$` |
| `domains[].name` | Required | Domain name used as directory name and in bridge references |
| `domains[].type` | Required | `"application"` or `"realized"` |
| `domains[].description` | Required | Human-readable domain description |
| `bridges` | Optional | Defaults to `[]` if absent |
| `bridges[].from` | Required | Calling domain name |
| `bridges[].to` | Required | Providing domain name |
| `bridges[].operations` | Required | List of bridge operation definitions |

---

## class-diagram.yaml

**Location:** `.design/model/<DomainName>/class-diagram.yaml`  
**Schema version field:** `schema_version` — required

Defines all classes, attributes, relationships, and associations for a domain.

```yaml
schema_version: "1.0.0"
domain: Elevator
classes:
  - name: Elevator
    stereotype: active         # "active" enables state machine; absent = passive
    attributes:
      - name: elevator_id
        type: UniqueID
        identifier: 1          # part of identifying attribute set
      - name: current_floor
        type: FloorNumber
        visibility: public     # "public" (default) or "private"
        scope: instance        # "instance" (default) or "class"
```

**Attribute field reference:**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Required | — | Attribute name |
| `type` | Required | — | MDF type name (`Integer`, `Boolean`, `String`, `Real`, `UniqueID`, or a domain-defined type) |
| `visibility` | Optional | `"public"` | `"public"` or `"private"` |
| `scope` | Optional | `"instance"` | `"instance"` or `"class"` |
| `identifier` | Optional | `null` | `true`, an integer, or a list of integers forming a compound identifier |
| `referential` | Optional | `null` | Referential attribute reference string |

---

## types.yaml

**Location:** `.design/model/<DomainName>/types.yaml`  
**Schema version field:** `schema_version` — required

Defines domain-specific named types. Optional — omit the file if no custom types are needed.

```yaml
schema_version: "1.0.0"
domain: Elevator
types:
  - name: Direction
    base: enum
    values: [Up, Down, None]
    description: Current direction of elevator travel

  - name: FloorNumber
    base: Integer
    range: [1, 100]
    description: A valid floor number in the building
```

**Supported `base` values:**

| Base | Description |
|------|-------------|
| `enum` | Enumeration — requires `values: [...]` |
| `struct` | Struct — requires `fields: [{name, type}, ...]` |
| `Boolean` | Scalar alias for the Boolean primitive |
| `Integer` | Scalar alias with optional `range: [min, max]` |
| `Real` | Scalar alias for floating-point |
| `String` | Scalar alias for text |
| `UniqueID` | Scalar alias for auto-generated unique identifier |

---

## State Diagram YAML

**Location:** `.design/model/<DomainName>/state-diagrams/<ClassName>.yaml`  
**Schema version field:** `schema_version` — required

One file per active class (classes with `stereotype: active` in the class diagram). Defines
states, transitions, entry actions, and events.

Action bodies in YAML must use the literal block scalar (`|`) for multi-line content.
Do not use the folded scalar (`>`), which collapses newlines and breaks statement boundaries.

```yaml
# Correct
entry_action: |
  self.direction = Stopped;
  generate Request_assigned to self;

# Wrong — collapses to one line
entry_action: >
  self.direction = Stopped;
  ...
```

---

## Simulation Engine Parameters

The simulation engine accepts runtime configuration through Python arguments rather than
config files. There are no environment variables or config files for the engine.

**`SimulationClock` — speed multiplier:**

```python
from engine.clock import SimulationClock

clock = SimulationClock(speed_multiplier=1.0)   # default: real-time ratio
clock.speed_multiplier = 2.0                     # 2x — delay queue expiry only
```

The `speed_multiplier` scales delay-queue expiry only. It does not affect action execution
speed.

**`run_simulation` — top-level entry point:**

```python
from engine.ctx import run_simulation

for step in run_simulation(domain_manifest, scenario=scenario_dict, bridge_mocks=mock_dict):
    print(step)
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `domain_manifest` | Required | — | Compiled `DomainManifest` TypedDict |
| `scenario` | Optional | `None` | Dict with `instances` and `events` lists for initial setup |
| `bridge_mocks` | Optional | `None` | Dict mapping bridge operation names to mock callables |

**Scenario dict format:**

```python
scenario = {
    "instances": [
        {"class": "Elevator", "identifier": {"elevator_id": "e1"}, "initial_state": "Idle", "attrs": {}},
    ],
    "events": [
        {"event": "FloorRequest", "class": "Elevator", "instance": {"elevator_id": "e1"}, "args": {"floor_num": 3}},
    ],
}
```

---

## Python Runtime Requirements

| Setting | Value |
|---------|-------|
| Python version | `>= 3.11` |
| Package manager | `uv` (recommended) or `pip` |
| Virtual environment | `.venv/` |
| Dependency source | `requirements.txt` (compiled from `requirements.in`) |

To update dependencies after modifying `requirements.in`:

```bash
pip-compile requirements.in        # regenerate requirements.txt
uv pip install -r requirements.txt # reinstall
```

See [COMMANDS.md](../COMMANDS.md) for full setup and tool invocation recipes.
