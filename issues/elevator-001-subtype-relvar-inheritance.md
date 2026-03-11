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

_Pending._

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator does not flag inherited relvar reference in subtype action | | |
| | Validator resolves implicit relvar name from association + target identifier | | |
