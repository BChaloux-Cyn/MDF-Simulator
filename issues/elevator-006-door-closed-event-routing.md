# Door_closed Event Routed to Wrong Recipient

**ID:** ELV-006
**Status:** Open
**Domain/Component:** Elevator model (Door.yaml, Request.yaml, Elevator.yaml)

## Root Cause

`Door.yaml` `Closed` entry action:
```
generate Door_closed to r1_elevator_id;
```
This sends `Door_closed` to the `Elevator`. But `Elevator.yaml` has no `Door_closed` event
in its event list — its transition from `At_Floor` is triggered by `Service_complete`.

Meanwhile, `Request.yaml` **does** expect a `Door_closed` event to drive the
`Serving → Complete` transition:
```yaml
- from: Serving
  to: Complete
  event: Door_closed
```
And `Request.Complete` entry action sends `Service_complete` to the elevator:
```
generate Service_complete to r2_elevator_id;
```

So the correct chain is:
```
Door enters Closed
  → generate Door_closed to <active Request>
  → Request: Serving → Complete
  → Request.Complete entry: generate Service_complete to Elevator
  → Elevator: At_Floor → Idle
```

The `Door` must target the `Request` that is currently being served, not the `Elevator`
directly. The `Door` doesn't currently have a reference to the active `Request` — it only
holds `r1_elevator_id`. Options:

**Option A:** The `Door` generates `Door_closed` to `r1_elevator_id` (the Elevator), and the
`Elevator` adds `Door_closed` to its event list and relays it to the active `Request`. This
adds indirection but keeps `Door` decoupled from `Request`.

**Option B:** Add a referential on `Door` to the currently-serving `Request` (a new
association, e.g., R12: `Door` 0..1 --- 0..1 `Request`). `Door` generates `Door_closed`
directly to the `Request`.

**Option C:** Remove `Door_closed` from `Request`'s events. Instead, the `Elevator` receives
`Door_closed`, transitions `At_Floor → Idle`, and as part of the `Idle` entry action it
advances the `Request` to `Complete` (or generates `Service_complete` directly). This
simplifies routing but puts more logic in the `Elevator`.

Current recommendation: **Option A** — minimal model change, keeps coupling low.

## Fix Applied

_Pending. Awaiting design decision on routing option._

## Change Log

| Date | File | Change |
|------|------|--------|
| | `Elevator/state-diagrams/Elevator.yaml` | Add `Door_closed` event (Option A) or adjust At_Floor→Idle trigger |
| | `Elevator/state-diagrams/Door.yaml` | Confirm or update target of `Door_closed` generate |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | Validator flags `generate <event>` where event is not defined on the target class | | |
| | Door closed sequence: Door→Closed → Request→Complete → Elevator→Idle (integration) | | |
