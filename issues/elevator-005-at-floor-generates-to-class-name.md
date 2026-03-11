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

_Pending._

## Change Log

| Date | File | Change |
|------|------|--------|
| | `Elevator/state-diagrams/Elevator.yaml` | Replace `generate Elevator_arrived to Floor;` with select + generate to instance variable |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator flags `generate <event> to <ClassName>` where target is a bare class name | | |
| | Validator accepts `generate <event> to <instance_var>` after fix | | |
