# method_call_stmt remove dispatches Map semantics to all container types

**ID:** COMP-001
**Status:** Open
**Domain/Component:** Compiler / action language transformation

## Root Cause

In `compiler/transformer.py`, the `method_call_stmt` rule dispatches purely on method name:

```python
if method == "remove":
    return f"{obj}.pop({args}, None)"
```

This is correct for `Map` (where `remove(key)` semantically maps to `.pop(key, None)`), but `remove` is also documented for `Set` and `List` with different semantics:

- **Map**: `remove(key)` → `.pop(key, None)` (Python dict semantic)
- **Set**: `remove(x)` → `.remove(x)` (Python set semantic, raises KeyError if absent)
- **List**: `remove(x)` → `.remove(x)` (Python list semantic, raises ValueError if absent)

The current name-only dispatch causes **all receivers** to emit `.pop(x, None)`, even when the receiver is a Set. This is latent because Set/List mutation is listed as "Not yet implemented" in `docs/design/SYNTAX.md §13`, so no test exercises it yet.

## Impact

**Severity:** Medium (latent — only affects Set/List `remove`, which are not yet implemented)

When Set/List mutation is implemented, `my_set.remove(x);` will emit `my_set.pop(x, None)` instead of `my_set.remove(x)`. This causes a `TypeError` at runtime: `set.pop()` does not accept positional arguments.

## Fix Applied

None yet. The fix requires type-aware dispatch in `method_call_stmt` to determine the receiver type and emit the correct transformation. This should be deferred until Set/List mutation is implemented in Phase 5.

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-06-30 | `tests/test_compiler_transformer.py` | Added failing test `test_remove_does_not_clobber_set_semantics` |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| `tests/test_compiler_transformer.py` | `test_remove_does_not_clobber_set_semantics` | YES (emits `pop` instead of `remove`) | Pending fix |
