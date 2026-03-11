# FloorCallButton Missing Subtype Link to CallButton via R6

**ID:** ELV-004
**Status:** Solved
**Domain/Component:** Elevator model (class-diagram.yaml), schema, validator

## Root Cause

Same structural pattern as ELV-002. `FloorCallButton` declared `specializes: R6` but was
not listed in any supertype's `partitions` for R6. The validator had no check for this.

The separate issue of `CallButton.yaml` creating `ElevatorCall` for all button presses
(instead of subtype-specific state machines) is a modeling issue deferred to action-code
work — the partition fix is the structural correctness fix.

## Fix Applied

Same validator and schema changes as ELV-002 (shared fix). Additionally:
- Added `partitions` block to `CallButton` class in
  `examples/elevator/.design/model/Elevator/class-diagram.yaml` listing both
  `DestFloorButton` and `FloorCallButton` as subtypes of R6.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-11 | `schema/yaml_schema.py` | `SubtypePartition.discriminator` made optional (shared with ELV-002) |
| 2026-03-11 | `tools/validation.py` | Partition membership check added (shared with ELV-002) |
| 2026-03-11 | `examples/elevator/.design/model/Elevator/class-diagram.yaml` | Added `partitions` to `CallButton` with subtypes `[DestFloorButton, FloorCallButton]` |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| `tests/test_validation.py` | `test_subtype_not_in_supertype_partition` | Yes | Yes |
| `tests/test_validation.py` | `test_subtype_listed_in_supertype_partition_no_error` | No (vacuous) | Yes |
| `tests/test_validation.py` | `test_elevator_model_no_partition_errors` | Yes | Yes |
