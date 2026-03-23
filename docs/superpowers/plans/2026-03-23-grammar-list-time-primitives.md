# Grammar Extension: List, Time, and Lambda Primitives

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Lark grammar in `pycca/grammar.py` to parse all new constructs defined in the 2026-03-23 list/time primitives design: container types, lambdas, for-each loops, method calls, delayed generate, cancel, arithmetic, and time built-ins.

**Architecture:** The grammar is a single Lark string (`PYCCA_GRAMMAR`) in `pycca/grammar.py` that feeds two parsers: `GUARD_PARSER` (Earley, start=`expr`) and `STATEMENT_PARSER` (Earley, start=`start`). Both parsers use Earley — the new grammar has inherent ambiguities (e.g., `NAME NAME "="` for typed decls vs `NAME "="` for assignments) that LALR cannot resolve without significant restructuring. Earley handles these naturally. Each task adds grammar rules and corresponding test cases. All tasks are parse-level only — no runtime semantics, no AST transformation.

**Out of scope:** `else if` chains, `while` loops, `switch` statements. These are listed in SYNTAX.md as "not yet implemented" and are not needed for the current design. They can be added in a future grammar extension.

**Tech Stack:** Python 3.13, Lark parser library, pytest

**Spec:** `docs/2026-03-23-list-time-primitives-design.md`
**Syntax ref:** `pycca/SYNTAX.md`

---

## File Map

| File | Role |
|------|------|
| `pycca/grammar.py` | Lark grammar string + parser objects (modify) |
| `tests/test_pycca.py` | Main grammar test file — new construct tests (modify) |
| `tests/test_pycca_grammar.py` | Legacy module-level tests (leave as-is, verify still pass) |

All changes are in these three files. No new files needed.

---

## Task 1: Typed Variable Declarations and Assignments

The current grammar only supports `self.attr = expr;`. We need general
variable declarations (`Type var = expr;`) and variable assignments
(`var = expr;`, `var.attr = expr;`). This is foundational — nearly every
subsequent task depends on being able to declare typed variables.

**Files:**
- Modify: `pycca/grammar.py:25-112` (grammar string)
- Modify: `tests/test_pycca.py` (add new test section)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pycca.py`:

```python
# ---------------------------------------------------------------------------
# Typed variable declarations
# ---------------------------------------------------------------------------

def test_typed_var_decl_simple():
    """FloorNumber my_floor = self.current_floor;"""
    STATEMENT_PARSER.parse("FloorNumber my_floor = self.current_floor;")


def test_typed_var_decl_integer_literal():
    """Integer count = 0;"""
    STATEMENT_PARSER.parse("Integer count = 0;")


def test_var_assignment():
    """var = expr; (non-self assignment)"""
    STATEMENT_PARSER.parse("count = count + 1;")


def test_var_dot_attr_assignment():
    """var.attr = expr; (cross-instance write)"""
    STATEMENT_PARSER.parse("req.destination_floor = 5;")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py::test_typed_var_decl_simple tests/test_pycca.py::test_typed_var_decl_integer_literal tests/test_pycca.py::test_var_assignment tests/test_pycca.py::test_var_dot_attr_assignment -v`
Expected: FAIL — grammar doesn't support these forms yet

- [ ] **Step 3: Extend grammar**

In `pycca/grammar.py`, update the grammar string:

1. Add `typed_var_decl` and `var_assignment` to the `statement` rule:
```
statement: typed_var_decl
         | assignment
         | var_assignment
         | generate_stmt
         ...
```

2. Add the new rules:
```
// --- Typed variable declaration ---
// Type var = expr;
typed_var_decl: NAME NAME "=" expr ";"

// --- Variable assignment (non-self) ---
// var = expr;
// var.attr = expr;
var_assignment: NAME "=" expr ";"
             | NAME "." NAME "=" expr ";"
```

3. Update the existing `assignment` rule to remain as `self.attr = expr;` (unchanged).

4. Add arithmetic with a proper precedence tower (highest to lowest
   precedence: atom → mul → add → compare → and → or):

```
?expr: or_expr

or_expr: and_expr "or" or_expr
       | and_expr

and_expr: compare_expr "and" and_expr
        | compare_expr

compare_expr: add_expr OP add_expr
            | add_expr

