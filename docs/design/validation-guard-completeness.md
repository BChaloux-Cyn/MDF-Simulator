# Guard Completeness Validation — Design Reference

## Overview

Guard completeness validation (`_check_guard_completeness` in `tools/validation.py`) checks that
every `(from_state, event)` pair in a state diagram has a well-formed, non-ambiguous, and
collectively exhaustive set of guard expressions. The check runs after referential integrity and
before reachability, once per active class state diagram.

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
  detection is implicit in the interval gap check — if two intervals overlap the coverage check
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
- Groups containing compound `AND`/`OR` guards (a warning is issued; see section 5).
- Groups where comparisons reference more than one variable (multi-variable guards cannot be
  analyzed as a single interval space).
- Groups where the discriminating variable is not an event parameter (type cannot be resolved).
- Groups where the type is a struct, `UniqueID`, `Boolean` primitive, or otherwise non-analyzable.

---

## 3. Interval Arithmetic for Numeric Guards

### 3.1 Representation

Each simple comparison `variable OP literal` is mapped to a half-open interval `[lo, hi)` using
integer-compatible normalization. The mapping is defined in `_normalize_interval`:

| Guard expression | Interval          |
|------------------|-------------------|
| `x < N`          | `(-inf, N)`       |
| `x <= N`         | `(-inf, N+1)`     |
| `x > N`          | `(N+1, +inf)`     |
| `x >= N`         | `(N, +inf)`       |
| `x == N`         | `(N, N+1)`        |
| `x != N`         | *(not analyzed)*  |

The `+1` normalization on `<=` and `>` allows Real-typed guards to be treated uniformly with
Integer guards. The trade-off is that for Real types, the normalization is an approximation: a gap
between `x < 5.0` and `x > 5.0` is detected as `[5, 6)` rather than the true point `{5.0}`. This
is acceptable because the validator's goal is to surface likely modeling errors, not to prove
mathematical completeness for continuous domains.

`x != N` is treated as unanalyzable and causes the group to be skipped.

### 3.2 Gap Detection

All intervals for a group are collected into a list. Then:

**With a declared `range`** (e.g., `ScalarType.range: [0, 200]`):

The declared range is used as the analysis window `[range_lo, range_hi)` where `range_hi =
declared_hi + 1` (inclusive high converted to exclusive). The function `_intervals_cover_range`
sweeps from `range_lo` upward through the sorted intervals and collects any gaps — spans that no
interval covers within the window.

Example: `Pressure` with `range: [0, 200]`, guards `pressure < 100` and `pressure >= 100`:

```
Intervals:  (-inf, 100)   [100, +inf)
Window:     [0, 201)
Sweep:      0 -> 100 covered by first interval
            100 -> 201 covered by second interval
Gaps:       none
```

**Without a declared `range`**:

The validator cannot determine whether the extreme ends (e.g., very large or very negative values)
are relevant. It only checks for gaps *between* defined intervals — spans between adjacent interval
upper and lower bounds that are not covered.

Example: guards `pressure < 5` and `pressure > 5` (no range):

```
Intervals (sorted): (-inf, 5)  (6, +inf)
Adjacent pair: hi=5, next_lo=6 -> gap [5, 6) exists
Issue: gap between 5 and 6
```

Gaps found with a declared range produce a `warning`. Gaps found between intervals without a
declared range also produce a `warning`. The `warning` severity (not `error`) reflects the fact
that numeric coverage analysis is an approximation — models with deliberate "ignore this value"
semantics are not prohibited.

### 3.3 Valid vs Invalid Example

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

Intervals: `(-inf, 100)` and `[100, +inf)` — the boundary `100` is covered by the second guard.
With `range: [0, 200]`, the window `[0, 201)` is fully spanned. No issues.

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

Intervals: `(-inf, 100)` and `[101, +inf)`. Point `100` (normalized interval `[100, 101)`) is
uncovered. With `range: [0, 200]`, the sweep finds gap `[100, 101)`.

Issue emitted (severity=`warning`):
```
Guard coverage gap on 'Idle' -> 'Pressure_changed':
variable 'pressure' has uncovered intervals: [100.0, 101.0)
```

---

## 4. Enum Completeness

When the discriminating variable's type resolves to an `EnumType` (from `types.yaml`), the
validator collects the right-hand-side names from all `variable == EnumValue` comparisons in the
group. The set of covered values is diffed against `EnumType.values`.

Any missing enum values produce an `error` (not a warning). The rationale: enum guards are
fully statically checkable — the domain of the variable is finite and known at model-read time.
A missing enum value is a definite modeling defect, not an approximation.

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

All three enum values covered. No issue.

**Invalid:**

Same as above but the `mode == Locked` transition is absent. Issue emitted (severity=`error`):
```
Enum guard on 'Idle' -> 'Mode_changed':
variable 'mode' (type 'ValveMode') is missing values: Locked
```

