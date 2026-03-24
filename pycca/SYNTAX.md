# Pycca Action Language — Syntax Reference

This document defines the syntax of the MDF action language used in
state entry actions, transition actions, method bodies, and bridge
operation bodies.

## Base Language

The base language is **C**. Standard C syntax applies within action
blocks — variable declarations, assignments, arithmetic, control flow,
function calls, etc. are all valid C.

Pycca adds a set of **keywords and macros** on top of C for
model-aware constructs:
- `self`, `rcvd_evt` — instance and event access
- `select`, `relate`, `unrelate` — relationship traversal and management
- `generate`, `cancel` — event propagation and cancellation
- `create`, `delete` — instance lifecycle
- `ClassName::` — class methods, class variables, bridge calls
- `now()` — built-in timestamp access

These compile down to runtime operations. See section 9 for the full
decomposition of each construct into runtime primitives.

**Action blocks are used in:**
- State entry actions
- Transition actions
- Method bodies (instance and class)
- Bridge operation implementations

**YAML scalar style:** Always use the literal block scalar (`|`) for
multi-line action bodies in YAML. Do **not** use the folded scalar (`>`),
which collapses newlines into spaces and destroys statement boundaries.
Single-line actions may use plain quoted strings.

```yaml
# Correct — preserves newlines between statements
entry_action: |
  self.direction = Stopped;
  Set<Request> reqs = select many from instances of Request
      where [] |r: Request| -> Boolean { return r.destination_floor > 0; };
  generate Request_assigned(target_floor: req.destination_floor) to self;

# Wrong — folds into one long line
entry_action: >
  self.direction = Stopped;
  ...
```

---

## 1. Types

### 1.1 Basic Types

The following scalar types are available:

| Type | Description |
|------|-------------|
| `Integer` | Signed integer |
| `Real` | Floating-point number |
| `Boolean` | `true` or `false` |
| `String` | Text string |
| `UniqueID` | Auto-generated unique identifier |
| `Timestamp` | Opaque absolute point in time (see section 7) |
| `Duration` | Opaque time interval (see section 7) |

Domain-defined types from `types.yaml` (e.g., `FloorNumber`, `Direction`)
are also valid wherever a type is expected.

### 1.2 Container Types

| Type | Description |
|------|-------------|
| `List<T>` | Ordered, allows duplicates, mutable in-place |
| `Set<T>` | Unordered, enforces uniqueness, mutable in-place |
| `Optional<T>` | Zero or one value |

Container types are first-class — they can be declared as local
variables and as class attributes. They are **not** allowed as event
parameters or method return types.

**Construction:**
```
List<FloorNumber> floors = List<FloorNumber>();
Set<DestFloorButton> buttons = Set<DestFloorButton>();
```

**Set uniqueness:** Determined by class identifier for instance types,
or bitwise equality for struct/value types.

**List-to-Set conversion:** Deduplicates using the same uniqueness rules.

**Set-to-List conversion:** Via `.sort(lambda)`, which produces an
ordered list.

### 1.3 Function Types

Lambda expressions can be stored in typed variables:

```
Fn(DestFloorButton, DestFloorButton) -> Boolean floor_asc =
    [] |a: DestFloorButton, b: DestFloorButton| -> Boolean {
        return a.r5_floor_num < b.r5_floor_num;
    };
```

See section 6 for full lambda syntax.

---

## 2. Pycca Statements

The following are the pycca-specific statements that extend C.
Standard C statements (assignments, if/else, loops, variable
declarations) are also valid within action blocks.

---

### 2.1 Select

Find one or many instances by relationship traversal or from the full
instance population.

**From all instances (no filter):**
```
Set<Class> <var> = select many from instances of <Class>;
Optional<Class> <var> = select any from instances of <Class>;
```

**From all instances (with where lambda):**
```
Set<Class> <var> = select many from instances of <Class>
    where <lambda>;
Optional<Class> <var> = select any from instances of <Class>
    where <lambda>;
```

The `where` clause takes a lambda that must return `Boolean`. The lambda
parameter type matches the class being selected:

```
FloorNumber target = 3;
Optional<Floor> f = select any from instances of Floor
    where [target] |f: Floor| -> Boolean { return f.floor_num == target; };
```

**By relationship traversal (from self):**
```
Set<Class> <var> = select many related by self->R<N>;
Optional<Class> <var> = select any related by self->R<N>;
```

**Chained traversal (multi-hop):**

