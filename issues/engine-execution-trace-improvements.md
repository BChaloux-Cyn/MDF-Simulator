# Engine Execution Trace Improvements

**ID:** engine-execution-trace-improvements
**Status:** Open
**Domain/Component:** engine (scheduler, microstep, simulation tool)

## Root Cause

Two categories of issues: simulation clock behavior, and trace format gaps.

### Clock / Scheduler

7. **Simulator terminates early when delay queue has pending events** — the `execute()`
   loop in `engine/scheduler.py` breaks when the priority and standard queues are both
   empty, even if the delay queue still contains pending events. `tick_delay_queue` only
   moves events where `expiry <= clock.now()`, and since the clock never advances during
   the loop, delayed events are stranded. Any scenario relying on delayed events (door
   timers, travel timers, etc.) terminates prematurely. The scenario YAML triggers in
   Scenario 1 (`Done_opening`, `Close_cmd`, `Done_closing`) exist solely to mask this bug.
   **Fix:** when both immediate queues are empty and `self._delay` is non-empty, advance
   the clock to `self._delay[0][0]` (the next expiry) and `continue` rather than `break`.

8. **No fast-forward mode — tests with delays take real wall-clock time** — even once
   the clock auto-advances, `duration_s(10)` delays would require 10 seconds of real
   time if the clock tracks wall time. The full Scenario 1 door cycle (Opening 10s +
   Open 5s + Closing 10s) would take 25+ real seconds per test. The simulator needs a
   fast-forward mode: the clock always jumps directly to the next delay expiry rather
   than sleeping. This is standard discrete-event simulation behavior. Scenario 1 should
   complete in milliseconds regardless of the modeled delay values.

### Trace Format

The current micro-step trace format is missing information needed to follow execution
at the level of individual instances, events, and action statements. Several gaps were
identified while reviewing scenario 1 traces:

1. **`ActionExecuted` missing `class_name` and `instance_id`** — there is no way to
   know which instance executed the action. The scheduler has this information at
   emit time but does not pass it to the dataclass.

2. **One `ActionExecuted` per action function, not per pycca statement** — action
   functions may contain multiple pycca statements. The trace collapses the entire
   action body into a single record, making it impossible to identify which statement
   executed or to set a logical breakpoint at a particular line.

3. **No timestamps** — micro-step records carry no timing information. Adding a
   monotonic timestamp (in ms from program start) to every record enables execution
   profiling and sequencing across parallel traces.

4. **No unique step ID** — records have no stable identifier. A sequential `step_id`
   field on every record allows a JSON consumer to reference any specific step by ID
   without scanning the full trace.

5. **Events have no ID; generated and absorbed events are not linked** — when
   `GenerateDispatched` emits an event and `EventReceived` later absorbs it, there
   is no shared token linking the two records. An `event_id` on `GenerateDispatched`
   that appears again on the corresponding `EventReceived` (and `SchedulerSelected`)
   would let a reader trace a single event from creation to consumption.

6. **ShaftDoor receives Door_open as a priority event when it should not** — in
   Scenario 1, CarDoor sends Door_open to ShaftDoor. Even though both are Door
   subtypes, they are distinct instances with different `door_id` values. The current
   `_classify_queue` in the scheduler compares `sender_id == target_id` (dict equality),
   which should correctly route this as standard. Needs verification that the priority/
   standard classification is correct for cross-instance events between subtypes sharing
   a base class.

## Fix Applied

_Leave blank until solved._

## Change Log

| Date | File | Change |
|------|------|--------|
| | | |

## Tests Added

| Test file | Test name | Fails before fix | Passes after fix |
|-----------|-----------|-----------------|-----------------|
| | | | |

## Investigation Notes

### Item 7 — Early termination when delay queue has pending events

`engine/scheduler.py` `execute()` loop (line ~329): the `else: break` fires when
`self._priority` and `self._standard` are both empty, without checking `self._delay`.
Fix is a two-line change:

```python
elif self._delay:
    next_expiry, _, _ = self._delay[0]
    self._clock.advance_to(next_expiry)
    # loop continues → tick_delay_queue() will drain it
else:
    break
```

Requires `SimulationClock` to expose an `advance_to(ms)` method (or equivalent).

### Item 8 — Fast-forward mode

The `SimulationClock` in `engine/clock.py` should run in fast-forward mode by default
for simulation: `now()` returns an internal counter, `advance_to(ms)` sets it directly
with no real-time sleep. Item 7's fix naturally produces fast-forward behavior as long
as the clock does not sleep. Verify that `SimulationClock` already does this, or add
a `fast_forward=True` constructor flag that disables any wall-clock coupling.

### Item 1 — `ActionExecuted` class/instance context
The scheduler yields `ActionExecuted` at two call sites in `scheduler.py` (lines ~458
and ~524). Both have `concrete_class` / `concrete_id` in scope. Fix is straightforward:
add `class_name: str` and `instance_id: dict` fields to the `ActionExecuted` dataclass
and pass them at both yield sites.

### Item 2 — Per-statement `ActionExecuted`
Action functions are rendered as monolithic Python functions in `compiler/codegen.py`
(`_render_action_fn`). The full pycca body is transformed to Python by
`compiler/transformer.py:transform_action` and inlined as a single function body.

To emit one record per statement we need to either:
- (A) Refactor generated action functions into a list of `(pycca_src, callable)` pairs
  executed sequentially by the scheduler, or
- (B) Annotate each generated function with a `__pycca_lines__` attribute listing the
  source lines, and have the scheduler emit one `ActionExecuted` per line after the
  function completes (assignments only on the last/relevant line).

Option A gives accurate per-statement assignments; Option B is lower risk.
Decision needed before implementation.

### Item 3 — Timestamps
Add a `timestamp_ms: float` field to `MicroStep` base class using `time.monotonic()`
captured at `_write_trace` call time (relative to a start time captured when the run
begins) — or add it in the serialization step in `_step_to_dict`. The latter avoids
changing frozen dataclasses; the former puts timing in the engine where it belongs.

### Item 4 — Step IDs
A simple sequential counter in `_write_trace` (or in the scheduler's execute loop) can
assign `step_id: int` starting at 0 to each record during serialization.

### Item 5 — Event IDs
Add `event_id: int` to the `Event` dataclass. Assign a monotonic counter in the
scheduler when an event is enqueued (`_event_id_counter`). Propagate the ID to:
- `GenerateDispatched.event_id`
- `EventDelayed.event_id`
- `EventReceived.event_id`
- `SchedulerSelected.event_id`
This lets a reader find every record related to one event dispatch.

### Item 6 — Queue classification for subtype cross-instance events
The `_classify_queue` rule is: `sender_id == target_id` → priority. For Door subtypes
sharing the same `door_id` value but being different classes, verify whether dict
equality correctly distinguishes them. If CarDoor `{door_id: 1}` sends to ShaftDoor
`{door_id: 1}`, `sender_id == target_id` is `True` but they are different instances.
The queue classifier compares only the `id` dict, not the class. Fix: priority queue
should require both `sender_class == target_class` AND `sender_id == target_id`.
(The current code at `scheduler.py:_classify_queue` already checks both class and id —
confirm this is enforced and write a test.)