The check uses set difference, so multiple missing values are reported together in one issue.

---

## 5. Severity Levels

| Condition | Severity |
|-----------|----------|
| Multiple unguarded transitions on same `(from, event)` | `error` |
| Guard on a `String`-typed variable (primitive or scalar alias) | `error` |
| Enum guard with missing enum values | `error` |
| Guard parse failure | `warning` |
| Compound `AND`/`OR` guard — completeness cannot be determined | `warning` |
| Numeric interval gap (with or without declared range) | `warning` |

`error`-severity issues represent definitive model defects that will cause runtime non-determinism
or are semantically meaningless (String guards). `warning`-severity issues represent cases where
the validator cannot prove completeness — either because the guard structure is too complex to
analyze, or because numeric coverage is inherently approximate.

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

If the guard variable does not appear in the event's declared `params`, the type cannot be
determined and the group is skipped silently. This can happen when a guard references `self.attr`
(an instance attribute) rather than an event parameter. Instance-attribute guards are syntactically
valid but not analyzable by this validator.

### 6.5 `!=` Operator

Guards using `!=` cannot be mapped to a half-open interval (the complement of a single point is
two disjoint rays, not a contiguous interval). `_normalize_interval` returns `None` for `!=`,
which sets `analysis_failed = True` and causes the group to be skipped silently. Models using
`!=` guards are not flagged as errors — they are simply not coverage-checked.

### 6.6 Unknown Types and Struct Types

If `types.yaml` is absent, unreadable, or does not contain the type referenced in the guard, the
validator receives `type_def = None`. Bare `Integer` and `Real` primitives are still analyzed
(without a range). All other unknown types (e.g., struct types, `UniqueID`, `Boolean`,
`Timestamp`, `Duration`) result in silent skip.

### 6.7 `ScalarType` with String Base

A user-defined type with `base: String` is caught explicitly — the same `error` is raised as for
a bare `String` primitive. This prevents the "use a named type alias" workaround from bypassing
the String prohibition.

---

## 7. Decision Tree Logic (Multi-Guard Structure)

The current implementation does not build an explicit decision tree. Instead, it treats the guard
set as a flat collection of intervals or enum values and checks coverage as a whole. The implicit
assumption is that guards on the same `(from_state, event)` group are mutually exclusive — this
matches the xUML requirement that exactly one transition fires.

The `_unwrap_to_compare` function peels off single-child precedence wrappers (`or_expr`,
`and_expr`) produced by the grammar's precedence hierarchy. A guard like `x == 5` is grammatically
wrapped as `or_expr(and_expr(compare_expr(...)))` — these single-child wrappers are transparent.
Only when an `or_expr` or `and_expr` node genuinely has multiple child trees (i.e., contains a
logical operator) is the guard classified as compound and the group skipped with a `warning`.

This means:
- `x == 5` — analyzed as a simple comparison.
- `x > 5 and y > 0` — compound, group skipped with warning.
- `x > 5 or x < 0` — compound, group skipped with warning.

True decision-tree analysis (where a compound guard like `x > 5 and y > 0` is combined with
`x <= 5` to check overall coverage) is not implemented.

---

## 8. Limitations

1. **No overlap detection.** Two intervals `[0, 10)` and `[5, 15)` both cover `[5, 10)`. The gap
   check only confirms that the union spans the target range — it does not verify mutual
   exclusion. A model with overlapping guards will not be flagged; runtime behavior would be
   non-deterministic.

2. **No compound guard analysis.** Guards with `and`/`or` are skipped entirely. A set of guards
   like `x > 5 and y > 0`, `x <= 5 and y > 0`, `y <= 0` might together be exhaustive, but the
   validator cannot determine this and emits only a warning.

3. **Real-valued types use integer normalization.** The `+1` interval normalization is designed
   for integer domains. For `Real`-typed parameters, a gap between `x < 5.0` and `x > 5.0` is
   reported as `[5.0, 6.0)` rather than the single point `{5.0}`. The gap is correctly identified
   but the interval representation is misleading for continuous domains.

4. **Instance-attribute guards are not analyzed.** Only event parameters are looked up in the
   type map. Guards that compare `self.some_attr` are silently skipped.

5. **Multi-variable guards are not analyzed.** If a group has guards `x == 1` and `y == 2`
   (different variable names), the variable-name set has cardinality > 1 and the group is skipped.

6. **No cross-state-group completeness.** The check is per `(from_state, event)` pair. It does
   not consider whether a given `(from_state, event)` pair should even exist for all states that
   receive a given event.

7. **`!=` guards are silently skipped.** A guard of `x != 5` causes the entire group's interval
   analysis to be abandoned. No warning is issued for this case specifically.

8. **`types.yaml` is optional.** If absent, enum and String-alias checks cannot run. Bare
   `Integer`/`Real` guards are still analyzed for gaps, but without range bounds the analysis
   only catches gaps between explicitly stated intervals.