Chains are allowed when every **intermediate** hop has multiplicity
`1` (direct traversal). The **final** hop determines whether `select`
is needed. If any intermediate hop is not `1`, the chain must stop
and the result must be handled before continuing.

```
// All hops are multiplicity 1 — pure direct traversal
Elevator elev = self->R8->R2->R1;

// Intermediate hops are multiplicity 1, final hop is 0..* — needs select many
Set<ShaftFloor> stops = select many related by self->R1->R2;

// R3 from Floor is 0..* — cannot chain further, must stop and handle
Optional<ShaftFloor> sf = select any related by floor->R3;
if (sf.has_value()) {
    ShaftFloor shaft_floor = sf.value();
    Elevator elev = shaft_floor->R2->R1;
}
```

**Traversal with where:**
```
Set<DestFloorButton> lit_btns = select many related by self->R4
    where [] |btn: DestFloorButton| -> Boolean { return btn.curr_state == Lit; };
```

**Return types — determined by relationship multiplicity:**

Traversals (`->R`) are only allowed on concrete instance variables
(`T`). They are **never** allowed on `Set<T>` or `Optional<T>`.

The traversal form depends on the target multiplicity:

| Target multiplicity | Syntax | Returns |
|---------------------|--------|---------|
| `1`                 | `var->R` (direct) | `T` |
| `0..1`              | `select any related by var->R` | `Optional<T>` |
| `0..*`              | `select any related by var->R` | `Optional<T>` |
| `0..*`              | `select many related by var->R` | `Set<T>` |
| `1..*`              | `select any related by var->R` | `T` |
| `1..*`              | `select many related by var->R` | `Set<T>` |
| `2`, `2..*`         | `select many related by var->R` | `Set<T>` |

- **Multiplicity `1`:** No `select` needed — the traversal resolves
  directly to a concrete instance. Use `var->R` as an expression.
- **`select any`** is not allowed for `2` or `2..*` (picking an
  arbitrary instance from a guaranteed collection is meaningless).
- **`select many`** is not allowed for `1` or `0..1` (at most one
  instance, use direct traversal or `select any`).
- The declared variable type must match the resolution type.

Examples:
```
// R1: Elevator 1---1 Shaft — multiplicity 1, direct traversal
Shaft shaft = self->R1;

// R5: DestFloorButton 1---1 Floor — multiplicity 1, direct
Floor floor = btn->R5;

// Chained direct traversal — all intermediate hops are multiplicity 1
Elevator elev = sf->R2->R1;

// R2: Shaft 1---0..* ShaftFloor — needs select
Set<ShaftFloor> stops = select many related by shaft->R2;

// R4: Elevator 1---2..* DestFloorButton — select any NOT allowed
Set<DestFloorButton> btns = select many related by self->R4;

// R3: Floor 1---0..* ShaftFloor — select any returns Optional
Optional<ShaftFloor> sf = select any related by floor->R3;
```

---

### 2.2 Generate

Send an event to a target instance or set of instances.

```
generate <EventName> to <target>;
generate <EventName>(<param>: <expr>, ...) to <target>;
```

**Delayed generate** — fire an event after a duration:
```
generate <EventName> to <target> delay <duration_expr>;
generate <EventName>(<param>: <expr>, ...) to <target> delay <duration_expr>;
```

At most one delayed event of a given type per (sender, receiver) pair
may be pending at any time. Posting a second cancels the first.

**Valid targets:**
| Target | Meaning |
|--------|---------|
| `self` | The current instance |
| `<var>` | An instance variable bound by a prior `select` |
| `<set_var>` | A `Set<T>` — broadcasts to all members |

**Invalid targets:**
| Target | Why |
|--------|-----|
| `ClassName` | A bare class name is not an instance. Use `select` first. |

Examples:
```
generate Open_door to self;
generate Floor_reached(floor_num: self.current_floor) to elev;
generate Floor_served(floor_num: my_floor) to buttons;
generate Door_close to self delay duration_s(5);
```

---

### 2.3 Cancel

Cancel a pending delayed event. Sender and target are always explicit:

```
cancel <EventName> from <sender> to <target>;
```

Examples:
```
cancel Door_close from self to self;
cancel Timer_expired from controller to door;
```

---

### 2.4 Create

Create a new instance of a class. Bind it to a variable for subsequent
`relate` and attribute assignment.

```
create <var> of <Class>;
create <var> of <Class>(<param>: <expr>, ...);
```

**Identifier handling:**
- `UniqueID` identifiers are auto-generated by the runtime — do not pass them.
- Non-`UniqueID` identifiers **must** be passed as parameters at creation.
- Identifier attributes are immutable after creation.

