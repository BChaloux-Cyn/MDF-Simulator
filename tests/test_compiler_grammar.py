"""
tests/test_compiler_grammar.py — Grammar gap regression tests (Wave 0, Plan 01).

Verifies that the 4 grammar gaps identified in 05.2-RESEARCH.md are closed:

  Gap 1: Lambda return type cannot be generic (-> Set<T> failed)
  Gap 2: Capture list cannot contain dotted names ([self.attr] failed)
  Gap 3: select_related_stmt only handled single-hop traversal
  Gap 4: Bridge call only accepted positional arglist, not named args

Each test exercises the real grammar via STATEMENT_PARSER or GUARD_PARSER.
All tests are GREEN once pycca/grammar.py is patched (Wave 0 task).

Requirement: MCP-08 (partial) — compiler must parse real elevator model actions.
"""

import pytest
from lark import LarkError


# ---------------------------------------------------------------------------
# Gap 1: Lambda return type = generic type (-> Set<T>)
# ---------------------------------------------------------------------------

def test_gap1_lambda_return_generic_simple():
    """Parser accepts a lambda with a single-param generic return type."""
    from pycca.grammar import STATEMENT_PARSER

    src = (
        "Set<Stop> stops = items.flat_map("
        "[] |sf: Stop| -> Set<Stop> { return sf; });"
    )
    # Must not raise LarkError
    STATEMENT_PARSER.parse(src)


def test_gap1_lambda_return_generic_compound():
    """Parser accepts a lambda with a compound generic return type (Gap 1 — elevator fixture)."""
    from pycca.grammar import STATEMENT_PARSER

    # Derived from Elevator.Arriving entry action in the elevator model
    src = (
        "Set<FloorCallButton> buttons = self.flat_map("
        "[] |sf: Stop| -> Set<FloorCallButton> { return sf.button; });"
    )
    STATEMENT_PARSER.parse(src)


def test_gap1_lambda_return_simple_still_works():
    """Simple (non-generic) lambda return type continues to parse correctly (regression)."""
    from pycca.grammar import STATEMENT_PARSER

    src = "bool ok = items.filter([] |x: Item| -> bool { return x.active; });"
    STATEMENT_PARSER.parse(src)


# ---------------------------------------------------------------------------
# Gap 2: Capture list with dotted names ([self.attr])
# ---------------------------------------------------------------------------

def test_gap2_capture_dotted_self_attr():
    """Parser accepts [self.current_floor] as a capture list item."""
    from pycca.grammar import STATEMENT_PARSER

    # Derived from Elevator.Arriving filter lambda
    src = (
        "Set<FloorCallButton> local_stops = stops.filter("
        "[self.current_floor] |x: Stop| -> bool { return x.floor_num; });"
    )
    STATEMENT_PARSER.parse(src)


def test_gap2_capture_multiple_items():
    """Parser accepts a capture list with both plain name and dotted name."""
    from pycca.grammar import STATEMENT_PARSER

    src = (
        "bool ok = items.filter("
        "[my_var, self.current_floor] |x: Item| -> bool { return x.active; });"
    )
    STATEMENT_PARSER.parse(src)


def test_gap2_capture_plain_name_still_works():
    """Plain-name capture list continues to work after Gap 2 fix (regression)."""
    from pycca.grammar import STATEMENT_PARSER

    src = (
        "bool ok = items.filter("
        "[my_var] |x: Item| -> bool { return x.active; });"
    )
    STATEMENT_PARSER.parse(src)


def test_gap2_empty_capture_still_works():
    """Empty capture list [] continues to work (regression)."""
    from pycca.grammar import STATEMENT_PARSER

    src = "bool ok = items.filter([] |x: Item| -> bool { return x.active; });"
    STATEMENT_PARSER.parse(src)


# ---------------------------------------------------------------------------
# Gap 3: select_related_stmt multi-hop traversal
# ---------------------------------------------------------------------------

def test_gap3_select_related_multi_hop_two():
    """Parser accepts select with two-hop traversal: self->R1->R2."""
    from pycca.grammar import STATEMENT_PARSER

    src = "select many stops related by self->R1->R2;"
    STATEMENT_PARSER.parse(src)


def test_gap3_select_related_multi_hop_three():
    """Parser accepts select with three-hop traversal: self->R1->R2->R3."""
    from pycca.grammar import STATEMENT_PARSER

    src = "select many items related by self->R1->R2->R3;"
    STATEMENT_PARSER.parse(src)


def test_gap3_select_related_single_hop_still_works():
    """Single-hop select_related_stmt still works after Gap 3 fix (regression)."""
    from pycca.grammar import STATEMENT_PARSER

    src = "select any stop related by self->R7;"
    STATEMENT_PARSER.parse(src)


def test_gap3_select_related_named_var():
    """Multi-hop select with a non-self source variable."""
    from pycca.grammar import STATEMENT_PARSER

    src = "select many buttons related by elev->R12->R8;"
    STATEMENT_PARSER.parse(src)


# ---------------------------------------------------------------------------
# Gap 4: Bridge call with named arguments
# ---------------------------------------------------------------------------

def test_gap4_bridge_named_single_arg():
    """Parser accepts a bridge call with a single named argument."""
    from pycca.grammar import STATEMENT_PARSER

    # Derived from Building bridge calls in elevator model
    src = "Building::IsTopFloor[floor_num: self.current_floor];"
    STATEMENT_PARSER.parse(src)


def test_gap4_bridge_named_multiple_args():
    """Parser accepts a bridge call with multiple named arguments."""
    from pycca.grammar import STATEMENT_PARSER

    src = "Transport::ElevatorDetected[elevator_id: self.id, floor: self.current_floor];"
    STATEMENT_PARSER.parse(src)


def test_gap4_bridge_positional_still_works():
    """Positional bridge call args continue to work after Gap 4 fix (regression)."""
    from pycca.grammar import STATEMENT_PARSER

    src = "Timer::start_timer[duration];"
    STATEMENT_PARSER.parse(src)


def test_gap4_bridge_empty_args_still_works():
    """Empty bridge arg list continues to work after Gap 4 fix (regression)."""
    from pycca.grammar import STATEMENT_PARSER

    src = "Building::Ping[];"
    STATEMENT_PARSER.parse(src)


# ---------------------------------------------------------------------------
# Regression: existing grammar constructs must still parse
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("src", [
    "self.x = 42;",
    "generate Open_valve to SELF;",
    "select any stop from instances of Stop where stop.active;",
    "relate var1 to var2 across R5;",
    "unrelate var1 from var2 across R5;",
    "create obj of Stop;",
    "delete obj;",
    "return self.floor_num;",
])
def test_regression_existing_statements(src):
    """Existing grammar statements still parse after all 4 gap fixes."""
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse(src)


@pytest.mark.parametrize("src", [
    "pressure >= 100",
    "x < 5",
    "x > 10",
    "mode == 2",
    "x != 0",
])
def test_regression_guard_expressions(src):
    """Guard expressions (comparison operators) still parse after gap fixes."""
    from pycca.grammar import GUARD_PARSER
    GUARD_PARSER.parse(src)
