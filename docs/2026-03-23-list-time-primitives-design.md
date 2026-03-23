# List and Time Primitives — Design Spec

**Date:** 2026-03-23
**Status:** Approved

## Motivation

The MDF action language (pycca) currently has `select many` returning untyped
instance sets with no way to access individual elements, sort, filter, or
iterate. Time is represented as a raw integer alias with no delayed event
syntax. Both lists and time are standard necessities for executable models.

This design introduces first-class container types (`List<T>`, `Set<T>`,
`Optional<T>`), lambda expressions, opaque time types (`Timestamp`,
`Duration`), and delayed event syntax.

---

## 1. Container Types

### 1.1 List\<T\>

Ordered, allows duplicates, mutable in-place. Typed — the compiler knows
the element type and validates attribute access, method calls, etc.

**Access:**
- `get(index: Integer)` -> `Optional<T>`
- `peek_front()` -> `Optional<T>`
- `peek_back()` -> `Optional<T>`

**Search:**
- `find(lambda)` -> `Optional<T>` — first element matching predicate
- `contains(element: T)` -> `Boolean`

**Transform:**
- `filter(lambda)` -> `List<T>` — new list of matching elements
- `sort(lambda)` -> in-place reorder
- `map(lambda)` -> `List<U>` — transform elements, return new list

**Mutate:**
- `push_front(element: T)`
- `push_back(element: T)`
- `pop_front()` -> `Optional<T>` — remove and return first
- `pop_back()` -> `Optional<T>` — remove and return last
- `remove(index: Integer)`
- `insert(index: Integer, element: T)`

**Common:**
- `size()` -> `Integer`
- `is_empty()` -> `Boolean`

**Construction:**
```
List<FloorNumber> floors = List<FloorNumber>();
```

### 1.2 Set\<T\>

Unordered, enforces uniqueness, mutable in-place. Uniqueness is determined
by class identifier for instance types, or bitwise equality for struct/value
types.

**Search:**
- `find(lambda)` -> `Optional<T>` — first element matching predicate
- `contains(element: T)` -> `Boolean`

**Transform:**
- `filter(lambda)` -> `Set<T>` — new set of matching elements
- `sort(lambda)` -> `List<T>` — sorted set produces an ordered list
- `map(lambda)` -> `List<U>` — transform elements, return new list

**Mutate:**
- `add(element: T)`
- `remove(element: T)`

**Set Operations:**
- `union(other: Set<T>)` -> `Set<T>`
- `intersection(other: Set<T>)` -> `Set<T>`
- `difference(other: Set<T>)` -> `Set<T>`

**Common:**
- `size()` -> `Integer`
- `is_empty()` -> `Boolean`

**Construction:**
```
Set<DestFloorButton> buttons = Set<DestFloorButton>();
```

**Conversion:**
- `Set<T>` -> `List<T>` via `.sort(lambda)`
- `List<T>` -> `Set<T>` — dedup using class identifier or bitwise equality

### 1.3 Optional\<T\>

Zero or one value. Returned by `select any`, `find`, `get`, `pop_front`,
`pop_back`, `peek_front`, `peek_back`.

**Methods:**
- `has_value()` -> `Boolean`
- `value()` -> `T` (runtime error if empty)

### 1.4 Attribute and Parameter Rules

- `List<T>` and `Set<T>` **allowed** as class attributes
- `List<T>` and `Set<T>` **not allowed** as event parameters
- `List<T>` and `Set<T>` **not allowed** as method return types (for now)

---

## 2. Lambda Expressions

First-class values with explicit typing and capture lists.

### 2.1 Syntax

```
// Full form
[capture_a, capture_b] |param: Type, param2: Type| -> ReturnType {
    statements;
    return expr;
}

// No captures
[] |a: Type, b: Type| -> Boolean { return a.x < b.x; }
```

### 2.2 Rules

- **Capture list always present** — empty `[]` when nothing is captured
- **`self` cannot be captured** — capture specific values instead
- **Parameters always typed** — `|param: Type|`
- **Return type always explicit** — `-> ReturnType`
- **Body always in braces with semicolons** — no shorthand form
- **Captures are by-value** — copies at time of lambda creation

### 2.3 Variable Assignment

Lambdas can be assigned to variables. The left-hand side must declare
the full `Fn` type:

```
Fn(DestFloorButton, DestFloorButton) -> Boolean floor_asc =
    [] |a: DestFloorButton, b: DestFloorButton| -> Boolean {
        return a.r5_floor_num < b.r5_floor_num;
    };
```

### 2.4 Multi-line Lambdas

```
Fn(DestFloorButton) -> Boolean is_lit_above =
    [my_floor, my_id] |btn: DestFloorButton| -> Boolean {
        if (btn.r4_elevator_id != my_id) {
            return false;
        }
        if (btn.curr_state != Lit) {
            return false;
        }
        return btn.r5_floor_num > my_floor;
    };
```

