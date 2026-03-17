# Subtype Inherits Supertype Referential Attributes

**ID:** ELV-001
**Status:** Open
**Domain/Component:** Schema validator / simulation engine

## Root Cause

`ElevatorCall.Fulfilled` entry action references `r7_button_id`:
```
generate Call_fulfilled to r7_button_id;
```
`r7_button_id` is declared on `Call` (the supertype) via association R7, not on `ElevatorCall`
directly. `ElevatorCall` specializes `Call` via R5, so it should inherit all of `Call`'s
referential attributes — including `r7_button_id`.

The validator and engine do not yet model subtype attribute inheritance, so this reference
would be flagged as missing or fail at runtime.

Additionally, a naming convention for implicitly-derived referential attributes must be
established. Referential attributes are not always declared explicitly in the class YAML —
they are implied by the association definition. The expected naming scheme is:
```
r<N>_<target_identifier_attr>
```
e.g., `r7_button_id` = R7 pointing to `CallButton`, whose identifier is `button_id`.

## Fix Applied

Partial fix applied in Phase 04.1 Plan 02:

1. **Model fix (ELV-001):** Removed redundant `call_id` attribute from `ElevatorCall` and
   `FloorCall` — both subtypes no longer re-declare the identifier inherited from `Call`.

2. **Validator fix:** Added `_get_effective_attributes(cls, class_map)` helper to
   `tools/validation.py`. This function merges supertype identifier attributes with subtype
   own attributes. A new check in `_check_referential_integrity_class_diagram` flags any
   subtype that re-declares an identifier attribute already present on the supertype.

Remaining work: The validator does not yet resolve implicit relvar references (e.g.,
`r7_button_id` inherited by `ElevatorCall` from `Call`) in action body expressions.
That requires the compiler layer (Phase 5) to use `_get_effective_attributes` during
name resolution.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-03-17 | `Elevator/class-diagram.yaml` | Removed `call_id` from ElevatorCall and FloorCall |
| 2026-03-17 | `tools/validation.py` | Added `_get_effective_attributes`; added subtype re-declaration check |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator does not flag inherited relvar reference in subtype action | | |
| | Validator resolves implicit relvar name from association + target identifier | | |
