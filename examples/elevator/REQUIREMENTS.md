# Elevator System Requirements

## Overview

A multi-elevator building control system modeled across two domains: `Building` (realized)
and `Elevator` (application). This model serves as a clean reference fixture for verifying
mdf-simulator tools.

---

## Physical Configuration

- The building has a configurable number of floors and elevator cars, defined by `BuildingSpec`
- Each floor has a `Floor` object with flags for top and bottom floors
- Each elevator has exactly one `Door`
- Each elevator has a `FloorIndicator` at every floor landing showing its intended direction

---

## Call Types

### ElevatorCall (car call)
- Created when a passenger inside the elevator presses a destination floor button (`DestFloorButton`)
- Handled entirely by the `Elevator` — does not go through `Dispatcher`
- Results in a `Request` added directly to the elevator's deque

### FloorCall (hall call)
- Created when a passenger at a floor landing presses an Up or Down button (`FloorCallButton`)
- Routed to `Dispatcher`, which assigns the first available idle elevator
- Results in a `Request` added to the assigned elevator's deque

---

## Dispatcher Behavior

- Handles FloorCalls only — ElevatorCalls bypass the Dispatcher entirely
- When a FloorCall arrives and an elevator is idle: assign immediately
- When a FloorCall arrives and no elevator is idle: queue it, wait for `Elevator_available`
- When an elevator signals `Elevator_available`: assign the head of the pending FloorCall queue
- First available idle elevator wins — no optimization for nearest elevator in this model

---

## Elevator Self-Service (ElevatorCalls)

- When a `DestFloorButton` is pressed, the `Elevator` receives the call directly
- The elevator creates a `Request` and inserts it into its own deque using safe-stop logic
- When the elevator empties its deque and has no FloorCall at its current floor, it signals
  `Elevator_available` to the `Dispatcher`

---

## Request Deque

The elevator maintains an ordered deque of pending `Request` objects implemented as a
singly-linked list (each `Request` has an optional reference to the next `Request` via R9).
The elevator holds a reference to the head of the deque.

### Insertion rules

- **Normal insertion (push back)**: New requests go to the back of the deque
- **Intermediate stop (push front)**: If a new request can be safely served before the current
  next stop, it is inserted at the front and the displaced request moves behind it

### Safe-stop rule

A new request can be inserted ahead of the current next stop only if the elevator has not yet
passed the point-of-no-return:

- Moving **Down** to floor N: can insert new stop at floor M if `current_floor >= M + 1`
- Moving **Up** to floor N: can insert new stop at floor M if `current_floor <= M - 1`

**Example**: Elevator at floor 9 going to floor 3. New request for floor 5 arrives.
- Safe to insert if elevator has not yet passed floor 6 (`current_floor >= 6`)
- If safe: deque becomes `[5 → 3]`, elevator stops at 5 first, then continues to 3
- If not safe: floor 5 request goes to back of deque `[3 → 5]`

---

## Direction Determination

When an elevator arrives at a floor, it must determine its next direction **before the doors open**
so that the `FloorIndicator` can be set and waiting passengers know whether to board.

Priority order for determining `next_direction`:

1. **Deque not empty**: peek at `head.next` — direction based on that request's floor vs `current_floor`
2. **Deque empty, FloorCall exists at this floor**: direction = `FloorCall.direction`
   (the passenger's desired direction of travel)
3. **Deque empty, no FloorCall at this floor**: `next_direction = Stopped`
   (indicator shows Off; elevator signals Dispatcher after door closes)

---

## Floor Indicators

- One `FloorIndicator` per elevator per floor landing
- Set to `Up`, `Down`, or `Off` before the elevator's door opens
- Passengers use the indicator to decide whether to board
- Reset to `Off` when the elevator departs

---

## Opportunistic FloorCall Satisfaction

When an elevator arrives at a floor with a known direction, it notifies the `Floor` object
with that direction. The `Floor` checks for any `FloorCall` at that floor in the matching
direction and fulfils it immediately — even if the `Dispatcher` had not yet created a `Request`
for it.

- A `FloorCall` in `Waiting` or `Assigned` state can be fulfilled this way
- If a `FloorCall` in `Waiting` is fulfilled opportunistically, any in-progress `Request`
  the `Dispatcher` may have created for it is cancelled

---

## Button Illumination

- A `CallButton` illuminates (`Lit`) when its call is submitted
- It extinguishes (`Unlit`) when the associated call is `Fulfilled`
- A button in `Lit` state does not generate a new call if pressed again (debounce)

---

## Call Lifecycle

```
Button pressed → Call created (Waiting) → Request created (Pending)
  → Request assigned to Elevator (Assigned) → Elevator arrives (Serving)
  → Door closes (Complete) → Call fulfilled → Button extinguished
```

Opportunistic path (no Request created):
```
Button pressed → Call created (Waiting)
  → Elevator arrives going same direction → Call fulfilled → Button extinguished
```

---

## Door Behavior

- Door opens on `Open_door` event from Elevator
- Door stays open for a timer period, then closes automatically
- If an obstruction is detected while closing, the door re-opens
- When fully closed, Door generates `Door_closed` back to the Elevator

---

## Terminal States

A state marked `terminal: true` in a state diagram has a specific lifecycle semantic:
**upon completion of the state's entry actions, the object instance deletes itself.**

Terminal states must have no outgoing transitions. It is a modeling error to define a
terminal state with outgoing transitions.

Terminal states in this model:

| Class | State | What triggers deletion |
|-------|-------|----------------------|
| `ElevatorCall` | `Fulfilled` | Elevator arrived at destination; `Call_fulfilled` sent to button before deletion |
| `FloorCall` | `Fulfilled` | Elevator arrived going matching direction; `Call_fulfilled` sent to button before deletion |
| `Request` | `Complete` | Door closed after serving; `Service_complete` sent to elevator before deletion |
| `Request` | `Cancelled` | FloorCall was satisfied opportunistically before a Request was dispatched; object deletes silently |

---

## Out of Scope (for this model)

- Elevator scheduling optimization (nearest car, least loaded)
- Weight sensors or capacity limits
- Emergency stop or fire service mode
- Express zones or skip-floor logic
- Elevator acceleration/deceleration physics beyond the safe-stop rule