add_expr: add_expr "+" mul_expr
        | add_expr "-" mul_expr
        | mul_expr

mul_expr: mul_expr "*" atom
        | atom
```

Keep `cardinality_expr` as a deprecated alternative in `atom` for
backward compatibility (we do not remove old syntax in this plan):
```
atom: ...
    | "cardinality" NAME -> cardinality_expr
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All new tests PASS. Existing tests still PASS.

**Parser change:** Switch `STATEMENT_PARSER` from LALR-with-fallback to
Earley directly. The new grammar has ambiguities (typed decl vs assignment)
that Earley handles naturally. Update the parser instantiation at the
bottom of `grammar.py`:
```python
GUARD_PARSER = Lark(PYCCA_GRAMMAR, start="expr", parser="earley")
STATEMENT_PARSER = Lark(PYCCA_GRAMMAR, start="start", parser="earley")
```

**Note:** The test `test_existing_select_from_instances` uses the old
bare-boolean `where` clause. This must continue to pass — the old
`select_stmt` rule stays alongside the new lambda-where form (added in
Task 6). We do not remove old syntax in this plan; we extend it.

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): typed variable declarations, var assignment, arithmetic"
```

---

## Task 2: Container Type Syntax in Declarations

Add parsing for `List<T>`, `Set<T>`, `Optional<T>`, and `Fn(T) -> R` in
type positions.

**Files:**
- Modify: `pycca/grammar.py` (grammar string)
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write failing tests**

```python
# ---------------------------------------------------------------------------
# Container type declarations
# ---------------------------------------------------------------------------

def test_list_type_decl():
    """List<FloorNumber> floors = List<FloorNumber>();"""
    STATEMENT_PARSER.parse("List<FloorNumber> floors = List<FloorNumber>();")


def test_set_type_decl():
    """Set<DestFloorButton> buttons = Set<DestFloorButton>();"""
    STATEMENT_PARSER.parse("Set<DestFloorButton> buttons = Set<DestFloorButton>();")


def test_optional_type_decl():
    """Optional<Door> door = select any related by self->R1;"""
    STATEMENT_PARSER.parse("Optional<Door> door = select any related by self->R1;")


def test_fn_type_decl():
    """Fn(DestFloorButton) -> Boolean filter_fn = ...; (lambda assigned later)"""
    # Just test the type parses — lambda body is Task 3
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton) -> Boolean filter_fn = some_var;'
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py::test_list_type_decl tests/test_pycca.py::test_set_type_decl tests/test_pycca.py::test_optional_type_decl tests/test_pycca.py::test_fn_type_decl -v`
Expected: FAIL

- [ ] **Step 3: Extend grammar**

1. Replace the simple `NAME NAME "=" expr ";"` typed_var_decl with a
   `type_expr` that handles parameterized types:

```
// --- Type expressions ---
type_expr: NAME                                          // simple: FloorNumber, Integer
         | NAME "<" NAME ">"                             // generic: List<T>, Set<T>, Optional<T>
         | "Fn" "(" fn_param_types? ")" "->" type_expr   // function: Fn(T, U) -> R

fn_param_types: type_expr ("," type_expr)*

// --- Typed variable declaration (updated) ---
typed_var_decl: type_expr NAME "=" expr ";"
```

2. Add constructor calls to `atom`:
```
atom: NUMBER -> number
    | ESCAPED_STRING -> string
    | NAME "<" NAME ">" "(" ")"  -> container_constructor   // List<T>(), Set<T>()
    | NAME "." NAME "(" arglist? ")" -> method_call          // var.method(args)
    | NAME "." NAME -> dotted_name
    | NAME "(" arglist? ")" -> func_call                     // now(), duration_s(5)
    | NAME -> name
    | "(" expr ")"
```

**Note:** With Earley parsing, alternative ordering does not affect
precedence. Earley handles the ambiguity between `container_constructor`,
`method_call`, `dotted_name`, and `name` by exploring all alternatives.

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): container types List<T>, Set<T>, Optional<T>, Fn type"
```

---

## Task 3: Lambda Expressions

Add full lambda syntax: `[captures] |params| -> ReturnType { body }`.

**Files:**
- Modify: `pycca/grammar.py`
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write failing tests**

