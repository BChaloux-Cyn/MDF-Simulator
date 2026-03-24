# Next Session — Elevator Model Continuation

## Where We Left Off

The model has 6 classes (Elevator, Shaft, Floor, ShaftFloor,
DestFloorButton, FloorCallButton), 6 associations (R1–R6), 3 state
machines, and 4 realized domain bridges (Building, Transport, Clock).

The elevator state machine has 6 states: Idle, Departing, Moving,
Floor_Updating, Arriving, Exchanging.

## Immediate Next Step: FloorCallButton ↔ Elevator Relationship

FloorCallButtons currently exist (R6 ties them to Floor) but have no
relationship to Elevator. The Arriving entry action's priorities 3–4
need to find lit FloorCallButtons accessible to this elevator. This
requires a traversal path from Elevator to FloorCallButton.

Design the association(s) that connect FloorCallButton to the elevator's
reachable floors, then wire the Arriving entry action to use them for
priorities 3–5.

## Still To Add: Doors (CarDoor, ShaftDoor)
- **Door** (active, supertype) — state machine: Closed, Opening, Open, Closing
- **CarDoor** (entity) — specializes Door, belongs to Elevator
- **ShaftDoor** (entity) — specializes Door, belongs to ShaftFloor
- When elevator enters Arriving → open CarDoor + ShaftDoor at current floor
- When doors close → generate `Door_closed` to Elevator
- Doors must synchronize: both open together, both close together

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
