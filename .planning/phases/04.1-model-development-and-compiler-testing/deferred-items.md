# Deferred Items — Phase 04.1

## Out-of-scope discoveries (pre-existing failures)

### test_attribute_visibility_scope_defaults and test_attribute_visibility_scope_explicit

**Discovered during:** Phase 04.1 Plan 01 (Task 2)
**Status:** Pre-existing failures, not caused by formalizes removals

**Issue:** `schema/yaml_schema.py` Attribute visibility is `Literal["public", "private"]` but
the test `test_attribute_visibility_scope_defaults` expects `"private"` as default (gets `"public"`),
and `test_attribute_visibility_scope_explicit` uses `"protected"` which the schema rejects.

**Root cause:** Schema visibility field has wrong default or wrong Literal set.

**Action needed:** Fix `ClassDef` Attribute and Method visibility Literal to include `"protected"`,
and set the default to `"private"`. Likely a Phase 04.1 later plan fix, or standalone fix.

**Files:** `schema/yaml_schema.py`, `tests/test_yaml_schema.py`