```python
# ---------------------------------------------------------------------------
# Lambda expressions
# ---------------------------------------------------------------------------

def test_lambda_no_captures():
    """[] |a: DestFloorButton, b: DestFloorButton| -> Boolean { return a.x < b.x; }"""
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton, DestFloorButton) -> Boolean cmp = '
        '[] |a: DestFloorButton, b: DestFloorButton| -> Boolean { return a.x < b.x; };'
    )


def test_lambda_with_captures():
    """[my_floor] |btn: DestFloorButton| -> Boolean { return btn.x > my_floor; }"""
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton) -> Boolean pred = '
        '[my_floor] |btn: DestFloorButton| -> Boolean { return btn.x > my_floor; };'
    )


def test_lambda_multi_capture():
    """[my_floor, my_id] |btn: DestFloorButton| -> Boolean { ... }"""
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton) -> Boolean pred = '
        '[my_floor, my_id] |btn: DestFloorButton| -> Boolean '
        '{ if (btn.r4 != my_id) { return 0; } return btn.x > my_floor; };'
    )


def test_lambda_empty_captures_single_param():
    """Simplest lambda form"""
    STATEMENT_PARSER.parse(
        'Fn(Floor) -> Boolean pred = '
        '[] |f: Floor| -> Boolean { return f.floor_num == 3; };'
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py -k lambda -v`
Expected: FAIL

- [ ] **Step 3: Extend grammar**

Add lambda rules:

```
// --- Lambda expression ---
lambda_expr: "[" capture_list? "]" "|" lambda_params "|" "->" NAME "{" lambda_body "}"

capture_list: NAME ("," NAME)*

lambda_params: lambda_param ("," lambda_param)*
lambda_param: NAME ":" NAME

lambda_body: lambda_stmt+

lambda_stmt: "return" expr ";"
           | assignment
           | var_assignment
           | typed_var_decl
           | if_stmt
```

Add `lambda_expr` as an `atom` alternative:
```
atom: ...
    | lambda_expr
```

**Important — do this first:** Add `return_stmt` to the main `statement`
rule before adding lambda rules. Lambda bodies contain `if_stmt`, which
expands to `statement*`, so `return` must be a valid `statement` for
`return` to work inside `if` blocks within lambdas.

```
statement: ...
         | return_stmt

return_stmt: "return" expr ";"
           | "return" ";"
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): lambda expressions with captures and typed params"
```

---

## Task 4: Method Calls and Container Method Chains

Parse `var.method(args)`, `var.method(lambda)`, and chained calls.
This replaces `cardinality` with `.size()`.

**Files:**
- Modify: `pycca/grammar.py`
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write failing tests**