Examples:
```
create req of Request;                          // UniqueID identifier — auto-generated
req.destination_floor = fc.destination_floor;
relate req to self across R2;

create f of Floor(floor_num: 3);                // FloorNumber identifier — must be provided
create btn of FloorCallButton(direction: Up);   // non-UniqueID attrs can also be passed
```

---

### 2.5 Delete

Delete an instance. The instance must be identified by a variable
bound by a prior `select`.

```
delete <var>;
```

Examples:
```
Optional<Request> req = select any related by self->R2;
if (req.has_value()) {
    unrelate req.value() from self across R2;
    delete req.value();
}
```

---

### 2.6 Relate / Unrelate

Create or remove an association link between two instances.

```
relate <var1> to <var2> across R<N>;
unrelate <var1> from <var2> across R<N>;
```

> **Note:** M:M associations are modeled as two 1:M associations via a
> linking class (see schema/COMPILATION.md section 4.3). Each `relate`
> is a standard two-endpoint operation — no special syntax is needed.

Examples:
```
relate self to shaft across R11;
relate self to indicator across R10;    // Elevator to FloorIndicator
relate floor to indicator across R13;   // Floor to FloorIndicator
unrelate self from old_req across R2;
```

---

### 2.7 Bridge Call

Invoke an operation provided by another domain.

```
<Domain>::<Operation>(<arg>, ...);
<var> = <Domain>::<Operation>(<arg>, ...);
```

Examples:
```
Building::IsTopFloor(self.current_floor);
is_top = Building::IsTopFloor(self.current_floor);
```

---

### 2.8 Method Call

Invoke a class method or instance method.

**Class method** — operates on the class, no instance required:
```
<ClassName>::<method>(<arg>, ...);
<var> = <ClassName>::<method>(<arg>, ...);
```

**Instance method** — operates on a specific instance:
```
self.<method>(<arg>, ...);
<var>.<method>(<arg>, ...);
<var> = self.<method>(<arg>, ...);
<var> = <other_var>.<method>(<arg>, ...);
```

Examples:
```
// Class method — no instance
Integer count = Elevator::GetIdleCount();
Dispatcher::ResetQueue();

// Instance method — on self
self.UpdateDisplay();
Integer next = self.PeekNextFloor();

// Instance method — on another instance
Optional<Door> door = select any related by self->R1;
door.value().ForceOpen();
```

Method bodies follow the same pycca syntax as entry actions and
transition actions. They can be defined inline in `class-diagram.yaml`
or in a separate `class-methods.yaml` file.

---

### 2.9 Control Flow

Standard C control flow is used for conditionals:

```c
if (req.has_value()) {
    generate Request_assigned to self;
} else {
    generate Elevator_available to dispatcher;
}
```

C `while`, `switch`, etc. are all valid within action blocks.

**For-each loop** — iterate over `List<T>` or `Set<T>`:

```
for (DestFloorButton btn : my_list) {
    // btn is scoped to the loop body only
}
```

The loop variable type must match the container's element type.

---

## 3. Container Methods

### 3.1 List\<T\> Methods

**Access:**
| Method | Returns | Description |
|--------|---------|-------------|
| `get(index: Integer)` | `Optional<T>` | Element at position |
| `peek_front()` | `Optional<T>` | First element without removing |
| `peek_back()` | `Optional<T>` | Last element without removing |

**Search:**
| Method | Returns | Description |
|--------|---------|-------------|
| `find(lambda)` | `Optional<T>` | First element matching predicate |
| `contains(element: T)` | `Boolean` | Membership test |

**Transform:**
| Method | Returns | Description |
|--------|---------|-------------|
| `filter(lambda)` | `List<T>` | New list of matching elements |
| `sort(lambda)` | *(in-place)* | Reorder list; lambda is comparator |
| `map(lambda)` | `List<U>` | Transform elements, return new list |

**Mutate:**
| Method | Returns | Description |
|--------|---------|-------------|
| `push_front(element: T)` | — | Add to front |
| `push_back(element: T)` | — | Add to back |
| `pop_front()` | `Optional<T>` | Remove and return first |
| `pop_back()` | `Optional<T>` | Remove and return last |
| `remove(index: Integer)` | — | Remove element at index |
| `insert(index: Integer, element: T)` | — | Insert at position |

**Common:**
| Method | Returns | Description |
|--------|---------|-------------|
| `size()` | `Integer` | Element count |
| `is_empty()` | `Boolean` | True if size is 0 |

