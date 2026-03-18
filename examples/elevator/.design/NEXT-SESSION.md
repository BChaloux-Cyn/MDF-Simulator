# Next Session — Elevator Model Continuation

## Where We Left Off

The model has 6 classes (Elevator, Shaft, Floor, ShaftFloor,
DestFloorButton, FloorCallButton), 6 associations (R1–R6), 3 state
machines, and 4 realized domain bridges (Building, Transport, Clock).

The elevator state machine has 6 states: Idle, Departing, Moving,
Floor_Updating, Arriving, Exchanging.

## Immediate Next Step: Arriving Entry Action

The Arriving state's entry action needs to implement the direction
priority logic. When the elevator arrives at a floor:

1. **Same direction:** Any lit DestFloorButtons (curr_state == Lit) in
   the direction the elevator was traveling? Keep going that way.
2. **Opposite direction:** Any lit DestFloorButtons the other way? Reverse.
3. **Current floor's FloorCallButton:** Earliest `pressed_at` among lit
   FloorCallButtons at this floor. Service it.
4. **Any FloorCallButton:** Most recent `pressed_at` among all lit
   FloorCallButtons accessible to this elevator (via R1→R2→R3→R6
   traversal). Go there.
5. **Nothing:** No work → Idle after door closes.

This requires traversing R4 to scan DestFloorButtons and R1→R2→R3→R6
to scan accessible FloorCallButtons.

## Classes Still To Add

### Doors (CarDoor, ShaftDoor)
- **Door** (active, supertype) — state machine: Closed, Opening, Open, Closing
- **CarDoor** (entity) — specializes Door, belongs to Elevator
- **ShaftDoor** (entity) — specializes Door, belongs to ShaftFloor
- When elevator enters Arriving → open CarDoor + ShaftDoor at current floor
- When doors close → generate `Door_closed` to Elevator
- Doors must synchronize: both open together, both close together

### Dispatcher
- Singleton active class, manages FloorCall queue
- Relationships: Dispatcher → Elevator (1:0..*), Dispatcher → FloorCall queue
- FloorCall queue uses linked-list pattern (head pointer + self-referential next)
- Assigns elevators to floor calls based on proximity/direction
- Generates `Floor_assigned` to the selected Elevator
- Generates `Call_served` to the FloorCallButton when satisfied

### Indicators (ElevatorIndicator, FloorIndicator)
- **ElevatorIndicator** — inside the car, shows current floor
- **FloorIndicator** — on a floor, shows direction of approaching elevator
- Updated in Departing and Arriving entry actions
- May need relationships to Elevator and Floor

## Open Issues Filed

| ID | Summary |
|----|---------|
| DRAWIO-003 | Render overwrites user layout changes on state diagrams |
| DRAWIO-004 | Draw.io should render referential annotations ({I1, R2}) |
| VAL-001 | Realized domains should not require class-diagram.yaml |

## Schema/Tool Changes Made This Session

- `Attribute.identifier` changed from `bool` to `list[int] | None` with
  backward-compatible coercion (supports compound identifiers)
- Validation: error on missing I1 for non-subtype classes, warning on
  UniqueID non-identifier attributes
- Draw.io: renders `{I1}`, `{I1, I2}` suffixes on identifier attributes
- Validation: provided bridges now correctly look up DOMAINS.yaml entries
- COMPILATION.md §5: documents explicit relvars and compiler deduplication
