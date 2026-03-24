# Issue Tracker — mdf-simulator

## Instructions for Claude

When you identify a bug, modeling error, schema gap, or missing test:

1. **Create an issue file** at `issues/<short-descriptive-name>.md` using the template below.
2. **Add an entry** to the Active Issues table in this manifest.
3. **Do not mark an issue solved** until:
   - The root cause is confirmed and documented.
   - All model/code/schema changes are logged in the issue file.
   - A test exists that **failed before the fix** and **passes after the fix**.
     (User testing is acceptable for visual or interactive aspects.)
4. **When solved:** move the issue file to `issues/solved/<filename>-SOLVED.md`
   and remove its row from the Active Issues table.

### Issue File Template

```markdown
# <Issue Title>

**ID:** <short-id>
**Status:** Open | In Progress | Solved
**Domain/Component:** <e.g., Elevator model, schema validator, pycca parser>

## Root Cause

<Explain what is wrong and why.>

## Fix Applied

<What was changed to resolve it. Leave blank until solved.>

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | | | |
```

---

## Active Issues

| ID | Title | Component | Status |
|----|-------|-----------|--------|
| [ELV-001](elevator-001-subtype-relvar-inheritance.md) | Subtype inherits supertype referential attributes | Schema / engine | Open |
| [DRAWIO-001](drawio-001-association-edge-routing-overlap.md) | Association edges may route through other class boxes | drawio renderer | Open |
| [DRAWIO-002](drawio-002-domain-diagram-missing.md) | No domain diagram renderer (DOMAINS.yaml → drawio) | drawio renderer | Open |
| [DRAWIO-003](drawio-003-render-overwrites-layout.md) | Render overwrites user layout changes on state diagrams | drawio renderer | Open |
| [DRAWIO-004](drawio-004-referential-annotation.md) | Draw.io should render referential annotations on attributes | drawio renderer | Open |
