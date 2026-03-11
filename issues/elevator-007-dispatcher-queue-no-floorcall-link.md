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

_Pending. Awaiting design decision on queue mechanism._

## Change Log

| Date | File | Change |
|------|------|--------|
| | `Elevator/class-diagram.yaml` | Add Dispatcher↔FloorCall association and any needed head-pointer referential |
| | `Elevator/state-diagrams/Dispatcher.yaml` | Update actions to traverse the queue association |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Dispatcher assigns correct FloorCall when multiple are pending | | |
| | Dispatcher queue depletes in FIFO order | | |
| | Validator flags `create object of Request` action without source FloorCall reference | | |