---

## 3. Time Primitives

### 3.1 Timestamp

Opaque type representing an absolute point in time. Internal
representation is implementation-defined (tick count, monotonic clock,
etc.).

**Built-in:**
- `now()` -> `Timestamp` — language built-in, always available

**No direct construction from integers.** `Timestamp t = 42;` is a
compile error.

### 3.2 Duration

Opaque type representing a time interval.

**Constructors:**
- `duration_s(Integer)` -> `Duration` — from seconds
- `duration_ms(Integer)` -> `Duration` — from milliseconds

**Getters:**
- `in_s(Duration)` -> `Integer` — extract as seconds
- `in_ms(Duration)` -> `Integer` — extract as milliseconds

### 3.3 Arithmetic

| Expression | Result |
|------------|--------|
| `Timestamp - Timestamp` | `Duration` |
| `Timestamp + Duration` | `Timestamp` |
| `Timestamp - Duration` | `Timestamp` |
| `Duration + Duration` | `Duration` |
| `Duration - Duration` | `Duration` |
| `Duration * Integer` | `Duration` |

### 3.4 Comparison

Both `Timestamp` and `Duration` support: `==`, `!=`, `<`, `>`, `<=`, `>=`

### 3.5 Delayed Generate

```
generate Door_close to self delay duration_s(5);
```

At most one delayed event of a given type per (sender, receiver) pair
may be pending at any time. Posting a second cancels the first.

### 3.6 Cancel

Cancels a pending delayed event. Sender and target are always explicit:

```
cancel Door_close from self to door;
```

---

## 4. Select Statement Changes

### 4.1 Return Types

- `select many` returns `Set<T>`
- `select any` returns `Optional<T>`

### 4.2 Where Clause

The `where` clause takes a lambda (must return `Boolean`):

```
select many lit_btns from instances of DestFloorButton
    where [my_id] |btn: DestFloorButton| -> Boolean {
        return btn.r4_elevator_id == my_id;
    };

Optional<DestFloorButton> btn = select any from instances of DestFloorButton
    where [target] |btn: DestFloorButton| -> Boolean {
        return btn.r5_floor_num == target;
    };
```

### 4.3 Relationship Traversal

Unchanged syntax, updated return types:

```
Set<DestFloorButton> buttons = select many related by self->R4;
Optional<Door> door = select any related by self->R1;
```

Traversal + where:
```
Set<DestFloorButton> lit_btns = select many related by self->R4
    where [] |btn: DestFloorButton| -> Boolean { return btn.curr_state == Lit; };
```

---

## 5. For-Each Loop

```
for (DestFloorButton btn : my_list) {
    // btn scoped to loop body only
}
```

Works on both `List<T>` and `Set<T>`.

---

## 6. Deprecated Constructs

| Old | Replacement |
|-----|-------------|
| `cardinality <set_var>` | `<set_var>.size()` |
| `where <bare_expr>` on select | `where <lambda>` |
| `empty` check on select any | `Optional<T>.has_value()` |

---

## 7. Runtime Decomposition

Every pycca-specific construct decomposes into primitive operations on
the runtime. The runtime class is the responsibility of the execution
engine (Phase 5). These decompositions serve as **requirements** for
the engine.

### 7.1 select many from instances of Class where lambda

**Sugar:**
```
select many lit_btns from instances of DestFloorButton
    where [my_id] |btn: DestFloorButton| -> Boolean { return btn.r4_elevator_id == my_id; };
```

**Decomposes to:**
```
Set<DestFloorButton> __all = runtime.get_all_instances(DestFloorButton);
Set<DestFloorButton> lit_btns = __all.filter(
    [my_id] |btn: DestFloorButton| -> Boolean { return btn.r4_elevator_id == my_id; }
);
```

### 7.2 select many from instances of Class (no where)

**Sugar:**
```
select many all_btns from instances of DestFloorButton;
```

**Decomposes to:**
```
Set<DestFloorButton> all_btns = runtime.get_all_instances(DestFloorButton);
```

### 7.3 select any from instances of Class where lambda

**Sugar:**
```
Optional<DestFloorButton> btn = select any from instances of DestFloorButton
    where [target] |btn: DestFloorButton| -> Boolean { return btn.r5_floor_num == target; };
```

**Decomposes to:**
```
Set<DestFloorButton> __all = runtime.get_all_instances(DestFloorButton);
Optional<DestFloorButton> btn = __all.find(
    [target] |btn: DestFloorButton| -> Boolean { return btn.r5_floor_num == target; }
);
```

### 7.4 select any from instances of Class (no where)

**Sugar:**
```
Optional<DestFloorButton> btn = select any from instances of DestFloorButton;
```

