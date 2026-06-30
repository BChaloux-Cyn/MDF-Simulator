# Generated Code Uses Domain Class Names Without Imports

**ID:** CODEGEN-001
**Status:** Open
**Domain/Component:** Compiler / codegen

## Root Cause

Generated class modules use domain class names (e.g. `Car`, `Floor`) as local type
annotations in `typed_var_decl` output (`var: DomainClass = ...`). These names are not
imported in the generated file, so mypy reports `[name-defined]` errors.

The names are valid at runtime (all classes are in scope when the bundle is loaded by
the engine), but mypy cannot verify them statically without import stubs.

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
