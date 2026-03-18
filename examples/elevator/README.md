# Elevator Example Model

A multi-domain elevator control system model used to verify the mdf-simulator
tools. Based on the well-known Shlaer-Mellor elevator case study.

## Domain Structure

- **Building** *(realized)* — physical building infrastructure, provides
  bridge operations (`IsTopFloor`, `IsBottomFloor`)
- **Transport** *(realized)* — motor control and position sensing, calls
  `ElevatorDetected(sensor_id)` when a car reaches a floor threshold
- **Clock** *(realized)* — provides monotonic timestamps via `Now()`
- **Elevator** *(application)* — core elevator control logic, built up
  class-by-class below

## Types

- `Direction` — enum: `Up`, `Down`, `None`
- `CallDirection` — enum: `Up`, `Down`
- `FloorNumber` — Integer scalar, range 1–100
- `Timestamp` — Integer, monotonic time value from Clock bridge

---

## Elevator Domain — Class-by-Class

The model is built up incrementally. Each class tells part of the story.

### Elevator *(active)*

An **Elevator** is a car that moves up and down within a building. It has a
current position (which floor it's at), a direction of travel, and a
destination it's heading toward. When idle, it waits for work. When assigned
a floor, it moves toward it, stops, and allows passengers to board or exit
before returning to idle or continuing to its next stop.

| Attribute | Type | |
|-----------|------|-|
| `elevator_id` | UniqueID | {I1} — distinguishes one car from another |
| `current_floor` | FloorNumber | where the car is right now |
| `direction` | Direction | Up, Down, or None |
| `next_stop_floor` | FloorNumber | where it's heading |
| `next_direction` | Direction | which way after the next stop |

**State machine:**

The elevator starts **Idle** — parked at a floor, door closed, no
destination. When assigned a floor it departs, moves, and updates its
position at each floor threshold. At its destination it stops, arrives,
and enters **Exchanging** — the door moves freely and passengers get on
and off. New destinations can arrive while exchanging. When the door
closes, the elevator either departs for the next destination or returns
to Idle.

| State | Type | Entry Action |
|-------|------|-------------|
| `Idle` | senescent | — (door closed, no work) |
| `Departing` | transient | set direction, update indicators; generate `Ready` |
| `Moving` | senescent | — (steady state) |
| `Floor_Updating` | transient | update `current_floor`; generate `At_Destination` or `Continue` |
| `Arriving` | transient | clear direction, notify buttons, update indicators; generate `Arrived` |
| `Exchanging` | senescent | — (door moving freely, passengers boarding) |

| From | To | Event | Guard |
|------|----|-------|-------|
| Idle | Departing | `Floor_assigned` | |
| Departing | Moving | `Ready` | |
| Moving | Floor_Updating | `Floor_reached` | |
| Floor_Updating | Arriving | `At_Destination` | |
| Floor_Updating | Moving | `Continue` | |
| Arriving | Exchanging | `Arrived` | |
| Exchanging | Exchanging | `Floor_assigned` | |
| Exchanging | Departing | `Door_closed` | `next_stop_floor != current_floor` |
| Exchanging | Idle | `Door_closed` | `next_stop_floor == current_floor` |

**Relationships:**
- **R1**: Each Elevator *moves within* exactly one Shaft; each Shaft *carries* exactly one Elevator

### Shaft *(entity)*

A **Shaft** is the fixed vertical structure that an elevator car travels
along. Each shaft contains exactly one elevator, and each elevator lives in
exactly one shaft. The shaft itself doesn't move — it's the physical column
of space that constrains the elevator's path through the building.

| Attribute | Type | |
|-----------|------|-|
| `shaft_id` | UniqueID | {I1} |

**Relationships:**
- **R1**: Each Elevator *moves within* exactly one Shaft; each Shaft *carries* exactly one Elevator

### Floor *(entity)*

A **Floor** is a level in the building. Floors are the sources and
destinations of elevator travel — passengers wait at a floor and ride to
a floor. A floor exists independently of any shaft or elevator.

| Attribute | Type | |
|-----------|------|-|
| `floor_num` | FloorNumber | {I1} — the floor number identifies it |
| `is_top_floor` | Boolean | true if this is the highest floor |
| `is_bottom_floor` | Boolean | true if this is the lowest floor |

### ShaftFloor *(entity)*

A **ShaftFloor** represents a specific stop — the point where a shaft
meets a floor. Not every shaft serves every floor. A shaft has many
ShaftFloors (one per floor it serves), and a floor may be served by
many shafts.

| Attribute | Type | |
|-----------|------|-|
| `r2_shaft_id` | UniqueID | {I1} — referential from R2 (Shaft) |
| `r3_floor_num` | FloorNumber | {I1} — referential from R3 (Floor) |
| `sensor_id` | Integer | the physical sensor at this stop |

The compound identifier (shaft + floor) uniquely identifies each stop —
there's no need for a surrogate ID. The `sensor_id` maps to the
physical sensor hardware but is not an identifier.

When the external transport system detects an elevator car arriving at
a floor, it calls `ElevatorDetected(sensor_id)` across the bridge.
The Elevator domain looks up the ShaftFloor by sensor ID, traverses to
the Shaft and then the Elevator (via R2→R1), and delivers the floor
update. The floor number comes from traversing ShaftFloor→Floor (R3).

**Relationships:**
- **R2**: Each Shaft *has stops at* zero or more ShaftFloors; each ShaftFloor *is a stop in* exactly one Shaft
- **R3**: Each Floor *is served by* zero or more ShaftFloors; each ShaftFloor *serves* exactly one Floor

### DestFloorButton *(active)*

A **DestFloorButton** is a button mounted inside an elevator car — one
per reachable floor. When a passenger presses it, they are saying
"take me to this floor." It lights up when pressed and goes dark when
the elevator arrives at that floor.

| Attribute | Type | |
|-----------|------|-|
| `r4_elevator_id` | UniqueID | {I1} — referential from R4 (Elevator) |
| `r5_floor_num` | FloorNumber | {I1} — referential from R5 (Floor) |
| `pressed_at` | Timestamp | when the button was last pressed |

The compound identifier (elevator + floor) uniquely identifies each
button — there is exactly one button per floor per elevator.

**Methods:**
- `press()` — records timestamp via `Clock::Now()`, generates `Activated` to self

**State machine:** Idle (unlit) and Lit. `press()` activates it. When the
elevator stops at a floor, it generates `Floor_served(floor_num)` to all
its buttons — the one matching the floor goes back to Idle.

| From | To | Event | Guard |
|------|----|-------|-------|
| Idle | Lit | `Activated` | |
| Lit | Idle | `Floor_served` | `floor_num == self.r5_floor_num` |
| Lit | Lit | `Floor_served` | `floor_num != self.r5_floor_num` |

**Relationships:**
- **R4**: Each Elevator *has destination buttons for* two or more DestFloorButtons; each DestFloorButton *is inside* exactly one Elevator
- **R5**: Each Floor *is a destination on* zero or more DestFloorButtons; each DestFloorButton *represents* exactly one Floor

### FloorCallButton *(active)*

A **FloorCallButton** is a button mounted on a floor — up to two per
floor (one Up, one Down). When a passenger presses it, they are saying
"I'm here and I want to go in this direction." It lights up when
pressed and goes dark when an elevator is assigned and arrives.

| Attribute | Type | |
|-----------|------|-|
| `button_id` | UniqueID | {I1} |
| `direction` | CallDirection | Up or Down |
| `pressed_at` | Timestamp | when the button was last pressed |

**Methods:**
- `press()` — records timestamp via `Clock::Now()`, generates `Activated` to self

**State machine:** Idle (unlit) and Lit. `press()` activates it.
`Call_served` (from the Dispatcher, once built) turns it off.

| From | To | Event |
|------|----|-------|
| Idle | Lit | `Activated` |
| Lit | Idle | `Call_served` |

**Relationships:**
- **R6**: Each Floor *has buttons at* zero to two FloorCallButtons; each FloorCallButton *is located on* exactly one Floor
