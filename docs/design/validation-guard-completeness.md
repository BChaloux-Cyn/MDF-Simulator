# Guard Completeness Validation — Design Reference

## Overview

Guard completeness validation (`_check_guard_completeness` in `tools/validation.py`) checks that
every `(from_state, event)` pair in a state diagram has a well-formed, non-ambiguous, and
collectively exhaustive set of guard expressions. The check runs after referential integrity and
before reachability, once per active class state diagram. Analysis uses Z3 SMT solving and covers
simple comparisons, compound AND/OR guards, and multi-variable guards.

---

## 1. What "Guard Completeness" Means in xUML

In xUML / Shlaer-Mellor, a state machine is deterministic: when an event arrives at a state,
exactly one transition must fire. If multiple transitions exist for the same `(from_state, event)`
pair, each must carry a guard, and the guards must collectively cover every possible value of the
discriminating parameter with no overlap.

Formally, for a group of transitions `{T1, T2, ..., Tn}` from state `S` on event `E`:

- **No ambiguity:** at most one transition may be unguarded. If unguarded, it must be the only
  transition in the group.
- **Exhaustiveness:** the union of all guard predicates must cover the full domain of the
  discriminating variable.
- **Non-overlap:** no two guards should simultaneously be true for the same input. (Overlap
  detection is implicit in the Z3 satisfiability check — if guards overlap, the coverage check
  still passes, but the model is semantically wrong. Full overlap detection is a known limitation;
  see section 6.)

---

## 2. Grouping and Entry Conditions

The validator groups all transitions in the state diagram by `(from_state, event)`. Each group is
analyzed independently. The `StateDiagramFile.check_guard_consistency` model validator (in
`schema/yaml_schema.py`) enforces a prerequisite: within any group, guards must be all-or-nothing —
either every transition has a guard, or none do. A mix raises a `ValidationError` at parse time and
never reaches the completeness check.

Groups that are skipped entirely:

- A single unguarded transition (normal, deterministic by construction).
- Any transition whose guard string fails to parse (a warning is issued; the group is abandoned).
- Groups where a guard expression is too complex for Z3 conversion (arithmetic operands in
  comparisons, unsupported constructs) — a warning is issued.
- Groups where the discriminating variable is not an event parameter (an error is issued).
- Groups where the type is a struct, `UniqueID`, `Boolean` primitive, or otherwise non-analyzable
  (an error is issued).
- Groups where Z3 returns `unknown` — a warning is issued.

---

## 3. Z3-Based Completeness Analysis

### 3.1 Algorithm

For each `(from_state, event)` group with `n` guarded transitions:

1. Parse all guard strings into Lark parse trees.
2. Collect all variable names referenced on the left-hand side of comparisons.
3. For each variable, resolve its type from event params and `types.yaml`.
4. Build a Z3 variable (Int or Real sort) and domain constraints for each variable:
   - `EnumType` → `Int` with `Or(var==0, ..., var==n-1)` domain
   - `Integer` or `ScalarType(Integer)` → `Int` with optional range bounds
   - `Real` or `ScalarType(Real)` → `Real` with optional range bounds
5. Convert each guard parse tree to a Z3 formula via `_tree_to_z3`.
6. Check satisfiability of `NOT(g1 OR g2 OR ... OR gn)` under the domain constraints.

The check asks: *is there any variable assignment that satisfies the domain but is not covered by
any guard?* If SAT → incomplete (error with counterexample). If UNSAT → complete. If unknown →
warning.

Integer variables use Z3 `Int` sort; Real variables use Z3 `Real` sort. The type distinction is
exact — a gap between `x <= 5` and `x >= 6` yields no integer (UNSAT) but would yield real values
like `5.5` (SAT).

### 3.2 Compound Guards (AND/OR)

The Z3 approach handles compound guards directly. A single guard like `pressure < 5 or pressure >= 5`
is converted to `Or(pressure < 5, pressure >= 5)` and checked. A group of guards where one is
`pressure > 10 and flow > 5` and another is `pressure <= 10` is combined as
`Or(And(pressure > 10, flow > 5), pressure <= 10)` for the satisfiability check.

### 3.3 Valid vs Invalid Examples

**Valid** — full coverage, no gap:

```yaml
transitions:
  - from: Idle
    to: Low
    event: Pressure_changed
    guard: "pressure < 100"
  - from: Idle
    to: High
    event: Pressure_changed
    guard: "pressure >= 100"
```

Z3 checks: `NOT(pressure < 100 OR pressure >= 100)` → UNSAT. No issue.

**Invalid** — gap at the boundary:

```yaml
transitions:
  - from: Idle
    to: Low
    event: Pressure_changed
    guard: "pressure < 100"
  - from: Idle
    to: High
    event: Pressure_changed
    guard: "pressure > 100"
```

Z3 checks: `NOT(pressure < 100 OR pressure > 100)` with domain `[0, 200]` → SAT with `pressure=100`.

Issue emitted (severity=`error`):
```
Incomplete guard on 'Idle' -> 'Pressure_changed': no guard fires when pressure=100
```

**Valid — compound OR guard covering all values:**

```yaml
transitions:
  - from: Idle
    to: Active
    event: Pressure_changed
    guard: "pressure < 5 or pressure >= 5"
```

Z3 checks: `NOT(pressure < 5 OR pressure >= 5)` → UNSAT. No issue.

---

## 4. Enum Completeness

When the discriminating variable's type resolves to an `EnumType` (from `types.yaml`), the
validator encodes enum values as integers 0..n-1 and adds an `Or(var==0, ..., var==n-1)` domain
constraint. The Z3 satisfiability check then finds any uncovered enum value.

