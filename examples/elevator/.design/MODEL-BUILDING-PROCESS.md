# Model Building Process — Elevator Domain

This document captures the reasoning process used to build the elevator
model from scratch, class by class. The approach was to start with the
central actor and expand outward, asking "what does this thing do?" and
"what does it interact with?" at each step.

## Starting Point: The Elevator

We began with the question: **what is an elevator?**

An elevator is a car that moves up and down within a building. It has a
current position, a direction of travel, and a destination. From this
description, the attributes fell out naturally: `current_floor`,
`direction`, `next_stop_floor`, `next_direction`.

## Physical Structure: Shaft, Floor, ShaftFloor

Next: **what does the elevator move within?**

A Shaft — the fixed vertical structure. One elevator per shaft, one shaft
per elevator (R1). The shaft doesn't move; the elevator does.

Then: **what are the sources and destinations of travel?**

Floors. But the intersection of "which shaft meets which floor" matters —
not every shaft serves every floor. This led to **ShaftFloor** as a
linking class decomposing the M:M between Shaft and Floor.

### Key decision: compound identifiers

ShaftFloor's natural identity is (shaft, floor) — not a surrogate ID.
This was the first use of explicit referential attributes as compound
identifiers, with `r2_shaft_id` and `r3_floor_num` both marked as
`identifier: 1, referential: R2/R3`.

## Position Updates: Transport Bridge

**How does the elevator know it reached a floor?**

Motor physics and sensor detection are out of domain — that's a realized
Transport domain's job. We added a sensor_id to ShaftFloor and a bridge
callback `ElevatorDetected(sensor_id)`. The bridge implementation looks
up the ShaftFloor by sensor, traverses to the Elevator via R2→R1, and
generates `Floor_reached` to the elevator.

This established the pattern: **bridge callbacks generate events to
domain objects** rather than directly mutating attributes.

## Elevator State Machine

Built iteratively through several refinements:

1. **First pass:** Idle → Moving → Floor_Updating → back to Moving or Idle.
   Problem: Moving's entry action set the destination, but re-entry from
   Continue would clobber it.

2. **Added transient states:** StartMoving and StopMoving to handle
   setup/teardown. This separated "begin moving" from "continue moving."

3. **Added Exchanging:** Realized the elevator needs a "parked at floor,
   passengers boarding" state distinct from Idle. Idle means door closed,
   no work. Exchanging means door moving freely, may or may not have a
   next destination.

4. **Merged states:** Departing absorbed StartMoving (sets direction,
   updates indicators). Arriving absorbed StopMoving (clears direction,
   notifies buttons, updates indicators). Down to 6 states.

5. **Direction semantics:** Direction represents the elevator's service
   direction — Up, Down, or None. None only when truly idle.

### Key insight: transient vs senescent states

- **Transient states** (Departing, Floor_Updating, Arriving) do work in
  their entry action and immediately generate an event to self to leave.
- **Senescent states** (Idle, Moving, Exchanging) wait for external events.

## Call Buttons: DestFloorButton and FloorCallButton

**How does the elevator get its destination?**

Through buttons. Two kinds:
- **DestFloorButton** — inside the car, one per floor. "Take me to floor 7."
- **FloorCallButton** — on a floor, up to two (Up/Down). "I'm here, going up."

### Key decision: dropped the CallButton generalization

Initially modeled as CallButton (supertype) → DestFloorButton / FloorCallButton.
But the two buttons have fundamentally different behaviors:
- DestFloorButton listens for `Floor_served` from its own elevator
- FloorCallButton listens for `Call_served` from the Dispatcher

Different events, different satisfaction conditions, different state machines.
The generalization wasn't pulling its weight, so we dropped it. Each button
is an independent active class with its own state machine.

### Compound identifiers again

DestFloorButton's natural identity is (elevator, floor) — one button per
floor per elevator. Uses explicit relvars `r4_elevator_id` and
`r5_floor_num` as compound I1.

### Timestamps for ordering

Both buttons need `pressed_at: Timestamp` to support the direction
priority logic when the elevator arrives at a floor. Added a Clock
realized domain with a `Now()` bridge.

## Direction Priority Logic (not yet implemented)

When the elevator arrives at a floor, it determines its next action
based on this priority list:

1. Lit DestFloorButtons in the same direction → keep going
2. Lit DestFloorButtons in the opposite direction → reverse
3. FloorCallButton at current floor, earliest pressed → service it
4. Any FloorCallButton accessible to this elevator, most recent → go there
5. Nothing → Idle

## Patterns Established

- **Start with the central actor**, expand outward by asking "what does
  it interact with?"
- **Compound identifiers** from referential attributes for linking classes
  (ShaftFloor, DestFloorButton)
- **Bridge callbacks generate events** to domain objects, not direct mutation
- **Transient states** for decision-making, senescent states for waiting
- **Drop generalizations** when subtypes have fundamentally different behavior
- **Timestamps from a realized Clock domain** for ordering
- **Document each class with a narrative** in the README as it's added
