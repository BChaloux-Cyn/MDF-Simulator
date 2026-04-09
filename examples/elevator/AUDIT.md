# Elevator Model Audit

Audit of the elevator example model against the rules defined in
`docs/design/SYNTAX.md` and `docs/design/COMPILATION.md`.

Date: 2026-03-18

---

## Validator Coverage

`validate_model()` returns **zero issues** for this model. All 15 issues
identified below live in action body content (entry actions, transition
actions), which the current validator treats as opaque strings.

**What the validator checks:**
- YAML schema conformance (Pydantic models)
- Association endpoints reference existing class names
- State diagram integrity (transitions reference valid states/events)
- State reachability via NetworkX graph analysis
- Guard completeness (enum value coverage on guarded transitions)

**What the validator does NOT check (all audit findings fall here):**
- Action body semantics — no parsing of `generate`, `select`, `create`, etc.
- Generate target validity — event existence on target class, param matching
- Attribute existence on cross-instance access
- Relationship traversal correctness
- Mandatory relationship satisfaction after `create`
- Supertype/subtype creation protocol

Action-level semantic validation would require extending the pycca grammar
parser (currently a subset in `pycca/grammar.py`) into a full semantic
analyzer that cross-references the class diagram, state diagrams, and types.
This is a natural fit for Phase 5 (Simulation Engine) or a dedicated
validation phase.

---

## Issue Summary

| # | Category | Severity | File | Line(s) | Status |
|---|----------|----------|------|---------|--------|
| 1a | Invalid generate target | error | Door.yaml | 11 | open |
| 1b | Invalid generate target | error | Request.yaml | 15 | open |
| 1c | Invalid generate target | error | ElevatorCall.yaml | 12 | open |
| 1d | Invalid generate target | error | FloorCall.yaml | 14 | open |
| 1e | Wrong event on target class | error | Elevator.yaml | 60 | open |
| 2a | Non-existent attribute | error | Dispatcher.yaml | 24,42,53 | open |
| 3a | Missing mandatory relate | error | Dispatcher.yaml | 24-28,42-46,53-55 | open |
| 4a | Missing supertype creation | error | CallButton.yaml | 14-16 | open |
| 5a | Event param name mismatch | error | Shaft.yaml | 30,43 | open |
| 6a | Direct referential access | warning | Elevator.yaml | 23,47 | open |
| 7a | Unused event declaration | info | Elevator.yaml | 16 | open |
| 8a | rcvd_evt on initial state | warning | ElevatorIndicator.yaml | 12 | open |
| 9a | Missing else branch | warning | Elevator.yaml | 47-54 | open |
| D1 | Doc ambiguity: where clause names | info | SYNTAX.md / COMPILATION.md | — | open |

Error: 7 | Warning: 3 | Info: 2

---

## Category 1: Invalid Generate Targets

**Rule:** SYNTAX.md §1.2 — valid generate targets are `self` or a variable
bound by a prior `select` or `create`. COMPILATION.md §5.3 — relvars are not
directly accessible; all navigation goes through `select ... related by`.

### 1a. Door.yaml — Closed entry action

```yaml
# Current (line 11)
entry_action: "generate Door_closed to r1_elevator_id;"
```

`r1_elevator_id` is a bare name, never bound by `select` or `create`.
Even as `self.r1_elevator_id`, it is a UniqueID value, not an instance reference.

```yaml
# Fix
entry_action: >-
  select any elev related by self->R1;
  generate Door_closed to elev;
```

### 1b. Request.yaml — Complete entry action

```yaml
# Current (line 15)
entry_action: "generate Service_complete to self.r2_elevator_id;"
```

`self.r2_elevator_id` is a referential attribute (UniqueID), not an instance.

```yaml
# Fix
entry_action: >-
  select any elev related by self->R2;
  generate Service_complete to elev;
```

### 1c. ElevatorCall.yaml — Fulfilled entry action

```yaml
# Current (line 12)
entry_action: "generate Call_fulfilled to self.r7_button_id;"
```

Same pattern — UniqueID value used as generate target.
Note: ElevatorCall inherits R7 from Call via R5 generalization.

```yaml
# Fix
entry_action: >-
  select any button related by self->R7;
  generate Call_fulfilled to button;
```

