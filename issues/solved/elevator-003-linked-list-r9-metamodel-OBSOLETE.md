# Linked List via R9 Needs Metamodel / Schema Support

**ID:** ELV-003
**Status:** Open
**Domain/Component:** Elevator model (class-diagram.yaml), schema, metamodel

## Root Cause

`Request` implements an ordered deque via a self-referential association:
```yaml
- name: R9
  point_1: Request
  point_2: Request
  1_mult_2: "0..1"
  2_mult_1: "0..1"
  1_phrase_2: is followed by
  2_phrase_1: follows
```
`Elevator` tracks the head of this list with:
```yaml
- name: r_queue_head_id
  type: UniqueID
  referential: R2
```
This declaration is wrong: `R2` is the `Elevator` 1 --- 0..* `Request` ownership association,
not a pointer to the queue head. The `r_queue_head_id` attribute is a separate optional
foreign key from `Elevator` to `Request` that has no corresponding association defined.

### Design question: How to model this?

**Option A — Add a new association R11:**
```
Elevator 0..1 --- 0..1 Request  ("has as queue head" / "is queue head for")
```
Then `r_queue_head_id` becomes `referential: R11`. This is valid SM/xUML but requires
a new association. The self-referential R9 remains unchanged as the "next pointer."

**Option B — Metamodel-level linked list primitive:**
The engine recognizes a self-referential 0..1:0..1 association as a linked list and provides
built-in traversal operations (push_front, push_back, remove, peek_head). The head pointer
is implicit and managed by the engine without a separate referential attribute.

**Current recommendation:** Option A (explicit R11) is safer for schema consistency and keeps
the model self-describing. Option B is more ergonomic but requires deeper engine support.
Revisit when the simulation engine (Phase 5) is designed.

## Fix Applied

Option A implemented (explicit association, not metamodel primitive) in Phase 04.1 Plan 02.
R11 was already in use (Elevator-Shaft), so R14 was used instead.

Changes made:
- `Elevator.r_queue_head_id` renamed to `r14_request_id` with `referential: R14`
- New association R14 added: `Elevator 0..1 --- 0..1 Request` ("has as queue head" / "is queue head for")
- Self-referential R9 (Request next-pointer) unchanged

The head pointer is now a proper declared association. Action bodies can navigate it via
`select any head_req related by self->R14`.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-17 | `Elevator/class-diagram.yaml` | Renamed `r_queue_head_id` to `r14_request_id`; changed `referential: R2` to `referential: R14`; added R14 association |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator accepts self-referential 0..1:0..1 association | | |
| | Validator flags referential attribute pointing to wrong association | | |
| | Validator accepts R11 head-pointer association after fix | | |
