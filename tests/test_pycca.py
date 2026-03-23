"""
tests/test_pycca.py — Unit tests for pycca/grammar.py.

Tests cover all nine grammar gap constructs needed for the elevator model,
plus regression checks for constructs already supported.

TDD: tests were written first (RED) against the original grammar,
then grammar.py was extended to make them pass (GREEN).
"""
import pytest
from lark import UnexpectedInput

from pycca.grammar import GUARD_PARSER, STATEMENT_PARSER


# ---------------------------------------------------------------------------
# Regression tests — must pass before and after grammar extension
# ---------------------------------------------------------------------------


def test_existing_assignment():
    """self.attr = NAME; — basic assignment, already supported."""
    STATEMENT_PARSER.parse("self.direction = Up;")


def test_existing_select_from_instances():
    """select any var from instances of Class where ...; — already supported."""
    STATEMENT_PARSER.parse(
        "select any req from instances of Request where request_id == self.r14_request_id;"
    )


# ---------------------------------------------------------------------------
# Gap 1 — select any var related by self->R<N>  (relationship traversal)
# ---------------------------------------------------------------------------


def test_select_related_by():
    """Gap 1: select any shaft related by self->R11;"""
    STATEMENT_PARSER.parse("select any shaft related by self->R11;")


def test_select_related_by_elev():
    """Gap 1: select any elev related by self->R11;"""
    STATEMENT_PARSER.parse("select any elev related by self->R11;")


# ---------------------------------------------------------------------------
# Gap 2 — generate Event to <variable>  (variable target)
# ---------------------------------------------------------------------------


def test_generate_to_variable():
    """Gap 2: generate Move_up to shaft;"""
    STATEMENT_PARSER.parse("generate Move_up to shaft;")


def test_generate_to_self():
    """Gap 2: generate Open_door to self; (self as target NAME)"""
    STATEMENT_PARSER.parse("generate Open_door to self;")


# ---------------------------------------------------------------------------
# Gap 3 — generate Event(param: expr) to var  (params)
# ---------------------------------------------------------------------------


def test_generate_with_params():
    """Gap 3: generate Floor_reached(floor_num: self.current_floor) to elev;"""
    STATEMENT_PARSER.parse(
        "generate Floor_reached(floor_num: self.current_floor) to elev;"
    )


def test_generate_with_params_var_attr_rhs():
    """Gap 3+9: generate with var.attr on RHS of param value."""
    STATEMENT_PARSER.parse(
        "generate Request_assigned(target_floor: req.destination_floor) to self;"
    )


# ---------------------------------------------------------------------------
# Gap 4 — relate / unrelate
# ---------------------------------------------------------------------------


def test_relate():
    """Gap 4: relate req to self across R2;"""
    STATEMENT_PARSER.parse("relate req to self across R2;")


def test_unrelate():
    """Gap 4: unrelate req from self across R2;"""
    STATEMENT_PARSER.parse("unrelate req from self across R2;")


# ---------------------------------------------------------------------------
# Gap 5 — if (expr) { stmts } else { stmts }  (brace-style if/else)
# ---------------------------------------------------------------------------


def test_if_else():
    """Gap 5: if/else with brace syntax."""
    STATEMENT_PARSER.parse(
        "if (req != empty) { generate Door_closed to req; } else { generate Foo to self; }"
    )


def test_if_no_else():
    """Gap 5: if without else."""
    STATEMENT_PARSER.parse(
        "if (req != empty) { generate Foo to self; }"
    )


# ---------------------------------------------------------------------------
# Gap 6 — delete <var>  (variable form)
# ---------------------------------------------------------------------------


def test_delete_variable():
    """Gap 6: delete req;"""
    STATEMENT_PARSER.parse("delete req;")


# ---------------------------------------------------------------------------
# Gap 7 — create <var> of <Class>(<param>: <expr>, ...)  (create with params)
# ---------------------------------------------------------------------------


def test_create_with_params():
    """Gap 7: create f of Floor(floor_num: 3);"""
    STATEMENT_PARSER.parse("create f of Floor(floor_num: 3);")


def test_create_no_params():
    """Gap 7: create req of Request; (no params)"""
    STATEMENT_PARSER.parse("create req of Request;")


# ---------------------------------------------------------------------------
# Gap 8 — var.attr on RHS of assignment  (dotted name read)
# ---------------------------------------------------------------------------


def test_var_dot_attr_read():
    """Gap 8: self.direction = req.destination_floor;"""
    STATEMENT_PARSER.parse("self.direction = req.destination_floor;")


def test_rcvd_evt_dot_attr_read():
    """Gap 8: self.displayed_floor = rcvd_evt.floor_num;"""
    STATEMENT_PARSER.parse("self.displayed_floor = rcvd_evt.floor_num;")