### 1d. FloorCall.yaml — Fulfilled entry action

```yaml
# Current (lines 13-16)
entry_action: >-
  generate Call_fulfilled to self.r7_button_id;
  select any req from instances of Request where request_id == self.r8_request_id;
  if (req != empty) { generate Request_cancelled to req; }
```

Same `self.r7_button_id` issue. Also uses `self.r8_request_id` directly
in where clause (see issue 6a).

```yaml
# Fix
entry_action: >-
  select any button related by self->R7;
  generate Call_fulfilled to button;
  select any req related by self->R8;
  if (req != empty) { generate Request_cancelled to req; }
```

### 1e. Elevator.yaml — At_Floor entry action (Open_door to self)

```yaml
# Current (line 60)
generate Open_door to self;
```

`Open_door` is an event on **Door**, not on Elevator.
Elevator's declared events: Request_assigned, Floor_reached, Stopped,
Service_complete, Elevator_available, Door_closed.

Violates COMPILATION.md §13.3: "Event exists on target class."

```yaml
# Fix
select any door related by self->R1;
generate Open_door to door;
```

---

## Category 2: Non-Existent Attribute Access

### 2a. Dispatcher.yaml — fc.destination_floor

```yaml
# Current (appears in 3 transition actions: lines 24, 42, 53)
req.destination_floor = fc.destination_floor;
```

`fc` is a FloorCall instance. FloorCall's declared attributes are
`floor_num` (FloorNumber) and `direction` (CallDirection), plus inherited
`call_id`, `r7_button_id`, `r8_request_id` from Call supertype.
There is no `destination_floor` attribute on FloorCall.

```yaml
# Fix
req.destination_floor = fc.floor_num;
```

---

## Category 3: Missing Mandatory Relationship Relate

**Rule:** COMPILATION.md §5.2 — relationships with multiplicity `1` are
mandatory. If a function body creates an instance that participates in a
mandatory relationship and does not `relate` it before the function returns,
the runtime raises an error.

### 3a. Dispatcher.yaml — Request created without R2 relate

```yaml
# Current (3 transition actions)
create req of Request;
req.destination_floor = fc.destination_floor;
select any elev from instances of Elevator;
generate Request_assigned(target_floor: req.destination_floor) to elev;
```

R2 (Elevator 1 --- 0..* Request) has multiplicity `1` on the Request side.
Every Request must be related to exactly one Elevator. The `relate` is missing.

```yaml
# Fix
create req of Request;
req.destination_floor = fc.floor_num;
relate req to elev across R2;
select any elev from instances of Elevator;
generate Request_assigned(target_floor: req.destination_floor) to elev;
```

Note: The `relate` must come after both `req` and `elev` are bound.
Reordering is needed — `select any elev` must precede `relate`.

```yaml
# Corrected order
select any elev from instances of Elevator;
create req of Request;
req.destination_floor = fc.floor_num;
relate req to elev across R2;
generate Request_assigned(target_floor: req.destination_floor) to elev;
```

---

## Category 4: Missing Supertype Creation

**Rule:** COMPILATION.md §9.4 — creating a subtype requires creating both
the supertype and subtype instances and relating them via the generalization.

### 4a. CallButton.yaml — ElevatorCall created without Call supertype

```yaml
# Current (lines 14-16)
action: >-
  create ec of ElevatorCall;
  relate ec to self across R7;
  select any disp from instances of Dispatcher;
  generate Call_submitted(has_idle_elevator: disp.has_idle_elevator) to disp;
```

Two problems:
1. No `Call` supertype instance is created
2. `relate ec to self across R7` — R7 links CallButton to **Call**, not
   to ElevatorCall directly

```yaml
# Fix
action: >-
  create call of Call;
  create ec of ElevatorCall;
  relate ec to call across R5;
  relate call to self across R7;
  select any disp from instances of Dispatcher;
  generate Call_submitted(has_idle_elevator: disp.has_idle_elevator) to disp;
```

---

## Category 5: Event Parameter Name Mismatch

**Rule:** COMPILATION.md §7 — parameter names in `generate` must match the
event definition on the target class.

### 5a. Shaft.yaml — Floor_reached parameter name

