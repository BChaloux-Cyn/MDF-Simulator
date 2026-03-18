# Realized domains should not require class-diagram.yaml

**ID:** VAL-001
**Status:** Open
**Domain/Component:** validation

## Root Cause

The validator requires every domain listed in DOMAINS.yaml to have a
`class-diagram.yaml` file. Realized domains (type: "realized") are
external/bridge-only — they have no classes, associations, or state
machines of their own. Requiring a class-diagram.yaml forces the
creation of an empty stub file (e.g., `Transport/class-diagram.yaml`
with empty lists) just to satisfy validation.

## Fix Applied

*Not yet applied.* The validator should skip the class-diagram.yaml
check for domains where `type == "realized"` in DOMAINS.yaml.

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | | | |
