# At_Floor Entry Action Generates Event to Class Name, Not Instance

**ID:** ELV-005
**Status:** Open
**Domain/Component:** Elevator model (Elevator.yaml), schema validator / pycca

## Root Cause

`Elevator.yaml` `At_Floor` entry action contains:
```
generate Elevator_arrived to Floor;
```
`Floor` here is a class name, not an instance variable. `generate` requires an instance
reference as the target — either a local variable bound by a `select` statement, `self`,
or `SELF`. Sending to a bare class name is a modeling error.

The correct fix is to select the specific `Floor` instance for the elevator's current floor
before generating the event:
```
select any f from instances of Floor where floor_num == self.current_floor;
generate Elevator_arrived to f;
```

### current_floor is valid at this point

`current_floor` is updated in the transition actions that lead to `Stopping`:
- `Moving_Up → Stopping`: `self.current_floor = next_stop_floor;`
- `Moving_Down → Stopping`: `self.current_floor = next_stop_floor;`

`At_Floor` is only entered from `Stopping` (on `Stopped`), so `current_floor` is
already correct when the `At_Floor` entry action fires.

### Validator rule needed

The pycca parser / validator should detect `generate <event> to <BareClassName>` and
flag it as an error. A valid target is one of:
- `self` / `SELF`
- A variable name bound by a preceding `select` in the same action block
- A referential attribute (e.g., `r1_elevator_id`)

## Fix Applied

Applied in Phase 04.1 Plan 03 (2026-03-17).

Changes made to `Elevator.yaml`:
1. Replaced `r_queue_head_id` with `r14_request_id` (correct referential from Plan 02 R14 association).
2. Replaced `r10_floor_num` with `r13_floor_num` (correct referential — FloorIndicator formalizes R13).
3. Added `(direction: self.next_direction)` param to `generate Direction_set`.
4. `generate Elevator_arrived to floor_inst` was already using bound variable `floor_inst` — confirmed correct.
5. Changed `generate Open_door to SELF` to `generate Open_door to self` (lowercase canonical form).

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-17 | `Elevator/state-diagrams/Elevator.yaml` | Fixed At_Floor entry_action: r14_request_id, r13_floor_num, Direction_set param, Open_door target |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator flags `generate <event> to <ClassName>` where target is a bare class name | | |
| | Validator accepts `generate <event> to <instance_var>` after fix | | |
