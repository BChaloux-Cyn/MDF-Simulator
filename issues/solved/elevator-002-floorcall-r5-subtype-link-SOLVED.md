# FloorCall Missing Subtype Link to Call via R5

**ID:** ELV-002
**Status:** Solved
**Domain/Component:** Elevator model (class-diagram.yaml), schema, validator

## Root Cause

Two related problems:

### 1. R5 association only listed ElevatorCall as subtype

`FloorCall` declared `specializes: R5` but was not listed anywhere as a participant in R5.
The schema had no mechanism to declare multiple subtypes for a generalization — the
`SubtypePartition` model existed on `ClassDef` but was never populated and `discriminator`
was required (blocking use without an explicit discriminator attribute).

### 2. FloorCall.Fulfilled action used wrong attribute name

`FloorCall.yaml` Fulfilled entry action queried `r8_call_id` on `Request`, which does not
exist. This is a separate action-code issue tracked under future pycca traversal work.

## Fix Applied

- Made `SubtypePartition.discriminator` optional in `schema/yaml_schema.py`.
- Added partition membership check to `_check_referential_integrity_class_diagram` in
  `tools/validation.py`: for every class with `specializes: RN`, the validator now verifies
  that a supertype class in the same domain has a `partitions` entry for RN that lists this
  class in `subtypes`. Missing membership is reported as `severity: error`.
- Added `partitions` block to `Call` class in
  `examples/elevator/.design/model/Elevator/class-diagram.yaml` listing both `ElevatorCall`
  and `FloorCall` as subtypes of R5.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-11 | `schema/yaml_schema.py` | Made `SubtypePartition.discriminator` optional (`str \| None = None`) |
| 2026-03-11 | `tools/validation.py` | Added `partition_map` build + membership check in `_check_referential_integrity_class_diagram` |
| 2026-03-11 | `examples/elevator/.design/model/Elevator/class-diagram.yaml` | Added `partitions` to `Call` with subtypes `[ElevatorCall, FloorCall]` |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| `tests/test_validation.py` | `test_subtype_not_in_supertype_partition` | Yes | Yes |
| `tests/test_validation.py` | `test_subtype_listed_in_supertype_partition_no_error` | No (vacuous) | Yes |
| `tests/test_validation.py` | `test_elevator_model_no_partition_errors` | Yes | Yes |
