# Schema Compilation Reference

This document defines how schema elements (YAML model definitions) compile
into names, scopes, and constructs that pycca action code can reference.

The compiler uses these rules to resolve identifiers in entry actions,
transition actions, and guard expressions.

---

## 1. Attribute Access

Every attribute declared in `class-diagram.yaml` is accessible on the
owning instance via `self.<attribute_name>`. Access from other instances
is controlled by visibility and mutability.

### 1.1 Visibility

| Visibility | `self.<attr>` | `var.<attr>` (other class) | subtype access |
|------------|---------------|---------------------------|----------------|
| `public` | read/write | read/write | read/write |
| `private` | read/write | compile error | read/write |

Default visibility is **`public`**.

Private attributes are accessible from within the owning class and
from any subtype that inherits them. External classes cannot access
private attributes.

### 1.2 Mutability

All attributes are mutable except:
- **Identifiers** (`identifier: 1` or any set) — constant after creation.
  Set once at creation time and never reassigned.
- **`curr_state`** — read-only in pycca code. Only changes through
  event propagation (see section 3).

Everything else can be read and written at any time (subject to
visibility).

**Schema example:**
```yaml
classes:
  - name: Elevator
    attributes:
      - name: current_floor
        type: FloorNumber
        visibility: public
      - name: direction
        type: Direction
        visibility: public
      - name: next_stop_floor
        type: FloorNumber
```

### 1.3 Access in Pycca

**Self access (always allowed):**
```
self.current_floor = 3;
self.direction = Up;
```

**Cross-instance access (requires public visibility):**
```
Optional<Request> req = select any related by self->R2;
req.value().destination_floor             // OK if destination_floor is public
req.value().destination_floor = 5;        // OK if public
```

**Compile errors:**
```
req.value().some_private_attr             // ERROR — private attribute
req.value().some_private_attr = 5;        // ERROR — private attribute
self.elevator_id = 42;                    // ERROR — identifier is constant
self.curr_state = Idle;                   // ERROR — curr_state is read-only
```

### 1.4 Container Attributes

Classes may declare attributes with container types:

```yaml
classes:
  - name: Dispatcher
    attributes:
      - name: pending_floors
        type: List<FloorNumber>
      - name: active_elevators
        type: Set<Elevator>
```

Container attributes follow the same visibility rules as scalar
attributes. They are **not** allowed as event parameters or method
return types.

---

## 2. Identifier Attributes

Identifier attributes mark the unique key(s) for an instance. The
`identifier` field accepts an integer or list of integers indicating
which identifier set(s) the attribute belongs to. Every non-subtype
class **must** have at least one attribute in identifier set 1.

**Accepted forms (all equivalent for a single I1 attribute):**
```yaml
identifier: 1          # bare int — coerced to [1]
identifier: true       # backward compat — coerced to [1]
identifier: [1]        # explicit list
```

**Omitted or false means "not an identifier":**
```yaml
identifier: false      # coerced to None
# or simply omit the field
```

### 2.1 Identifier Sets

Each positive integer represents a distinct identifier set. Identifier
set 1 (`I1`) is the **primary** identifier — it is mandatory on every
non-subtype class.

**Single identifier (most common):**
```yaml
- name: elevator_id
  type: UniqueID
  identifier: 1
```

**Compound identifier** — multiple attributes sharing the same set number
form a composite key:
```yaml
- name: floor_num
  type: FloorNumber
  identifier: 1
- name: direction
  type: CallDirection
  identifier: 1
```

**Multiple identifier sets** — an attribute can participate in more than
one set:
```yaml
- name: floor_num
  type: FloorNumber
  identifier: [1, 2]    # participates in I1 and I2
```

### 2.2 UniqueID Identifiers

When the identifier type is `UniqueID`, the runtime auto-generates the
value at creation. No explicit assignment is needed in pycca.

**Schema:**
```yaml
- name: elevator_id
  type: UniqueID
  identifier: 1
```

**Pycca:**
```
create elev of Elevator;
// elev.elevator_id is auto-assigned by runtime — do not set manually
```

### 2.3 Non-UniqueID Identifiers

When the identifier type is anything other than `UniqueID`, the value
**must** be provided as a parameter during creation. The runtime cannot
generate a meaningful value for domain-specific types.

**Schema:**
```yaml
- name: Floor
  attributes:
    - name: floor_num
      type: FloorNumber
      identifier: 1
```