### 3.2 Set\<T\> Methods

**Search:**
| Method | Returns | Description |
|--------|---------|-------------|
| `find(lambda)` | `Optional<T>` | First element matching predicate |
| `contains(element: T)` | `Boolean` | Membership test |

**Transform:**
| Method | Returns | Description |
|--------|---------|-------------|
| `filter(lambda)` | `Set<T>` | New set of matching elements |
| `sort(lambda)` | `List<T>` | Sorted set produces an ordered list |
| `map(lambda)` | `List<U>` | Transform elements, return new list |

**Mutate:**
| Method | Returns | Description |
|--------|---------|-------------|
| `add(element: T)` | — | Add element (no-op if duplicate) |
| `remove(element: T)` | — | Remove element |

**Set Operations:**
| Method | Returns | Description |
|--------|---------|-------------|
| `union(other: Set<T>)` | `Set<T>` | All elements from both sets |
| `intersection(other: Set<T>)` | `Set<T>` | Elements in both sets |
| `difference(other: Set<T>)` | `Set<T>` | Elements in this but not other |

**Common:**
| Method | Returns | Description |
|--------|---------|-------------|
| `size()` | `Integer` | Element count |
| `is_empty()` | `Boolean` | True if size is 0 |

### 3.3 Optional\<T\> Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `has_value()` | `Boolean` | True if a value is present |
| `value()` | `T` | The contained value (runtime error if empty) |

---

## 4. Name Resolution

Names in pycca are resolved by prefix. Bare names are only valid
when they refer to something defined in the current scope.

| Form | Resolves to | Defined by |
|------|-------------|------------|
| `self.<name>` | Instance attribute on the current object | `class-diagram.yaml` |
| `rcvd_evt.<name>` | Parameter from the received event | event `params` in state-diagram YAML |
| `arg.<name>` | Method argument | method `params` in class-diagram YAML |
| `<var>.<name>` | Attribute on another instance | `select` or `create` binds `<var>` |
| `<var>.<method>()` | Container or instance method call | type of `<var>` |
| `<var>` | Local variable (instance ref or C-typed) | `select`, `create`, bridge return, or C declaration |
| `Up`, `Down`, etc. | Enum value | `types.yaml` |
| `0`, `42`, `"hello"` | Literal | language built-in |
| `empty` | Null/missing instance (deprecated — use `Optional<T>`) | language built-in |
| `now()` | Current timestamp | language built-in |

**Scope rules:**
- `self` is always in scope within instance method bodies, entry
  actions, and transition actions
- `rcvd_evt` is in scope in guard expressions, transition actions,
  and entry actions of the target state
- `arg` is in scope within method bodies only
- `now()` is always in scope — returns `Timestamp`
- A bare name **must** have been declared earlier in the same action
  block via `select`, `create`, bridge return assignment, or C-type
  variable declaration. The compiler scans the action block top-down;
  if the bare name has no prior binding, it is a compile error — no
  fallback to attributes, event params, or class names
- Enum values are the one exception: if a bare name matches a value
  in `types.yaml` and is not shadowed by a local binding, it resolves
  to that enum constant
- Resolution order: local variable → enum value → compile error
- For-each loop variables are scoped to the loop body only

---

## 5. Expressions

Expressions appear in guards, if conditions, lambda bodies, and
on the right-hand side of assignments.

| Form | Example |
|------|---------|
| Literal integer | `0`, `42` |
| Literal string | `"hello"` |
| Enum value | `Up`, `Down`, `Stopped`, `True`, `False` |
| Attribute read (self) | `self.current_floor` |
| Attribute read (var) | `req.destination_floor` |
| Event parameter | `rcvd_evt.floor_num`, `rcvd_evt.target_floor` |
| Comparison | `a == b`, `a != b`, `a > b`, `a < b`, `a >= b`, `a <= b` |
| Logical | `a and b`, `a or b` |
| Arithmetic | `a + b`, `a - b`, `a * b` |
| Method call | `my_list.size()`, `btn.has_value()` |
| Built-in call | `now()`, `duration_s(5)`, `in_ms(d)` |

---

## 6. Lambda Expressions

Lambdas are first-class values with explicit typing, capture lists,
and braced bodies.

### 6.1 Syntax

```
[<captures>] |<param>: <Type>, ...| -> <ReturnType> {
    <statements>;
    return <expr>;
}
```

### 6.2 Rules

