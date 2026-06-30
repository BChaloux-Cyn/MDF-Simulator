# Generated Code Has Enum/Typedef Assignment Type Mismatches

**ID:** CODEGEN-002
**Status:** Open
**Domain/Component:** Compiler / codegen

## Root Cause

Generated action code assigns enum and typedef values (e.g. `FloorNumber`, `Direction`)
to `TypedDict` fields typed as the nominal MDF type. Mypy reports `[assignment]` errors
because it sees the right-hand side as `int` or `str` (the underlying Python type) while
the TypedDict field is typed with the nominal name.

This is a consequence of nominal typing (constraint in the plan): `FloorNumber` and `int`
are intentionally distinct, but the generated assignment code does not use explicit casts,
causing mypy to flag the mismatch.

## Fix Applied

(Not yet applied.)

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | | | |
