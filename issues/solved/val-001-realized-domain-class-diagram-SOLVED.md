# Realized domains should not require class-diagram.yaml

**ID:** VAL-001
**Status:** Solved
**Domain/Component:** validation

## Root Cause

The validator requires every domain listed in DOMAINS.yaml to have a
`class-diagram.yaml` file. Realized domains (type: "realized") are
external/bridge-only — they have no classes, associations, or state
machines of their own. Requiring a class-diagram.yaml forces the
creation of an empty stub file just to satisfy validation.

## Fix Applied

`validate_model()` now skips domains where `domain_entry.type == "realized"`
in DOMAINS.yaml. Realized domains are not validated for class-diagram.yaml,
state diagrams, or any other internal model artifacts.

The empty Transport/class-diagram.yaml stub was removed.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-24 | tools/validation.py | Skip realized domains in validate_model loop |
| 2026-03-24 | examples/elevator/.design/model/Transport/class-diagram.yaml | Removed empty stub |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| tests/test_elevator.py | test_elevator_model_clean | N/A (no false positive) | Yes |