- **Capture list always present** — empty `[]` when nothing is captured
- **`self` cannot be captured** — capture specific values instead
- **Parameters always typed** — `|param: Type|`
- **Return type always explicit** — `-> ReturnType`
- **Body always in braces with semicolons** — no shorthand form
- **Captures are by-value** — copies at time of lambda creation

### 6.3 Variable Assignment

The left-hand side must declare the full `Fn` type:

```
Fn(DestFloorButton, DestFloorButton) -> Boolean floor_asc =
    [] |a: DestFloorButton, b: DestFloorButton| -> Boolean {
        return a.r5_floor_num < b.r5_floor_num;
    };
```

### 6.4 Inline Usage

Lambdas can be passed directly to container methods and `where` clauses:

```
// Filter
Set<DestFloorButton> lit = all_btns.filter(
    [] |btn: DestFloorButton| -> Boolean { return btn.curr_state == Lit; }
);

// Sort
List<DestFloorButton> sorted = lit.sort(
    [] |a: DestFloorButton, b: DestFloorButton| -> Boolean {
        return a.r5_floor_num < b.r5_floor_num;
    }
);

// Map
List<FloorNumber> floors = sorted.map(
    [] |btn: DestFloorButton| -> FloorNumber { return btn.r5_floor_num; }
);

// Where clause on select
Set<DestFloorButton> candidates = select many from instances of DestFloorButton
    where [my_id] |btn: DestFloorButton| -> Boolean {
        return btn.r4_elevator_id == my_id;
    };
```

### 6.5 Multi-line Lambdas

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

## 7. Time Primitives

### 7.1 Timestamp

Opaque type representing an absolute point in time. Internal
representation is implementation-defined.

**Built-in access:**
```
Timestamp t = now();
```

`now()` is a language built-in — always available without a bridge call.

No direct construction from integers: `Timestamp t = 42;` is a
compile error.

### 7.2 Duration

Opaque type representing a time interval.

**Constructors:**
```
Duration d = duration_s(5);     // 5 seconds
Duration d = duration_ms(500);  // 500 milliseconds
```

**Getters:**
```
Integer s = in_s(d);    // extract as seconds
Integer ms = in_ms(d);  // extract as milliseconds
```

No direct construction from integers: `Duration d = 100;` is a
compile error.

### 7.3 Arithmetic

| Expression | Result |
|------------|--------|
| `Timestamp - Timestamp` | `Duration` |
| `Timestamp + Duration` | `Timestamp` |
| `Timestamp - Duration` | `Timestamp` |
| `Duration + Duration` | `Duration` |
| `Duration - Duration` | `Duration` |
| `Duration * Integer` | `Duration` |

### 7.4 Comparison

Both `Timestamp` and `Duration` support: `==`, `!=`, `<`, `>`, `<=`, `>=`

### 7.5 Delayed Generate

```
generate Door_close to self delay duration_s(5);
generate Open_reminder(floor: self.current_floor) to door delay duration_ms(500);
```

At most one delayed event of a given type per (sender, receiver) pair
may be pending at any time. Posting a second cancels the first.

### 7.6 Cancel

```
cancel Door_close from self to self;
cancel Timer_expired from controller to door;
```

Sender and target are always explicit.

---

## 8. Guard Expressions

Guards appear on transitions and are pure boolean expressions
(no side effects). They use the same expression syntax from section 5.

```yaml
guard: "rcvd_evt.target_floor > self.current_floor"
guard: "rcvd_evt.current_floor == self.next_stop_floor"
guard: "rcvd_evt.has_idle_elevator == true"
```

Event parameters use the `rcvd_evt.` prefix. Instance attributes
use the `self.` prefix. No bare names for either.

---

## 9. Runtime Decomposition

Every pycca-specific construct compiles down to runtime operations.
The runtime interface is the responsibility of the execution engine.
These decompositions serve as **requirements** for that engine.

### 9.1 select many from instances of Class where lambda

**Sugar:**
```
Set<DestFloorButton> lit_btns = select many from instances of DestFloorButton
    where [my_id] |btn: DestFloorButton| -> Boolean { return btn.r4_elevator_id == my_id; };
```

**Decomposes to:**
```
Set<DestFloorButton> __all = runtime.get_all_instances(DestFloorButton);
Set<DestFloorButton> lit_btns = __all.filter(
    [my_id] |btn: DestFloorButton| -> Boolean { return btn.r4_elevator_id == my_id; }
);
```

### 9.2 select many from instances of Class (no where)

**Sugar:**
```
Set<DestFloorButton> all_btns = select many from instances of DestFloorButton;
```

