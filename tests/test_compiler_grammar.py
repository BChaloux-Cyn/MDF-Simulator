"""
tests/test_compiler_grammar.py — Regression tests for the 4 grammar gaps fixed in Plan 05.2-01.

These tests verify that the patched pycca/grammar.py correctly parses elevator-model
constructs that were blocked before the gap fixes:

  Gap 1: Lambda return type cannot be generic (-> Set<T> failed; -> NAME only)
  Gap 2: Capture list cannot contain attribute access ([self.attr] failed)
  Gap 3: select_related_stmt only handles single-hop (multi-hop ->R1->R2 failed)
  Gap 4: Bridge call uses named params (key: val) but grammar expected positional
"""
import pytest
from lark import LarkError


@pytest.fixture
def stmt_parser():
    from pycca.grammar import STATEMENT_PARSER
    return STATEMENT_PARSER


@pytest.fixture
def guard_parser():
    from pycca.grammar import GUARD_PARSER
    return guard_parser


# ---------------------------------------------------------------------------
# Gap 1: Lambda return type = generic type (Set<T>, List<T>, etc.)
# ---------------------------------------------------------------------------

def test_gap1_lambda_generic_return_type(stmt_parser):
    """flat_map lambda with -> Set<FloorCallButton> return type should parse."""
    source = "List<FloorCallButton> result = x.flat_map([] |sf: ShaftFloor| -> Set<FloorCallButton> { return select many from instances of FloorCallButton; });"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap1_lambda_simple_return_type_still_works(stmt_parser):
    """Existing simple return type (-> Boolean) must still parse after fix."""
    source = "Boolean result = x.filter([] |b: FloorCallButton| -> Boolean { return b.lit == True; });"
    tree = stmt_parser.parse(source)
    assert tree is not None


# ---------------------------------------------------------------------------
# Gap 2: Capture list with dotted-name item ([self.current_floor])
# ---------------------------------------------------------------------------

def test_gap2_capture_list_dotted_name(stmt_parser):
    """[self.current_floor] capture in a filter lambda should parse."""
    source = "Set<FloorCallButton> calls = collection.filter([self.current_floor] |btn: FloorCallButton| -> Boolean { return btn.floor_num == self.current_floor; });"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap2_capture_list_plain_name_still_works(stmt_parser):
    """Plain capture list [var] must still work after fix."""
    source = "Set<Item> result = col.filter([my_floor] |x: Item| -> Boolean { return x.n == my_floor; });"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap2_capture_list_mixed(stmt_parser):
    """Mixed capture list [self.attr, plain_var] should parse."""
    source = "Set<Item> r = col.filter([self.x, other] |i: Item| -> Boolean { return i.v == self.x; });"
    tree = stmt_parser.parse(source)
    assert tree is not None


# ---------------------------------------------------------------------------
# Gap 3: select_related_stmt with multi-hop traversal chain
# ---------------------------------------------------------------------------

def test_gap3_select_related_multi_hop(stmt_parser):
    """select many related by self->R1->R2 (two hops) should parse."""
    source = "select many stops related by self->R1->R2;"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap3_select_related_three_hops(stmt_parser):
    """select many related by self->R1->R2->R3 (three hops) should parse."""
    source = "select many result related by self->R1->R2->R3;"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap3_select_related_single_hop_still_works(stmt_parser):
    """Original single-hop select related by still works after fix."""
    source = "select any e related by self->R1;"
    tree = stmt_parser.parse(source)
    assert tree is not None


# ---------------------------------------------------------------------------
# Gap 4: Bridge call with named arguments (key: val)
# ---------------------------------------------------------------------------

def test_gap4_bridge_named_args(stmt_parser):
    """Building::IsTopFloor[floor_num: self.current_floor] should parse."""
    source = "Building::IsTopFloor[floor_num: self.current_floor];"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap4_bridge_named_args_multiple(stmt_parser):
    """Bridge call with multiple named args should parse."""
    source = "Transport::ElevatorDetected[sensor_id: self.sensor_id, floor: self.current_floor];"
    tree = stmt_parser.parse(source)
    assert tree is not None


def test_gap4_bridge_empty_args_still_works(stmt_parser):
    """Bridge call with empty arg list still works."""
    source = "Building::Notify[];"
    tree = stmt_parser.parse(source)
    assert tree is not None
