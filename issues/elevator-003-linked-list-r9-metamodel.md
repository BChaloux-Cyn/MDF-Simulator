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

_Pending. Awaiting design decision on Option A vs B._

## Change Log

| Date | File | Change |
|------|------|--------|
| | `Elevator/class-diagram.yaml` | Fix `r_queue_head_id` referential; add R11 if Option A chosen |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator accepts self-referential 0..1:0..1 association | | |
| | Validator flags referential attribute pointing to wrong association | | |
| | Validator accepts R11 head-pointer association after fix | | |
