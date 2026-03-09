"""
tests/test_pycca_grammar.py — Grammar module tests for pycca.grammar.

All tests are RED until pycca/grammar.py is implemented in 03-02 Task 2.
"""


def test_grammar_module_imports():
    from pycca.grammar import PYCCA_GRAMMAR, GUARD_PARSER, STATEMENT_PARSER  # noqa: F401


def test_guard_simple_compare():
    from pycca.grammar import GUARD_PARSER
    tree = GUARD_PARSER.parse("pressure >= 100")
    assert tree.data == "simple_compare"


def test_guard_inequality_lt():
    from pycca.grammar import GUARD_PARSER
    GUARD_PARSER.parse("x < 5")


def test_guard_inequality_gt():
    from pycca.grammar import GUARD_PARSER
    GUARD_PARSER.parse("x > 10")


def test_guard_equality():
    from pycca.grammar import GUARD_PARSER
    GUARD_PARSER.parse("mode == 2")


def test_statement_assignment():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("self.x = 42;")


def test_statement_generate_self():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("generate Open_valve to SELF;")


def test_statement_generate_class():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("generate Open_valve to CLASS;")


def test_statement_bridge_call():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("Timer::start_timer[duration];")


def test_statement_create():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("create object of Valve;")


def test_statement_delete():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("delete object of Valve where v_id == 1;")


def test_statement_select_any():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("select any v from instances of Valve;")


def test_statement_if():
    from pycca.grammar import STATEMENT_PARSER
    STATEMENT_PARSER.parse("if x > 0; self.y = 1; end if;")