```yaml
# Current (lines 30, 43)
generate Floor_reached(floor_num: self.current_floor) to elev;
```

Elevator's `Floor_reached` event declares a parameter named `current_floor`:
```yaml
# Elevator.yaml events
- name: Floor_reached
  params:
    - name: current_floor
      type: FloorNumber
```

The generate uses `floor_num` but the event definition says `current_floor`.

```yaml
# Fix
generate Floor_reached(current_floor: self.current_floor) to elev;
```

---

## Category 6: Direct Referential Attribute Access

**Rule:** COMPILATION.md §5.3 — relvars are not directly accessible in pycca
code. All navigation goes through relationship traversal (`select ... related by`)
and link management goes through `relate`/`unrelate`.

### 6a. Elevator.yaml — self.r14_request_id in where clause

```yaml
# Current (lines 23, 47)
select any req from instances of Request where request_id == self.r14_request_id;
```

`self.r14_request_id` directly accesses a referential attribute.
The simpler and rule-compliant approach is relationship traversal:

```yaml
# Fix
select any req related by self->R14;
```

This is both cleaner and follows the compilation rules.

---

## Category 7: Unused Event Declaration

### 7a. Elevator.yaml — Elevator_available event

```yaml
# Line 16
- name: Elevator_available
```

`Elevator_available` is declared in Elevator's event list but no transition
on Elevator ever consumes it. The event is only meaningful on the Dispatcher
class (which correctly declares and consumes it).

The Idle entry action generates `Elevator_available` **to** the Dispatcher,
not to self. Declaring it on Elevator is harmless but misleading — it
suggests an incomplete state model.

**Recommendation:** Remove from Elevator's event list.

---

## Category 8: rcvd_evt on Initial State Entry

**Rule:** COMPILATION.md §6.3 — `rcvd_evt` is available in entry actions
because the entry executes as part of the same micro-step as the transition.
But the initial pseudo-transition has no triggering event.

### 8a. ElevatorIndicator.yaml — Displaying entry action

```yaml
# Line 12
entry_action: "self.displayed_floor = rcvd_evt.floor_num;"
```

`Displaying` is the initial state. On creation, the state machine enters
this state via the initial pseudo-transition, which has no event payload.
`rcvd_evt.floor_num` would be undefined.

**Options:**
- Add an initialization state with no entry action, transition to
  Displaying on the first Floor_updated event
- Guard the access: `if (rcvd_evt != empty) { self.displayed_floor = rcvd_evt.floor_num; }`
- Accept as a convention that `rcvd_evt` fields default to zero on
  initial entry (document this)

---

## Category 9: Logic Gap

### 9a. Elevator.yaml — At_Floor missing else for equal floors

```yaml
# Lines 47-54
if (next_req.destination_floor > self.current_floor) { self.next_direction = Up; }
if (next_req.destination_floor < self.current_floor) { self.next_direction = Down; }
```

If `next_req.destination_floor == self.current_floor`, neither branch fires.
`self.next_direction` retains its previous value, which may be stale.

```yaml
# Fix — use else-if chain
if (next_req.destination_floor > self.current_floor) { self.next_direction = Up; }
else if (next_req.destination_floor < self.current_floor) { self.next_direction = Down; }
else { self.next_direction = Stopped; }
```

---

## Documentation Ambiguity: Where Clause Name Resolution

**Files:** docs/design/SYNTAX.md §2, docs/design/COMPILATION.md §11.1

The model consistently uses bare attribute names in `where` clauses to
reference the candidate instance's attributes:
```
select any fc from instances of FloorCall where floor_num == self.current_floor;
```

Here `floor_num` (bare) = candidate FloorCall attribute,
`self.current_floor` = the caller Elevator's attribute.

However:
- SYNTAX.md §2 says bare names must be bound by a prior `select`/`create`/declaration
- COMPILATION.md §11.1 says "`self.` in where clauses refers to each candidate
  instance being tested"

These two rules conflict. If `self.` means the candidate in where clauses,
then the caller has no way to reference its own attributes. The codebase
convention (bare = candidate, `self.` = caller) contradicts §11.1.

**Recommendation:** Clarify in both documents that where clauses have special
scoping: bare attribute names resolve against the candidate class, and `self.`
retains its normal meaning (the current instance executing the action).