```python
# ---------------------------------------------------------------------------
# Method calls on containers
# ---------------------------------------------------------------------------

def test_method_call_size():
    """lit_btns.size() — replaces cardinality"""
    STATEMENT_PARSER.parse("Integer count = lit_btns.size();")


def test_method_call_is_empty():
    """lit_btns.is_empty()"""
    STATEMENT_PARSER.parse("if (lit_btns.is_empty()) { generate Idle to self; }")


def test_method_call_has_value():
    """door.has_value()"""
    STATEMENT_PARSER.parse("if (door.has_value()) { generate Open to door.value(); }")


def test_method_call_value():
    """door.value().curr_state — chained value access"""
    STATEMENT_PARSER.parse("if (door.value().curr_state == Closed) { self.x = 1; }")


def test_method_call_filter_with_lambda():
    """btns.filter(lambda)"""
    STATEMENT_PARSER.parse(
        'Set<DestFloorButton> lit = btns.filter('
        '[] |b: DestFloorButton| -> Boolean { return b.curr_state == Lit; });'
    )


def test_method_call_sort_with_lambda():
    """btns.sort(lambda)"""
    STATEMENT_PARSER.parse(
        'btns.sort([] |a: DestFloorButton, b: DestFloorButton| -> Boolean '
        '{ return a.floor_num < b.floor_num; });'
    )


def test_method_call_push_back():
    """floors.push_back(3)"""
    STATEMENT_PARSER.parse("floors.push_back(3);")


def test_method_call_pop_front():
    """Optional<FloorNumber> next = floors.pop_front();"""
    STATEMENT_PARSER.parse("Optional<FloorNumber> next = floors.pop_front();")


def test_method_call_map():
    """btns.map(lambda) -> List<FloorNumber>"""
    STATEMENT_PARSER.parse(
        'List<FloorNumber> floors = btns.map('
        '[] |b: DestFloorButton| -> FloorNumber { return b.r5_floor_num; });'
    )


def test_method_call_find_with_lambda():
    """btns.find(lambda) -> Optional<T>"""
    STATEMENT_PARSER.parse(
        'Optional<DestFloorButton> btn = btns.find('
        '[target] |b: DestFloorButton| -> Boolean { return b.r5_floor_num == target; });'
    )


def test_method_call_get():
    """floors.get(0) -> Optional<T>"""
    STATEMENT_PARSER.parse("Optional<FloorNumber> f = floors.get(0);")


def test_method_call_push_front():
    """floors.push_front(1)"""
    STATEMENT_PARSER.parse("floors.push_front(1);")


def test_method_call_insert():
    """floors.insert(0, 3)"""
    STATEMENT_PARSER.parse("floors.insert(0, 3);")


def test_method_call_contains():
    """my_list.contains(item)"""
    STATEMENT_PARSER.parse("if (my_list.contains(item)) { self.x = 1; }")


def test_chained_method_double():
    """sorted.peek_front().value().r5_floor_num — two method calls then attr"""
    STATEMENT_PARSER.parse(
        "self.x = sorted_btns.peek_front().value().r5_floor_num;"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py -k method_call -v`
Expected: FAIL

- [ ] **Step 3: Extend grammar**

The `method_call` atom was partially added in Task 2. Extend it to
handle:

1. Method calls as standalone statements (not just in expressions):
```
statement: ...
         | method_call_stmt

// var.method(args);
method_call_stmt: NAME "." NAME "(" arglist? ")" ";"
```

2. Chained access needs to support arbitrary depth, e.g.,
   `below_sorted.peek_front().value().r5_floor_num`. Use a recursive
   `access_chain` rule instead of a fixed-depth alternative:

```
// Recursive access chain — handles any depth of method().method().attr
access_chain: NAME "." NAME "(" arglist? ")"                    -> method_call
            | access_chain "." NAME "(" arglist? ")"            -> chained_method_call
            | access_chain "." NAME                             -> chained_attr_access
```

Add `access_chain` as an `atom` alternative. This handles:
- `door.value()` — one method call
- `door.value().curr_state` — method then attr
- `sorted.peek_front().value().r5_floor_num` — two methods then attr

3. Make sure `arglist` can include lambda expressions (already an atom,
   so this should work if lambda_expr is an atom alternative).

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS. Verify `test_statement_bridge_call` still passes
(bridge call syntax uses `[args]` not `(args)` — no conflict).

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): method calls, container methods, chained access"
```

---

## Task 5: For-Each Loop

Add `for (Type var : collection) { stmts }` syntax.

**Files:**
- Modify: `pycca/grammar.py`
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write failing tests**

```python
# ---------------------------------------------------------------------------
# For-each loop
# ---------------------------------------------------------------------------

def test_for_each_simple():
    """for (DestFloorButton btn : my_list) { ... }"""
    STATEMENT_PARSER.parse(
        "for (DestFloorButton btn : my_list) { generate Foo to btn; }"
    )


def test_for_each_with_method_call():
    """for loop with method call in body"""
    STATEMENT_PARSER.parse(
        "for (Floor f : floors) { self.x = f.floor_num; }"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py -k for_each -v`
Expected: FAIL

- [ ] **Step 3: Extend grammar**

```
statement: ...
         | for_each_stmt

// for (Type var : collection_expr) { stmts }
// Collection is an expr to support method call results, not just variable names
for_each_stmt: "for" "(" NAME NAME ":" expr ")" "{" statement* "}"
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): for-each loop over List<T> and Set<T>"
```

---

## Task 6: Select with Lambda Where Clause

Update `select` statements to accept lambda `where` clauses and return
typed results.

**Files:**
- Modify: `pycca/grammar.py`
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write failing tests**

```python
# ---------------------------------------------------------------------------
# Select with lambda where
# ---------------------------------------------------------------------------