**Decomposes to:**
```
Set<DestFloorButton> all_btns = runtime.get_all_instances(DestFloorButton);
```

### 9.3 select any from instances of Class where lambda

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

### 9.4 select any from instances of Class (no where)

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

### 9.5 select many related by self->R

**Sugar:**
```
Set<DestFloorButton> buttons = select many related by self->R4;
```

**Decomposes to:**
```
Set<DestFloorButton> buttons = runtime.traverse(self, R4);
```

### 9.6 select any related by self->R

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

### 9.7 select with traversal + where

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

### 9.8 Chained traversal

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

### 9.9 generate Event to target

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

### 9.10 generate Event to target delay duration

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

### 9.11 cancel Event from sender to target

**Sugar:**
```
cancel Door_close from self to door;
```

**Decomposes to:**
```
runtime.cancel_delayed_event(Door_close, self, door);
```

### 9.12 create var of Class(params)

**Sugar:**
```
create f of Floor(floor_num: 3);
```

**Decomposes to:**
```
Floor f = runtime.create_instance(Floor, {floor_num: 3});
```

### 9.13 delete var

**Sugar:**
```
delete req;
```

**Decomposes to:**
```
runtime.delete_instance(req);
```

### 9.14 relate var1 to var2 across R

**Sugar:**
```
relate req to self across R2;
```

**Decomposes to:**
```
runtime.link(req, self, R2);
```

### 9.15 unrelate var1 from var2 across R

**Sugar:**
```
unrelate req from self across R2;
```

**Decomposes to:**
```
runtime.unlink(req, self, R2);
```

### 9.16 bridge call

**Sugar:**
```
Boolean is_top = Building::IsTopFloor(self.current_floor);
```

**Decomposes to:**
```
Boolean is_top = runtime.bridge_call(Building, IsTopFloor, {self.current_floor});
```

### 9.17 now() built-in

**Decomposes to:**
```
Timestamp t = runtime.get_current_time();
```

---

## 10. Runtime Interface Summary

The decompositions above require the following runtime interface.
This is the responsibility of the execution engine, not the parser.

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

---

## 11. Reserved Words

```
self, rcvd_evt, arg, select, any, many, from, instances, of, where,
related, by, generate, to, create, delete, relate, unrelate, across,
bridge, if, else, for, return, cancel, delay, now, empty,
and, or, true, false,
duration_s, duration_ms, in_s, in_ms
```

---

## 12. Differences from Standard OAL

| OAL (BridgePoint) | MDF Pycca | Notes |
|--------------------|-----------|-------|
| `select one var related by self->Class[R1]` | `Optional<Class> var = select any related by self->R1;` | MDF uses `Optional<T>` return; target class inferred |
| `select many ... where <expr>` | `select many ... where <lambda>` | MDF uses lambdas for filtering |
| `send Event(param) to var` | `generate Event(param: val) to var;` | MDF uses `generate`, named params |
| `create object instance var of Class` | `create var of Class;` | Shorter form |
| `delete object instance var` | `delete var;` | Shorter form |
| `LOG::LogString(...)` | `Domain::Operation(...)` | Same pattern |
| `cardinality var` | `var.size()` | Method call on container |
| `transform` | *(not supported)* | No inline transforms |

---

## 13. Grammar Status

The current `pycca/grammar.py` parser supports a **subset** of this syntax.

**Implemented:**
- Assignments (`self.attr = expr;`)
- Select from instances with bare boolean `where` (legacy, to be migrated)
- Select related by (`self->R<N>`)
- Generate with variable targets and param lists
- Create with and without params
- Delete (variable and object forms)
- Relate / Unrelate
- If/else with brace syntax
- Bridge calls
- Dotted name expressions (`var.attr`, `self.attr`, `rcvd_evt.param`)

**Not yet implemented:**
- Container types (`List<T>`, `Set<T>`, `Optional<T>`)
- Lambda expressions (`[captures] |params| -> ReturnType { body }`)
- Container method calls (`.filter()`, `.sort()`, `.map()`, etc.)
- For-each loops (`for (Type var : collection) { ... }`)
- `Fn` type declarations
- `where` clause with lambda (currently uses bare boolean)
- Time primitives (`Timestamp`, `Duration`, `now()`, `duration_s()`, etc.)
- Delayed generate (`generate ... delay ...`)
- Cancel statement (`cancel ... from ... to ...`)
- Arithmetic expressions (`a + b`, `a * b`)
- `else if` chains