**Decomposes to:**
```
Set<DestFloorButton> __all = runtime.get_all_instances(DestFloorButton);
Optional<DestFloorButton> btn = __all.find(
    [] |btn: DestFloorButton| -> Boolean { return true; }
);
```

### 7.5 select many related by self->R

**Sugar:**
```
Set<DestFloorButton> buttons = select many related by self->R4;
```

**Decomposes to:**
```
Set<DestFloorButton> buttons = runtime.traverse(self, R4);
```

### 7.6 select any related by self->R

**Sugar:**
```
Optional<Door> door = select any related by self->R1;
```

**Decomposes to:**
```
Set<Door> __related = runtime.traverse(self, R1);
Optional<Door> door = __related.find(
    [] |d: Door| -> Boolean { return true; }
);
```

### 7.7 select with traversal + where

**Sugar:**
```
Set<DestFloorButton> lit_btns = select many related by self->R4
    where [] |btn: DestFloorButton| -> Boolean { return btn.curr_state == Lit; };
```

**Decomposes to:**
```
Set<DestFloorButton> __related = runtime.traverse(self, R4);
Set<DestFloorButton> lit_btns = __related.filter(
    [] |btn: DestFloorButton| -> Boolean { return btn.curr_state == Lit; }
);
```

### 7.8 Chained traversal

**Sugar:**
```
Optional<Floor> floor = select any related by self->R2->R3;
```

**Decomposes to:**
```
Set<Shaft> __hop1 = runtime.traverse(self, R2);
Set<Floor> __hop2 = Set<Floor>();
for (Shaft s : __hop1) {
    Set<Floor> __partial = runtime.traverse(s, R3);
    __hop2 = __hop2.union(__partial);
}
Optional<Floor> floor = __hop2.find(
    [] |f: Floor| -> Boolean { return true; }
);
```

### 7.9 generate Event to target

**Sugar:**
```
generate Floor_served(floor_num: my_floor) to buttons;
```

**Decomposes to (single target):**
```
runtime.enqueue_event(Event(Floor_served, {floor_num: my_floor}), target);
```

**Decomposes to (set target — broadcast):**
```
for (DestFloorButton btn : buttons) {
    runtime.enqueue_event(Event(Floor_served, {floor_num: my_floor}), btn);
}
```

### 7.10 generate Event to target delay duration

**Sugar:**
```
generate Door_close to self delay duration_s(5);
```

**Decomposes to:**
```
runtime.enqueue_delayed_event(
    Event(Door_close, {}),
    self,   // sender
    self,   // target
    duration_s(5)
);
```

### 7.11 cancel Event from sender to target

**Sugar:**
```
cancel Door_close from self to door;
```

**Decomposes to:**
```
runtime.cancel_delayed_event(Door_close, self, door);
```

### 7.12 create var of Class(params)

**Sugar:**
```
create f of Floor(floor_num: 3);
```

**Decomposes to:**
```
Floor f = runtime.create_instance(Floor, {floor_num: 3});
```

### 7.13 delete var

**Sugar:**
```
delete req;
```

**Decomposes to:**
```
runtime.delete_instance(req);
```

### 7.14 relate var1 to var2 across R

**Sugar:**
```
relate req to self across R2;
```

**Decomposes to:**
```
runtime.link(req, self, R2);
```

### 7.15 unrelate var1 from var2 across R

**Sugar:**
```
unrelate req from self across R2;
```

**Decomposes to:**
```
runtime.unlink(req, self, R2);
```

### 7.16 cardinality (deprecated)

**Sugar:**
```
if (cardinality lit_btns == 0) { ... }
```

**Decomposes to:**
```
if (lit_btns.size() == 0) { ... }
// or
if (lit_btns.is_empty()) { ... }
```

### 7.17 bridge call

**Sugar:**
```
Boolean is_top = Building::IsTopFloor(self.current_floor);
```

**Decomposes to:**
```
Boolean is_top = runtime.bridge_call(Building, IsTopFloor, {self.current_floor});
```

### 7.18 now() built-in

**Decomposes to:**
```
Timestamp t = runtime.get_current_time();
```

---

## 8. Runtime Interface Requirements

The decompositions above imply the following runtime interface. This is
the responsibility of the execution engine (Phase 5), not the parser.

```
runtime.get_all_instances(Class) -> Set<T>
runtime.traverse(instance, relationship) -> Set<T>
runtime.enqueue_event(event, target)
runtime.enqueue_delayed_event(event, sender, target, duration)
runtime.cancel_delayed_event(event_type, sender, target)
runtime.create_instance(Class, params) -> T
runtime.delete_instance(instance)
runtime.link(instance_a, instance_b, relationship)
runtime.unlink(instance_a, instance_b, relationship)
runtime.bridge_call(domain, operation, args) -> value
runtime.get_current_time() -> Timestamp
```