Any missing enum values produce an `error`. The counterexample names the missing value using
the original enum label (e.g., `mode=Locked`).

**Valid:**

```yaml
# ValveMode enum: [Manual, Auto, Locked]
transitions:
  - from: Idle
    to: Manual
    event: Mode_changed
    guard: "mode == Manual"
  - from: Idle
    to: Auto
    event: Mode_changed
    guard: "mode == Auto"
  - from: Idle
    to: Locked
    event: Mode_changed
    guard: "mode == Locked"
```

Z3 checks: `NOT(mode==0 OR mode==1 OR mode==2)` with domain `Or(mode==0, mode==1, mode==2)` → UNSAT.
No issue.

**Invalid:**

Same as above but the `mode == Locked` transition is absent. Z3 finds SAT with `mode=2`.
Issue emitted (severity=`error`):
```
Incomplete guard on 'Idle' -> 'Mode_changed': no guard fires when mode=Locked
```

---

## 5. Severity Levels

| Condition | Severity |
|-----------|----------|
| Multiple unguarded transitions on same `(from, event)` | `error` |
| Guard on a `String`-typed variable (primitive or scalar alias) | `error` |
| Guard variable not in event params | `error` |
| Guard variable has unresolvable type | `error` |
| Guard completeness gap (Z3 returns SAT) | `error` |
| Guard parse failure | `warning` |
| Guard expression too complex for Z3 conversion | `warning` |
| Z3 returns `unknown` | `warning` |

`error`-severity issues represent definitive model defects that will cause runtime non-determinism
or are semantically meaningless (String guards). `warning`-severity issues represent cases where
the validator cannot prove completeness due to guard structure or solver limitations.

---

## 6. Edge Cases

### 6.1 Implicit Else / Single Unguarded Transition

A single unguarded transition in an `(from_state, event)` group is unconditionally valid. It acts
as an implicit `else` that fires for all inputs. The validator skips the group entirely without
any issue.

### 6.2 Bare Boolean Guards (Deprecated)

The `SYNTAX.md` grammar section notes that `where` clauses with bare booleans (as opposed to
lambdas) are legacy and to be migrated. Guard expressions on transitions are plain strings parsed
by the guard grammar. If a guard string reduces to a bare boolean (`true` or `false`) it will
parse but will not match the `compare_expr` structure required for analysis. The group will be
skipped silently (no issue, no coverage check). This is intentional — bare boolean guards are
effectively equivalent to an unguarded transition (`true`) or an impossible transition (`false`)
and should be refactored at the model level.

### 6.3 `rcvd_evt.` Prefix

Guard expressions use `rcvd_evt.<param>` syntax for event parameters (see SYNTAX.md section 8).
The parser produces a `dotted_name` node in this case. The validator handles `dotted_name` by
taking the second component (the parameter name) as the variable name, so
`rcvd_evt.floor_num == 3` is analyzed as if the variable were `floor_num`. The `rcvd_evt.`
prefix is stripped for lookup in the event params map.

### 6.4 Variable Not in Event Params

If the guard variable does not appear in the event's declared `params`, an `error` is issued:
the type cannot be determined at compile time. This includes guards that reference `self.attr`
(an instance attribute) rather than an event parameter. Instance-attribute guards are
syntactically valid but produce an error at this check.

### 6.5 `!=` Operator

Guards using `!=` are converted to Z3 `!=` comparisons and analyzed normally. The Z3 solver
handles disjoint coverage correctly without any special treatment.

### 6.6 Unknown Types and Struct Types

If `types.yaml` is absent or does not contain the referenced type, and the type is not a bare
`Integer` or `Real` primitive, the validator emits an `error` for unresolvable type. Bare
`Integer` and `Real` primitives are analyzed without range bounds.

### 6.7 `ScalarType` with String Base

A user-defined type with `base: String` is caught explicitly — the same `error` is raised as for
a bare `String` primitive.

---

## 7. Guard Conversion to Z3

The `_tree_to_z3` function converts a Lark parse tree to a Z3 expression. The guard grammar
produces a precedence tower: `or_expr > and_expr > compare_expr > add_expr > mul_expr > atom`.
Single-child wrapper nodes are passed through transparently.

- `or_expr` with two Tree children → `z3.Or(left, right)`
- `and_expr` with two Tree children → `z3.And(left, right)`
- `compare_expr` with three children `[left, OP, right]` → Z3 comparison
- Single-child `or_expr`/`and_expr`/`compare_expr` → pass through
- `add_expr`/`mul_expr` with a single child → pass through
- `add_expr`/`mul_expr` with multiple children (arithmetic) → `None` (not analyzable)

If any subexpression returns `None`, the entire conversion fails and the group gets a `warning`
about unsupported constructs.

---

## 8. Limitations

1. **No overlap detection.** The satisfiability check only verifies that the union of guards
   covers the domain. It does not verify mutual exclusion. A model with overlapping guards will
   not be flagged; runtime behavior would be non-deterministic.

2. **Arithmetic in guard comparisons.** Guards like `pressure + offset > 10` (arithmetic on the
   left-hand side) cannot be converted to Z3 and produce a `warning` instead of analysis.

3. **Instance-attribute guards produce errors.** Guards that reference `self.some_attr` are not
   in the event params map and are flagged as errors (unknown variable). These should be
   refactored to use event parameters or moved to entry actions.

4. **No cross-state-group completeness.** The check is per `(from_state, event)` pair. It does
   not consider whether a given `(from_state, event)` pair should even exist for all states that
   receive a given event.

5. **`types.yaml` is optional.** If absent, enum and String-alias checks cannot run. Bare
   `Integer`/`Real` guards are still analyzed for gaps, but without range bounds the analysis
   only catches gaps relative to explicitly stated constraints.