def test_select_many_typed_no_where():
    """Set<DestFloorButton> btns = select many from instances of DestFloorButton;"""
    STATEMENT_PARSER.parse(
        "Set<DestFloorButton> btns = select many from instances of DestFloorButton;"
    )


def test_select_any_typed_no_where():
    """Optional<Floor> f = select any from instances of Floor;"""
    STATEMENT_PARSER.parse(
        "Optional<Floor> f = select any from instances of Floor;"
    )


def test_select_many_with_lambda_where():
    """select many ... where [captures] |param| -> Boolean { ... };"""
    STATEMENT_PARSER.parse(
        'Set<DestFloorButton> lit = select many from instances of DestFloorButton '
        'where [my_id] |btn: DestFloorButton| -> Boolean { return btn.r4 == my_id; };'
    )


def test_select_any_with_lambda_where():
    """select any ... where lambda;"""
    STATEMENT_PARSER.parse(
        'Optional<Floor> f = select any from instances of Floor '
        'where [target] |f: Floor| -> Boolean { return f.floor_num == target; };'
    )


def test_select_related_typed():
    """Set<DestFloorButton> btns = select many related by self->R4;"""
    STATEMENT_PARSER.parse(
        "Set<DestFloorButton> btns = select many related by self->R4;"
    )


def test_select_related_with_where():
    """select many related by ... where lambda;"""
    STATEMENT_PARSER.parse(
        'Set<DestFloorButton> lit = select many related by self->R4 '
        'where [] |btn: DestFloorButton| -> Boolean { return btn.curr_state == Lit; };'
    )


