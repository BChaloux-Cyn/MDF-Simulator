# method_call_stmt remove dispatches Map semantics to all container types

**ID:** COMP-001
**Status:** Solved
**Domain/Component:** Compiler / action language transformation

## Root Cause

In `compiler/transformer.py`, the `method_call_stmt` rule dispatched purely on method name:

```python
if method == "remove":
    return f"{obj}.pop({args}, None)"
```

This is correct for `Map` (where `remove(key)` semantically maps to `.pop(key, None)`), but `remove` is also documented for `Set` and `List` with different semantics:

- **Map**: `remove(key)` → `.pop(key, None)` (Python dict semantic)
- **Set**: `remove(x)` → `.discard(x)` (Python set semantic, silent if absent)
- **List**: `remove(x)` → `.remove(x)` (Python list semantic, raises ValueError if absent)

The name-only dispatch caused **all receivers** to emit `.pop(x, None)`, even when the receiver is a Set or List.

## Impact

**Severity:** Medium (latent — only affects Set/List `remove`, which are not yet implemented)

When Set/List mutation is implemented, `my_set.remove(x);` would emit `my_set.pop(x, None)` instead of `my_set.discard(x)`. This causes a `TypeError` at runtime: `set.pop()` does not accept positional arguments.

## Fix Applied

- Changed `remove` in `method_call_stmt` to emit `_mdf_remove(obj, arg)` (commit 67db9b6).
- Added `mdf/runtime.py` with `_mdf_remove()` that dispatches to `dict.pop`, `set.discard`, or `list.remove` at runtime based on the receiver type (commit c44171a).

## Change Log

| Date | File | Change |
|------|------|--------|
| 2026-06-30 | `tests/test_compiler_transformer.py` | Added failing test `test_remove_does_not_clobber_set_semantics` |
| 2026-06-30 | `compiler/transformer.py` | Changed `remove` to emit `_mdf_remove(obj, arg)` |
| 2026-06-30 | `mdf/runtime.py` | Added `_mdf_remove()` with type-dispatched runtime logic |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| `tests/test_compiler_transformer.py` | `test_remove_does_not_clobber_set_semantics` | YES | YES |
