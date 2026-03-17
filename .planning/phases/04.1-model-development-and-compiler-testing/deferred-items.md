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

---

### validate_model: subtype re-declares identifier attribute (DestFloorButton, FloorCallButton)

**Discovered during:** Phase 04.1 Plan 05 (overall verification)
**Status:** Pre-existing issue in class-diagram.yaml, out of scope for Plan 05

**Issue:** validate_model reports "Subtype 'DestFloorButton' re-declares identifier attribute 'button_id'
that exists on its supertype" (same for FloorCallButton). Both subtypes inherit `button_id` from
the ButtonBase supertype via R6 but also explicitly declare it.

**Fix:** Remove `button_id` attribute declaration from both `DestFloorButton` and `FloorCallButton`
in `examples/elevator/.design/model/Elevator/class-diagram.yaml`.

**Files:** `examples/elevator/.design/model/Elevator/class-diagram.yaml`

---

### validate_model: FloorIndicator guard completeness (Showing_Up, Showing_Down -> Direction_set)

**Discovered during:** Phase 04.1 Plan 05 (overall verification)
**Status:** Pre-existing model gap, out of scope for Plan 05

**Issue:** The FloorIndicator state machine has `Direction_set` transitions from `Showing_Up` and
`Showing_Down` for some direction values but not all. Validator reports missing guard values
(Down/Stopped from Showing_Down; Stopped/Up from Showing_Up).

**Fix:** Add self-loop transitions for the unhandled guard values on each state, or model them
as explicit no-ops. Likely addressed in Plan 06 alongside broader model cleanup.

**Files:** `examples/elevator/.design/model/Elevator/state-diagrams/FloorIndicator.yaml`