def test_select_related_chained():
    """Optional<Floor> f = select any related by self->R2->R3;"""
    STATEMENT_PARSER.parse(
        "Optional<Floor> f = select any related by self->R2->R3;"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py -k "select_many_typed or select_any_typed or select_related_typed or select_related_with_where or select_related_chained or select_many_with_lambda or select_any_with_lambda" -v`
Expected: FAIL

- [ ] **Step 3: Extend grammar**

The new select forms are **typed variable declarations** on the left with
a select expression on the right. The cleanest approach: add select
expressions as valid `expr` alternatives so `typed_var_decl` can handle
them naturally.

```
// --- Select expressions (return Set<T> or Optional<T>) ---
?expr: ...
     | select_expr

select_expr: "select" ("any"|"many") "from" "instances" "of" NAME ("where" lambda_expr)?
           | "select" ("any"|"many") "related" "by" traversal_chain ("where" lambda_expr)?

traversal_chain: NAME "->" NAME ("->" NAME)*
```

The old `select_stmt` and `select_related_stmt` rules remain for backward
compatibility (untyped form: `select any var from instances of Class;`).
They will be used until the elevator model is migrated.

- [ ] **Step 4: Run all tests, verify old-style selects still parse**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS — both old-style and new-style selects parse.

Key regression checks — these must still pass:
- `test_existing_select_from_instances` (old bare-boolean `where`)
- `test_select_related_by` (old untyped `select any var related by`)
- `test_select_related_by_elev`
- `test_statement_select_any`

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): typed select with lambda where clause, chained traversal"
```

---

## Task 7: Delayed Generate and Cancel

Add `generate ... delay <expr>;` and `cancel Event from sender to target;`.

**Files:**
- Modify: `pycca/grammar.py`
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write failing tests**

```python
# ---------------------------------------------------------------------------
# Delayed generate and cancel
# ---------------------------------------------------------------------------

def test_delayed_generate():
    """generate Door_close to self delay duration_s(5);"""
    STATEMENT_PARSER.parse("generate Door_close to self delay duration_s(5);")


def test_delayed_generate_with_params():
    """generate with params and delay"""
    STATEMENT_PARSER.parse(
        "generate Open_reminder(floor: self.current_floor) to door delay duration_ms(500);"
    )


def test_cancel():
    """cancel Door_close from self to self;"""
    STATEMENT_PARSER.parse("cancel Door_close from self to self;")


def test_cancel_different_targets():
    """cancel Timer_expired from controller to door;"""
    STATEMENT_PARSER.parse("cancel Timer_expired from controller to door;")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pycca.py -k "delayed_generate or cancel" -v`
Expected: FAIL

- [ ] **Step 3: Extend grammar**

Update `generate_stmt` to accept optional delay:
```
generate_stmt: "generate" NAME "to" NAME ";"
             | "generate" NAME "(" param_list ")" "to" NAME ";"
             | "generate" NAME "to" NAME "delay" expr ";"
             | "generate" NAME "(" param_list ")" "to" NAME "delay" expr ";"
```

Add cancel:
```
statement: ...
         | cancel_stmt

cancel_stmt: "cancel" NAME "from" NAME "to" NAME ";"
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pycca/grammar.py tests/test_pycca.py
git commit -m "feat(grammar): delayed generate and cancel statement"
```

---

## Task 8: Time Built-ins and Expressions

Add `now()`, `duration_s()`, `duration_ms()`, `in_s()`, `in_ms()` as
parseable function calls, and verify time arithmetic works.

**Files:**
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write tests**

These should already parse thanks to the `func_call` atom added in Task 2.
Write tests to confirm:

```python
# ---------------------------------------------------------------------------
# Time built-ins
# ---------------------------------------------------------------------------

def test_now_builtin():
    """Timestamp t = now();"""
    STATEMENT_PARSER.parse("Timestamp t = now();")


def test_duration_s():
    """Duration d = duration_s(5);"""
    STATEMENT_PARSER.parse("Duration d = duration_s(5);")


def test_duration_ms():
    """Duration d = duration_ms(500);"""
    STATEMENT_PARSER.parse("Duration d = duration_ms(500);")


def test_in_s():
    """Integer s = in_s(d);"""
    STATEMENT_PARSER.parse("Integer s = in_s(d);")


def test_in_ms():
    """Integer ms = in_ms(d);"""
    STATEMENT_PARSER.parse("Integer ms = in_ms(d);")


def test_timestamp_arithmetic():
    """Duration elapsed = now() - start_time;"""
    STATEMENT_PARSER.parse("Duration elapsed = now() - start_time;")


def test_duration_arithmetic():
    """Duration total = d1 + d2;"""
    STATEMENT_PARSER.parse("Duration total = d1 + d2;")


def test_duration_multiply():
    """Duration scaled = d * 3;"""
    STATEMENT_PARSER.parse("Duration scaled = d * 3;")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_pycca.py -k "now_builtin or duration_s or duration_ms or in_s or in_ms or timestamp_arithmetic or duration_arithmetic or duration_multiply" -v`
Expected: All PASS (these use `func_call` and `add_expr` from Tasks 1-2).
If any fail, extend grammar rules as needed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pycca.py
git commit -m "test(grammar): time built-ins and arithmetic parse tests"
```

---

## Task 9: Set Operations

Verify set operation method calls (`union`, `intersection`, `difference`)
parse correctly. These should work via the `method_call` rules from Task 4.

**Files:**
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write tests**

```python
# ---------------------------------------------------------------------------
# Set operations
# ---------------------------------------------------------------------------

def test_set_union():
    """Set<Floor> all = set_a.union(set_b);"""
    STATEMENT_PARSER.parse("Set<Floor> all = set_a.union(set_b);")


def test_set_intersection():
    """Set<Floor> common = set_a.intersection(set_b);"""
    STATEMENT_PARSER.parse("Set<Floor> common = set_a.intersection(set_b);")


def test_set_difference():
    """Set<Floor> diff = set_a.difference(set_b);"""
    STATEMENT_PARSER.parse("Set<Floor> diff = set_a.difference(set_b);")


def test_set_contains():
    """if (my_set.contains(item)) { ... }"""
    STATEMENT_PARSER.parse("if (my_set.contains(item)) { self.x = 1; }")


def test_set_add():
    """my_set.add(item);"""
    STATEMENT_PARSER.parse("my_set.add(item);")


def test_set_remove():
    """my_set.remove(item);"""
    STATEMENT_PARSER.parse("my_set.remove(item);")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_pycca.py -k "set_" -v`
Expected: All PASS (these are standard `method_call` or `method_call_stmt`
from Task 4).

- [ ] **Step 3: Commit**

```bash
git add tests/test_pycca.py
git commit -m "test(grammar): set operation parse tests"
```

---

## Task 10: Integration — Full Arriving Action

Write a single integration test that parses a realistic multi-statement
action block using the new syntax. This validates that all the grammar
pieces compose correctly.

**Files:**
- Modify: `tests/test_pycca.py`

- [ ] **Step 1: Write integration test**

```python
# ---------------------------------------------------------------------------
# Integration: full action block with new syntax
# ---------------------------------------------------------------------------

def test_arriving_action_new_syntax():
    """Parse a realistic Arriving entry action using new list/lambda syntax."""
    action = """
    Direction prev_direction = self.direction;
    self.direction = None;
    FloorNumber my_floor = self.current_floor;
    UniqueID my_id = self.elevator_id;

    Set<DestFloorButton> buttons = select many related by self->R4;
    generate Floor_served(floor_num: my_floor) to buttons;

    Set<DestFloorButton> lit_btns = select many from instances of DestFloorButton
        where [my_id, my_floor] |btn: DestFloorButton| -> Boolean {
            return btn.r4_elevator_id == my_id
                and btn.curr_state == Lit
                and btn.r5_floor_num != my_floor;
        };

    if (lit_btns.is_empty()) {
        self.next_stop_floor = my_floor;
        generate Arrived to self;
        return;
    }

    Fn(DestFloorButton, DestFloorButton) -> Boolean floor_asc =
        [] |a: DestFloorButton, b: DestFloorButton| -> Boolean {
            return a.r5_floor_num < b.r5_floor_num;
        };
    List<DestFloorButton> sorted_btns = lit_btns.sort(floor_asc);
    Optional<DestFloorButton> first_btn = sorted_btns.peek_front();
    Optional<DestFloorButton> last_btn = sorted_btns.peek_back();

    if (prev_direction == Down and first_btn.value().r5_floor_num < my_floor) {
        Set<DestFloorButton> below = lit_btns.filter(
            [my_floor] |b: DestFloorButton| -> Boolean {
                return b.r5_floor_num < my_floor;
            });
        List<DestFloorButton> below_sorted = below.sort(
            [] |a: DestFloorButton, b: DestFloorButton| -> Boolean {
                return a.r5_floor_num > b.r5_floor_num;
            });
        self.next_stop_floor = below_sorted.peek_front().value().r5_floor_num;
    } else {
        self.next_stop_floor = first_btn.value().r5_floor_num;
    }

    generate Arrived to self;
    """
    STATEMENT_PARSER.parse(action)
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_pycca.py::test_arriving_action_new_syntax -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/test_pycca.py tests/test_pycca_grammar.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_pycca.py
git commit -m "test(grammar): integration test for full Arriving action with new syntax"
```

---

## Task 11: Verify Legacy Tests and Clean Up

Ensure all legacy tests in both test files still pass. Update docstrings
in `grammar.py` to reflect the new grammar status.

**Files:**
- Modify: `pycca/grammar.py:1-21` (module docstring)
- Modify: `tests/test_pycca_grammar.py` (verify, no changes expected)

- [ ] **Step 1: Run full suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS (including non-grammar tests)

- [ ] **Step 2: Update grammar.py docstring**

Update the module docstring at `pycca/grammar.py:1-21` to reflect
all the grammar extensions made in this plan.

- [ ] **Step 3: Run final verification**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add pycca/grammar.py
git commit -m "docs(grammar): update module docstring for list/time/lambda extensions"
```

---

## Summary

| Task | What it adds | Tests |
|------|-------------|-------|
| 1 | Typed var decls, var assignment, arithmetic (precedence tower) | 4 |
| 2 | Container types `List<T>`, `Set<T>`, `Optional<T>`, `Fn` | 4 |
| 3 | Lambda expressions with captures | 4 |
| 4 | Method calls, `.size()`, `.filter()`, `.find()`, chained access (recursive) | 16 |
| 5 | For-each loop | 2 |
| 6 | Select with lambda where, typed returns, chained traversal | 7 |
| 7 | Delayed generate, cancel | 4 |
| 8 | Time built-ins (verify) | 8 |
| 9 | Set operations (verify) | 6 |
| 10 | Integration: full Arriving action | 1 |
| 11 | Legacy verification, docstring cleanup | 0 |
| **Total** | | **56 new tests** |
