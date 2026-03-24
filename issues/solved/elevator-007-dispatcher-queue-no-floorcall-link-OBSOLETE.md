# Dispatcher Has No Association Link to Pending FloorCall Queue

**ID:** ELV-007
**Status:** Open
**Domain/Component:** Elevator model (Dispatcher.yaml, class-diagram.yaml)

## Root Cause

The `Dispatcher` class tracks pending floor calls using only an integer counter:
```yaml
- name: queue_length
  type: Integer
```
There is no association between `Dispatcher` and the `FloorCall` instances it is managing.
When a `FloorCall` arrives and the `Dispatcher` transitions to `Waiting`, it has no way to
know **which** `FloorCall` instances are pending, what order they arrived in, or which one
to assign next.

The `Dispatcher.yaml` `Elevator_available` transition actions:
```
action: "create object of Request; generate Request_assigned to Elevator;"
```
...create a `Request` without any reference to a specific `FloorCall`. There is no way to
populate the `Request` with the correct destination floor without knowing which `FloorCall`
is at the head of the queue.

### What is needed

A FIFO queue of pending `FloorCall` instances must be accessible to the `Dispatcher`. Options:

**Option A — Association:**
Add an association between `Dispatcher` and `FloorCall`:
```
Dispatcher 0..1 --- 0..* FloorCall  ("is managing" / "is pending with")
```
The `Dispatcher` selects `FloorCall` instances related via this association, ordered by
arrival. A head-pointer pattern (similar to ELV-003) would track the front of the queue.

**Option B — Query-based:**
No explicit association. When assigning, the `Dispatcher` queries all `FloorCall` instances
in `Waiting` state and picks the oldest (by timestamp or insertion order). Requires a
`submitted_at` timestamp attribute on `FloorCall` or similar ordering mechanism.

**Option C — Linked list on FloorCall:**
`FloorCall` instances form their own FIFO via a self-referential association (similar to
`Request` / R9 in ELV-003), and `Dispatcher` holds a head pointer referential.

Current recommendation: **Option A with head pointer** — consistent with the `Request` deque
pattern already in the model.

## Fix Applied

Applied in Phase 04.1 Plan 03 (2026-03-17). **Pragmatic workaround applied; formal fix deferred to Phase 4.2.**

**Pragmatic fix (Plan 03):**
The formal Option A (explicit Dispatcher↔FloorCall association) requires schema and class-diagram
changes that are out of scope for this plan. As a pragmatic workaround, the Dispatcher transition
actions now use `select any fc from instances of FloorCall where floor_num != 0` to retrieve a
pending FloorCall without a formal association traversal. This is semantically equivalent when only
one FloorCall is pending but does not guarantee FIFO ordering with multiple pending calls.

Changes made:
1. All three Dispatcher transition actions using `create object of Request` replaced with:
   ```
   select any fc from instances of FloorCall where floor_num != 0;
   create req of Request;
   req.destination_floor = fc.floor_num;
   select any elev from instances of Elevator;
   generate Request_assigned(target_floor: req.destination_floor) to elev;
   ```
2. `Request_assigned` now includes `(target_floor: req.destination_floor)` param (matching Elevator event signature).

**Pending (Phase 4.2):** Add formal Dispatcher↔FloorCall association to class-diagram.yaml and
replace the `select any fc where floor_num != 0` workaround with proper queue traversal.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-17 | `Elevator/state-diagrams/Dispatcher.yaml` | Replaced create object of Request with create req of Request + select FloorCall (pragmatic workaround) |
| Phase 4.2 | `Elevator/class-diagram.yaml` | Add Dispatcher↔FloorCall association and head-pointer referential (pending) |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Dispatcher assigns correct FloorCall when multiple are pending | | |
| | Dispatcher queue depletes in FIFO order | | |
| | Validator flags `create object of Request` action without source FloorCall reference | | |
