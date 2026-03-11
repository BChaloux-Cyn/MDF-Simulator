# Elevator Example Model

A multi-domain elevator control system model used to verify the mdf-simulator tools.

## Purpose

This model serves as a clean, well-formed reference model for testing:

- `validate_model` — structural checks, guard completeness, referential integrity
- `model_io` — read/write round-trip, domain listing
- `render_to_drawio` (Phase 4) — Draw.io export
- `simulate_domain` / `simulate_class` (Phase 5) — simulation engine

Errors can be introduced into this model to verify that the validation tool catches them correctly.

## Domain Structure

### `Building` *(realized)*

Represents the physical building infrastructure. Provides bridge operations consumed by the `Elevator` domain.

| Class | Stereotype |
|-------|-----------|
| `Floor` | entity |

**Bridge operations provided:**
- `IsTopFloor` — checks if a given floor number is the top floor
- `IsBottomFloor` — checks if a given floor number is the bottom floor

---

### `Elevator` *(application)*

Contains the core elevator control logic.

| Class | Stereotype | Purpose |
|-------|-----------|---------|
| `Elevator` | active | Manages movement between floors |
| `Door` | active | Controls the open/close cycle |
| `Dispatcher` | active | Receives requests and assigns elevators |
| `Request` | entity | A single hall call or car call |

**Associations:**
- **R1**: `Elevator` 1 --- 1 `Door`
- **R2**: `Elevator` 1 --- 0..* `Request`

**Types:**
- `Direction` — enum: `Up`, `Down`, `Stopped`
- `RequestType` — enum: `HallCall`, `CarCall`
- `FloorNumber` — Integer scalar, range 1–100

**Bridge operations required:**
- `Building::IsTopFloor`
- `Building::IsBottomFloor`

## State Machines

### Elevator
| State | Entry Action |
|-------|-------------|
| `Idle` | — |
| `Moving_Up` | `self.direction = Up;` |
| `Moving_Down` | `self.direction = Down;` |
| `Stopping` | `self.direction = Stopped;` |
| `At_Floor` | `generate Open_door to self.r1_door_id;` |

Key transitions:
- `Idle` → `Moving_Up` on `Floor_assigned` [guard: `target_floor > current_floor`]
- `Idle` → `Moving_Down` on `Floor_assigned` [guard: `target_floor < current_floor`]
- `Idle` → `At_Floor` on `Floor_assigned` [guard: `target_floor == current_floor`]
- `Moving_Up` / `Moving_Down` → `Stopping` on `Floor_reached`
- `Stopping` → `At_Floor` on `Stopped`
- `At_Floor` → `Idle` on `Door_closed`

### Door
| State | Entry Action |
|-------|-------------|
| `Closed` | `generate Door_closed to self.r1_elevator_id;` |
| `Opening` | — |
| `Open` | — |
| `Closing` | — |

Key transitions:
- `Closed` → `Opening` on `Open_door`
- `Opening` → `Open` on `Door_timer_expired`
- `Open` → `Closing` on `Door_timer_expired`
- `Closing` → `Closed` on `Door_timer_expired`
- `Closing` → `Opening` on `Obstruction_detected`

### Dispatcher
| State | Entry Action |
|-------|-------------|
| `Idle` | — |
| `Assigning` | — |

Key transitions:
- `Idle` → `Assigning` on `Request_received`
- `Assigning` → `Idle` on `Assignment_complete`

## References

- Based on the well-known Shlaer-Mellor elevator case study
- Leon Starr's Executable UML elevator tutorial (modeling-languages.com)
- Standard elevator state machine (Software Ideas Modeler)