**Pycca:**
```
create f of Floor(floor_num: 3);
```

### 2.4 Identifiers Are Constants

Identifier attributes are **constants after creation**. They are set
exactly once — either auto-generated (UniqueID) or provided as a
creation parameter — and are immutable for the lifetime of the instance.

Any assignment to an identifier after creation is a compile error:
```
self.elevator_id = 42;    // COMPILE ERROR — identifier is constant
self.floor_num = 5;       // COMPILE ERROR — identifier is constant
```

Identifiers can be **read** freely:
```c
if (self.floor_num == rcvd_evt.target_floor) {   // OK — read access
    ...
}
```

The compiler validates:
- Every non-subtype class has at least one attribute in identifier set 1
- All non-UniqueID identifier attributes have values provided in the
  `create` parameter list
- UniqueID identifiers are **not** provided (auto-generated)
- Identifier attributes are never the target of an assignment after creation

### 2.5 Identifiers and Set Uniqueness

When instances are stored in a `Set<T>`, uniqueness is determined by the
class's identifier attributes. Two instances are considered equal if all
their identifier attributes match. For value types (scalars, structs),
bitwise equality is used.

---

## 3. Current State

Every active class instance has a compiler-generated macro for
reading its current state machine state.

```c
self.curr_state
```

`curr_state` is a **macro** that expands to a getter call at compile
time. It is not a stored attribute — the state machine runtime tracks
the current state internally.

**Properties:**
- Public — readable by any class
- Read-only — cannot be assigned in pycca code. Any assignment
  (`self.curr_state = ...;`) is a compile error. Only event
  propagation (transitions) can change the state.
- Set to `initial_state` at instance creation time.
- The value is one of the state names declared in the class's
  state-diagram YAML.

**Pycca (read access):**
```c
if (self.curr_state == Idle) {
    // elevator is idle
}
```