# ---------------------------------------------------------------------------
# Guard parser tests
# ---------------------------------------------------------------------------


def test_guard_rcvd_evt():
    """GUARD_PARSER: rcvd_evt.floor_num == self.next_stop_floor"""
    GUARD_PARSER.parse("rcvd_evt.floor_num == self.next_stop_floor")


def test_guard_var_dot_attr():
    """GUARD_PARSER: target_floor > current_floor"""
    GUARD_PARSER.parse("target_floor > current_floor")


def test_guard_simple_compare():
    """GUARD_PARSER: self.current_floor == 3"""
    GUARD_PARSER.parse("self.current_floor == 3")


def test_guard_not_empty():
    """GUARD_PARSER: req != empty"""
    GUARD_PARSER.parse("req != empty")


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


# ---------------------------------------------------------------------------
# Lambda expressions
# ---------------------------------------------------------------------------

def test_lambda_no_captures():
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton, DestFloorButton) -> Boolean cmp = '
        '[] |a: DestFloorButton, b: DestFloorButton| -> Boolean { return a.x < b.x; };'
    )

def test_lambda_with_captures():
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton) -> Boolean pred = '
        '[my_floor] |btn: DestFloorButton| -> Boolean { return btn.x > my_floor; };'
    )

def test_lambda_multi_capture():
    STATEMENT_PARSER.parse(
        'Fn(DestFloorButton) -> Boolean pred = '
        '[my_floor, my_id] |btn: DestFloorButton| -> Boolean '
        '{ if (btn.r4 != my_id) { return 0; } return btn.x > my_floor; };'
    )

def test_lambda_empty_captures_single_param():
    STATEMENT_PARSER.parse(
        'Fn(Floor) -> Boolean pred = '
        '[] |f: Floor| -> Boolean { return f.floor_num == 3; };'
    )


# ---------------------------------------------------------------------------
# Method calls on containers
# ---------------------------------------------------------------------------

def test_method_call_size():
    STATEMENT_PARSER.parse("Integer count = lit_btns.size();")

def test_method_call_is_empty():
    STATEMENT_PARSER.parse("if (lit_btns.is_empty()) { generate Idle to self; }")

def test_method_call_has_value():
    STATEMENT_PARSER.parse("if (door.has_value()) { generate Open to door.value(); }")

def test_method_call_value():
    STATEMENT_PARSER.parse("if (door.value().curr_state == Closed) { self.x = 1; }")

def test_method_call_filter_with_lambda():
    STATEMENT_PARSER.parse(
        'Set<DestFloorButton> lit = btns.filter('
        '[] |b: DestFloorButton| -> Boolean { return b.curr_state == Lit; });'
    )

def test_method_call_sort_with_lambda():
    STATEMENT_PARSER.parse(
        'btns.sort([] |a: DestFloorButton, b: DestFloorButton| -> Boolean '
        '{ return a.floor_num < b.floor_num; });'
    )

def test_method_call_push_back():
    STATEMENT_PARSER.parse("floors.push_back(3);")

def test_method_call_pop_front():
    STATEMENT_PARSER.parse("Optional<FloorNumber> next = floors.pop_front();")

def test_method_call_map():
    STATEMENT_PARSER.parse(
        'List<FloorNumber> floors = btns.map('
        '[] |b: DestFloorButton| -> FloorNumber { return b.r5_floor_num; });'
    )

def test_method_call_find_with_lambda():
    STATEMENT_PARSER.parse(
        'Optional<DestFloorButton> btn = btns.find('
        '[target] |b: DestFloorButton| -> Boolean { return b.r5_floor_num == target; });'
    )

def test_method_call_get():
    STATEMENT_PARSER.parse("Optional<FloorNumber> f = floors.get(0);")

def test_method_call_push_front():
    STATEMENT_PARSER.parse("floors.push_front(1);")

def test_method_call_insert():
    STATEMENT_PARSER.parse("floors.insert(0, 3);")

def test_method_call_contains():
    STATEMENT_PARSER.parse("if (my_list.contains(item)) { self.x = 1; }")

def test_chained_method_double():
    STATEMENT_PARSER.parse(
        "self.x = sorted_btns.peek_front().value().r5_floor_num;"
    )


# ---------------------------------------------------------------------------
# For-each loop
# ---------------------------------------------------------------------------

def test_for_each_simple():
    STATEMENT_PARSER.parse(
        "for (DestFloorButton btn : my_list) { generate Foo to btn; }"
    )

def test_for_each_with_method_call():
    STATEMENT_PARSER.parse(
        "for (Floor f : floors) { self.x = f.floor_num; }"
    )