**Pycca (reading another instance's state):**
```c
Optional<Door> door = select any related by self->R1;
if (door.has_value() and door.value().curr_state == Closed) {
    // door is closed
}
```

State names are resolved like enum values — bare names that must
match a state declared in the corresponding state-diagram YAML.
Entity classes (no state machine) do not have `curr_state`.

### 3.1 Compiled State Enum

The compiler generates a C enum for each active class's states.

**Naming convention:**
- Enum type: `<ClassName>_STATE_ENUM_e`
- Enum values: `<StateName>_<ClassName>_STATE`

**Example — Elevator with states Idle, Moving_Up, Moving_Down, Stopping, At_Floor:**

```c
typedef enum {
    Idle_Elevator_STATE,
    Moving_Up_Elevator_STATE,
    Moving_Down_Elevator_STATE,
    Stopping_Elevator_STATE,
    At_Floor_Elevator_STATE
} Elevator_STATE_ENUM_e;
```

**Example — Door with states Closed, Opening, Open, Closing:**

```c
typedef enum {
    Closed_Door_STATE,
    Opening_Door_STATE,
    Open_Door_STATE,
    Closing_Door_STATE
} Door_STATE_ENUM_e;
```

In pycca code, state names are used without the suffix — the compiler
resolves `Idle` to `Idle_Elevator_STATE` based on the type of the
instance being checked:

```c
// Pycca — uses short names
if (self.curr_state == Idle) { ... }

// Compiles to:
if (self->_get_curr_state() == Idle_Elevator_STATE) { ... }
```

---

## 4. Relationship Traversal

Associations declared in `class-diagram.yaml` compile into navigable
relationship labels used in `select ... related by` statements.

### 4.1 Simple Traversal (1:1 and 1:M)

**Schema:**
```yaml
associations:
  - name: R1
    point_1: Elevator
    point_2: Door
    1_mult_2: "1"
    2_mult_1: "1"
```

**Pycca (from Elevator context):**
```
Optional<Door> door = select any related by self->R1;
```

**Pycca (from Door context):**
```
Optional<Elevator> elev = select any related by self->R1;
```

The compiler resolves `R1` by:
1. Looking up the association by label in the class diagram
2. Determining which endpoint is the "self" class
3. The target class is the other endpoint
4. Multiplicity determines whether `any` or `many` is valid

### 4.2 One-to-Many Traversal

**Schema:**
```yaml
  - name: R2
    point_1: Elevator
    point_2: Request
    1_mult_2: "0..*"
    2_mult_1: "1"
```

**Pycca (from Elevator — one-to-many side):**
```
Set<Request> reqs = select many related by self->R2;
Optional<Request> req = select any related by self->R2;    // picks one arbitrarily
```

**Pycca (from Request — many-to-one side):**
```
Optional<Elevator> elev = select any related by self->R2;  // always exactly one
```

### 4.3 Decomposing Associative Classes

Many-to-many (M:M) associations are not modeled directly. Instead,
the linking class is modeled as a regular entity or active class with
two separate relationships — one to each participant. This eliminates
the need for a special `associative` stereotype entirely.

**Example — FloorIndicator links Elevator and Floor:**

Before (associative — no longer supported):
```yaml
associations:
  - name: R10
    point_1: Elevator
    point_2: Floor
    1_mult_2: "0..*"
    2_mult_1: "0..*"

classes:
  - name: FloorIndicator
    stereotype: associative
    formalizes: R10
```

After (decomposed — two explicit relationships):
```yaml
associations:
  - name: R10
    point_1: Elevator
    point_2: FloorIndicator
    1_mult_2: "0..*"
    2_mult_1: "1"
  - name: R13
    point_1: Floor
    point_2: FloorIndicator
    1_mult_2: "0..*"
    2_mult_1: "1"

classes:
  - name: FloorIndicator
    stereotype: entity
```

Pycca traversal is always unambiguous — each relationship has exactly
two endpoints:

```c
// From FloorIndicator
Optional<Elevator> elev = select any related by self->R10;
Optional<Floor> floor = select any related by self->R13;

// From Elevator to all FloorIndicators
Set<FloorIndicator> indicators = select many related by self->R10;
```

### 4.4 Self-Referential Traversal

**Schema:**
```yaml
  - name: R9
    point_1: Request
    point_2: Request
    1_mult_2: "0..1"
    2_mult_1: "0..1"
    1_phrase_2: is followed by
    2_phrase_1: follows
```

A self-referential association is a single directed link from one
instance to another of the same class. Traversal syntax is the same
as any other relationship:

**Pycca:**
```
Optional<Request> next_req = select any related by self->R9;
```

If bidirectional traversal is needed (e.g., doubly-linked list),
model it as two separate associations — one for forward, one for
reverse.

### 4.5 Chained Traversal

Multiple hops can be chained in a single select:

**Pycca:**
```
Optional<FloorCallButton> button = select any related by self->R8->R7;
```

The compiler resolves each hop left-to-right, using the intermediate
class as the new "self" context for the next hop.

---

## 5. Referential Attributes (Relvars)

Referential attributes are **normally not declared by the modeler**. They
are derived automatically by the compiler from the associations in
`class-diagram.yaml`. Both sides of every association receive a relvar;
the data structure depends on the multiplicity.

**Exception — explicit relvars:** When a modeler declares an attribute
with a `referential` field (e.g., `referential: R16`), the compiler
must recognize that this attribute *is* the relvar for that relationship
and avoid generating a duplicate. This is used when the referential
attribute participates in the class's identifier (compound key) or
needs to be referenced by name in action code.

```yaml
# ShaftFloor is identified by (shaft, floor) — both are relvars
- name: r16_shaft_id
  type: UniqueID
  identifier: 1
  referential: R16
- name: r17_floor_num
  type: FloorNumber
  identifier: 1
  referential: R17
```

**TODO:** When an explicit relvar is declared, the compiler must also
verify that the attribute's type matches the identifier type of the
related class (e.g., `r16_shaft_id: UniqueID` must match `Shaft.shaft_id:
UniqueID`). The exact type-matching rules depend on how association
multiplicities translate to storage types, which is not yet defined.

### 5.1 Formalization Rules

The compiler generates a relvar on **each** endpoint of every association.
The relvar is identified by the relationship label itself — `R1`, `R2`,
`R11`, etc. The relationship label is unique across the entire model.

**Multiplicity determines the runtime behavior:**

| This side's multiplicity | Semantics |
|--------------------------|-----------|
| `1` | Exactly one related instance, always present |
| `0..1` | At most one related instance, may be empty |
| `0..*` | Zero or more related instances |
| `1..*` | One or more related instances |

### 5.2 Mandatory Relationship Validation

Relationships with multiplicity `1` or `1..*` are mandatory — the
related instance(s) must exist. Since `create` and `relate` are
separate statements, the compiler cannot enforce this mid-function.
Instead, mandatory relationships are checked at the **end of each
function body** (entry action, transition action, or method).

If a function body creates an instance that participates in a
mandatory relationship and does not `relate` it before the function
returns, the runtime raises an error.

```c
// This is valid — relate happens before function ends
create req of Request;
req.destination_floor = rcvd_evt.floor_num;
relate req to self across R2;   // R2 is mandatory on Request side
// end of function — R2 is satisfied

// This is a runtime error — mandatory R2 not satisfied
create req of Request;
req.destination_floor = rcvd_evt.floor_num;
// end of function — R2 not related
```

Optional relationships (`0..1`, `0..*`) have no such constraint.

### 5.3 Storage Strategy

The concrete storage strategy is an implementation detail of the
runtime — the modeler and pycca code only ever reference the
relationship label. Traversals return `Set<T>` (for `many`) or
`Optional<T>` (for `any`).

**Example — R1: Elevator 1---1 Door:**

Both `Elevator` and `Door` have a relvar identified as `R1`.
From Elevator, `R1` resolves to a single Door (`Optional<Door>`).
From Door, `R1` resolves to a single Elevator (`Optional<Elevator>`).

**Example — R2: Elevator 1---0..* Request:**

From Elevator, `R2` resolves to a set of Requests (`Set<Request>`).
From Request, `R2` resolves to a single Elevator (`Optional<Elevator>`).

**Example — R9: Request 0..1---0..1 Request (self-referential):**

A self-referential association is a single link from one instance to
another instance of the same class. Each instance has at most one R9
link. Traversal works the same as any other relationship:

```
Optional<Request> next_req = select any related by self->R9;
```

If bidirectional traversal is needed (e.g., a doubly-linked list),
model it as two separate associations — one for forward, one for
reverse. Each relationship is a single directed link.

### 5.4 Decomposed M:M Relationships

M:M relationships are decomposed into two 1:M relationships via a
linking class (see section 4.3). Because each relationship is a
standard two-endpoint association, relvars follow the standard rules
from section 5.1 — no special handling is needed.

### 5.5 Relvars in Pycca Code

Relvars are not directly accessible in pycca code. All navigation
goes through relationship traversal (`select ... related by`)
and all link management goes through `relate`/`unrelate`.

```c
// Navigate a relationship
Optional<Door> door = select any related by self->R1;

// Check if a link exists
Optional<Request> next_req = select any related by self->R9;
if (!next_req.has_value()) {
    // no next request in queue
}

// Modify links — only through relate/unrelate
relate self to some_door across R1;     // correct
unrelate self from some_door across R1; // correct
```

---

## 6. Event Parameter Scoping

Events declared in `state-diagrams/<Class>.yaml` compile into
receivable signals with typed parameters. Event parameters are
accessed via the `rcvd_evt.` prefix — never as bare names.

**Schema:**
```yaml
events:
  - name: Floor_reached
    params:
      - name: floor_num
        type: FloorNumber
```

### 6.1 In Guard Expressions

```yaml
guard: "rcvd_evt.floor_num == self.next_stop_floor"
```

`rcvd_evt.floor_num` is the event parameter. `self.next_stop_floor` is
an instance attribute. Both are explicitly prefixed — no ambiguity.

### 6.2 In Transition Actions

```yaml
action: "self.current_floor = rcvd_evt.floor_num;"
```

### 6.3 In Entry Actions

`rcvd_evt` is also available in the entry action of the target state,
since the entry action executes as part of the same micro-step as the
transition:

```yaml
states:
  - name: Displaying
    entry_action: "self.displayed_floor = rcvd_evt.floor_num;"
```

### 6.4 Pass-by-Value Semantics

Event parameters are **passed by value**. They are copies of the
original data at the time of `generate`. Modifying an event parameter
within an action block does not affect the source attribute:

```
// Shaft entry action
Optional<Elevator> elev = select any related by self->R11;
generate Floor_reached(floor_num: self.current_floor) to elev.value();
// self.current_floor is copied into the event — not referenced

// Elevator transition action
rcvd_evt.floor_num = rcvd_evt.floor_num + 1;  // OK — modifies local copy only
// does NOT affect Shaft's self.current_floor
```

### 6.5 Allowed Event Parameter Types

Event parameters must be **value types** — no pointers or references.
Allowed types:

- Scalar primitives: `Integer`, `Real`, `Boolean`, `String`
- Domain-defined scalars (e.g., `FloorNumber`, `Direction`)
- Enum types
- `UniqueID` (identifiers are basic types and may be passed as event data)
- `Timestamp`, `Duration` (opaque time types are value types)

**Not allowed as event parameters:**
- Instance references (use relationship traversal instead)
- `List<T>`, `Set<T>`, `Optional<T>` (container types)
- `Fn` types (function references)

---

## 7. Generate — Event Data Passing

When generating an event with parameters, use named parameter syntax:

**Schema (target class events):**
```yaml
events:
  - name: Floor_reached
    params:
      - name: floor_num
        type: FloorNumber
```

**Pycca:**
```
Optional<Elevator> elev = select any related by self->R11;
generate Floor_reached(floor_num: self.current_floor) to elev.value();
```

**Delayed generate:**
```
generate Door_close to self delay duration_s(5);
```

**Cancel a pending delayed event:**
```
cancel Door_close from self to self;
```

The compiler validates:
- The event name exists on the target class
- All required parameters are provided
- Parameter names match the event definition
- Parameter types are compatible
- Delay expression is of type `Duration`
- Cancel sender and target are bound instance variables

---

## 8. Subtype Inheritance

A class with `specializes: R<N>` inherits all attributes **and relvars**
from its supertype (the other endpoint of the subtype/supertype partition).

### 8.1 Attribute Inheritance

**Schema:**
```yaml
- name: Call
  partitions:
    - name: R5
      subtypes: [ElevatorCall, FloorCall]
  attributes:
    - name: call_id
      type: UniqueID
      identifier: 1

- name: ElevatorCall
  specializes: R5
  attributes:
    - name: destination_floor
      type: FloorNumber
```

Note: `ElevatorCall` does **not** redeclare `call_id`. The identifier
is inherited from the supertype `Call`.

**Compiled attribute set for ElevatorCall:**
```
call_id             (inherited from Call — shared identifier)
destination_floor   (declared on ElevatorCall)
```

### 8.2 Relvar Inheritance

Relvars derived from the supertype's associations are also inherited.
`Call` participates in R7 (CallButton→Call) and R8 (Call→Request),
so `ElevatorCall` inherits both relvars:

```
r7_callbutton       (inherited — Call's R7 relvar)
r8_request          (inherited — Call's R8 relvar)
```

**Pycca (inside ElevatorCall action):**
```
// Traverse inherited relationship — compiler resolves through supertype
Optional<CallButton> button = select any related by self->R7;

// Access inherited attribute
self.call_id

// Access own attribute
self.destination_floor
```

### 8.3 Subtype Strategy

Subtypes use **reference-based** generalization: the subtype and
supertype are separate instances linked by a relvar. This means:
- The supertype instance always exists alongside the subtype instance
- The supertype's identifier is shared (same `call_id` value)
- Traversal from subtype to supertype: `Optional<Call> call = select any related by self->R5;`
- Traversal from supertype to subtype: `Optional<ElevatorCall> ec = select any related by self->R5;`

### 8.4 Compiler Resolution Order

The compiler resolves attribute and relvar references by searching:
1. The current class's declared attributes
2. The current class's compiled relvars (from its own associations)
3. The supertype's declared attributes (if `specializes` is set)
4. The supertype's compiled relvars
5. Recursively up the supertype chain

---

## 9. Create and Relate

When creating an instance, the compiler needs to know which
relationships to establish. `relate` sets the relvars on both sides.

### 9.1 Simple Create and Relate

**Pycca:**
```
create req of Request;
req.destination_floor = fc.destination_floor;
relate req to self across R2;
```

The `relate` statement:
1. Looks up R2 in the class diagram
2. Confirms `req` (Request) and `self` (Elevator) are the two endpoints
3. Sets relvars on **both** sides:
   - `req.r2_elevator` → self (scalar, required — many-to-one side)
   - `self.r2_request` → adds req to set (one-to-many side)

### 9.2 Linking Class Relate

M:M associations are decomposed into two 1:M relationships via a
linking class (see section 4.3). To create the link, create the
linking instance and relate it to each participant using the two
separate relationships:

```c
create indicator of FloorIndicator;
relate self to indicator across R10;   // Elevator to FloorIndicator
relate floor to indicator across R13;  // Floor to FloorIndicator
```

Each `relate` is a standard two-endpoint operation — no special
syntax is needed.

### 9.3 Unrelate

`unrelate` reverses the process — clears relvars on both sides:

```
unrelate req from self across R2;
```

- `req.r2_elevator` → null
- `self.r2_request` → removes req from set

### 9.4 Subtype Relate

When creating a subtype instance, relate it to its supertype:

```
create ec of ElevatorCall;
create call of Call;
relate ec to call across R5;
ec.destination_floor = floor_num;
```

After `relate`, `ec` inherits all of `call`'s attributes and relvars.
The shared identifier (`call_id`) is the same on both instances.

---

## 10. Bridge Calls

Bridge operations compile from the `bridges` stanza in `class-diagram.yaml`
and `DOMAINS.yaml`.

**Schema (class-diagram.yaml — required bridge):**
```yaml
bridges:
  - to_domain: Building
    direction: required
    operations:
      - IsTopFloor
      - IsBottomFloor
```

**Schema (DOMAINS.yaml — bridge definition with params):**
```yaml
bridges:
  - from: Elevator
    to: Building
    operations:
      - name: IsTopFloor
        params:
          - name: floor_num
            type: FloorNumber
        return: Boolean
```

**Pycca:**
```
Boolean is_top = Building::IsTopFloor(self.current_floor);
```

The compiler validates:
- The bridge domain exists
- The operation is declared in both the requiring and providing sides
- Parameter count and types match

---

## 11. Methods

Methods are defined on classes and follow the same pycca action
language syntax as entry actions and transition actions.

### 11.1 Class Methods

Class methods have `scope: class`. They have no `self` — they operate
on the class as a whole (e.g., querying across all instances).

**Schema (class-diagram.yaml):**
```yaml
classes:
  - name: Elevator
    methods:
      - name: GetIdleCount
        scope: class
        return: Integer
        action: |
          Set<Elevator> idle_elevs = select many from instances of Elevator
              where [] |e: Elevator| -> Boolean { return e.curr_state == Idle; };
          Integer count = idle_elevs.size();
```

**Pycca (calling):**
```
Integer count = Elevator::GetIdleCount();
```

### 11.2 Instance Methods

Instance methods have `scope: instance`. They have `self` in scope —
the instance the method is called on.

**Schema (class-diagram.yaml):**
```yaml
      - name: PeekNextFloor
        scope: instance
        return: FloorNumber
        action: |
          Optional<Request> next_req = select any related by self->R2;
          if (next_req.has_value()) {
              return next_req.value().destination_floor;
          }
          return self.current_floor;
```

**Pycca (calling):**
```
// On self
FloorNumber next = self.PeekNextFloor();

// On another instance
Optional<Elevator> elev = select any related by self->R11;
FloorNumber next = elev.value().PeekNextFloor();
```

### 11.3 Method Arguments

Method arguments are accessed via the `arg.` prefix, analogous to
`rcvd_evt.` for event parameters and `self.` for instance attributes.

```c
// Schema
methods:
  - name: SetFloor
    params:
      - name: floor_num
        type: FloorNumber
    action: "self.current_floor = arg.floor_num;"
```

```c
// Calling
self.SetFloor(3);
```

`arg.` is in scope within the method body only. It is not available
in state entry actions or transition actions (use `rcvd_evt.` there).

### 11.4 Method Bodies

Method bodies can be defined in two places:
- **Inline** in `class-diagram.yaml` via the `action` field
- **Separate file** in `class-methods.yaml` alongside the state diagrams

Method bodies follow the same pycca syntax as state entry actions and
transition actions. All name resolution rules apply:
- `self.` for instance attributes (instance methods only)
- `arg.` for method parameters
- `rcvd_evt.` is **not** available (methods are not triggered by events)
- Bare names must be bound locally (`select`, `create`, C declarations)

### 11.5 Class Variables

Class-scoped attributes (`scope: class`) are shared across all instances.
They are accessed using `ClassName::` syntax.

**Schema:**
```yaml
classes:
  - name: Elevator
    attributes:
      - name: total_count
        type: Integer
        scope: class
```

**Pycca:**
```
Elevator::total_count = Elevator::total_count + 1;
Integer n = Elevator::total_count;
```

Class variables follow the same visibility rules as instance attributes.
They are not accessed via `self.` — always via `ClassName::`.

The compiler validates:
- Class method calls use `ClassName::` syntax
- Instance method calls use `self.` or `var.` syntax
- Instance methods are not called with `ClassName::` (no instance)
- Class methods are not called with `self.` (no class context)
- `rcvd_evt` is not referenced inside method bodies
- Method parameters and return types match at call sites

---

## 12. Enum and Type Resolution

Types declared in `types.yaml` compile into named constants usable
in assignments and comparisons.

**Schema:**
```yaml
types:
  - name: Direction
    base: enum
    values: [Up, Down, Stopped]
```

**Pycca:**
```c
self.direction = Up;
if (self.direction == Stopped) {
    ...
}
```

Enum values are unqualified — they are globally unique within a domain.
The compiler resolves bare names (like `Up`) by searching the domain's
type definitions for a matching enum value.

---

## 13. Compilation Validation Summary

The compiler should validate the following at compile time:

### 13.1 Attribute and Relvar Checks

| Check | Source | Pycca construct |
|-------|--------|-----------------|
| Attribute exists on class (or inherited) | class-diagram.yaml | `self.<attr>` |
| Attribute on other instance exists | class-diagram.yaml | `var.value().<attr>` |
| Visibility: private attr not accessed externally | class-diagram.yaml | `var.value().<private_attr>` → error |
| Every non-subtype class has identifier set 1 | class-diagram.yaml | `identifier: [1]` on at least one attr |
| Identifier not assigned after creation | class-diagram.yaml | `self.<id> = ...` → error |
| Non-UniqueID identifier provided at create | class-diagram.yaml | `create var of Class(id: val)` |
| `curr_state` not assigned in pycca | compiler-derived | `self.curr_state = ...` → error |
| `curr_state` only on active classes | state-diagram YAML | entity class has no `curr_state` |
| Container attribute types are valid | class-diagram.yaml | `List<T>`, `Set<T>` only |

### 13.2 Relationship Checks

| Check | Source | Pycca construct |
|-------|--------|-----------------|
| Relationship label exists | class-diagram.yaml | `related by self->R<N>` |
| Target class is valid endpoint of R<N> | class-diagram.yaml | `select ... ->R<N>` |
| Multiplicity matches select cardinality | class-diagram.yaml | `any` → `Optional<T>`, `many` → `Set<T>` |
| Chained traversal types are consistent | class-diagram.yaml | each hop resolves correctly |
| Relate endpoints match association | class-diagram.yaml | `relate a to b across R<N>` |
| Relate endpoints match association | class-diagram.yaml | both vars must be endpoints of R<N> |

### 13.3 Event Checks

| Check | Source | Pycca construct |
|-------|--------|-----------------|
| Event exists on target class | state-diagram YAML | `generate Event to var` |
| Event params match definition | state-diagram YAML | `generate Event(p: v)` |
| Event params in scope | state-diagram YAML | guards, transition actions, entry actions |
| Generate target is bound variable | select in same action block | `generate E to var` |
| Generate target is not bare class name | class-diagram.yaml | `generate E to ClassName` → error |
| Delay expression is `Duration` type | type check | `generate E to var delay <expr>` |
| Cancel sender/target are bound variables | action block scope | `cancel E from a to b` |

### 13.4 Type Checks

| Check | Source | Pycca construct |
|-------|--------|-----------------|
| Enum value exists in domain types | types.yaml | bare name in expr |
| Bridge operation exists | DOMAINS.yaml + class-diagram.yaml | `Domain::Op(...)` |
| Bridge param count and types match | DOMAINS.yaml | `Domain::Op(a, b)` |
| Assignment type compatibility | types.yaml + class-diagram.yaml | `self.attr = expr` |
| Container element type is valid | type system | `List<T>`, `Set<T>` |
| Lambda param types match container element type | type system | `.filter(lambda)`, `.sort(lambda)` |
| Lambda return type matches expected | type system | `where` → `Boolean`, `sort` → `Boolean` |
| `Fn` variable type matches lambda signature | type system | `Fn(T) -> R var = lambda` |
| No containers as event params | type system | event param type check |
| No containers as method return types | type system | method return type check |
| `Timestamp`/`Duration` arithmetic is valid | type system | `Timestamp - Timestamp` → `Duration` |
| `now()` returns `Timestamp` | built-in | type inference |
| `duration_s()`/`duration_ms()` return `Duration` | built-in | type inference |
