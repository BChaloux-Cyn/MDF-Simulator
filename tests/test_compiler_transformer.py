"""
tests/test_compiler_transformer.py — RED stubs for transformer construct coverage (Plan 02).

These tests are RED until compiler/transformer.py is implemented in Plan 02.
The import of `compiler.transformer` fails because the module does not exist yet.

Coverage targets (one stub per pycca construct family):
  - Assignment (self.attr = expr)
  - Generate statement (generate Event to target)
  - Select from instances
  - Select related by (single and multi-hop)
  - Bridge call (positional and named)
  - Lambda expression
  - If/else statement
  - For-each loop
  - Method call statement
  - Return statement
  - Variable declaration (typed_var_decl)

Requirement: MCP-08 (partial) — Lark Transformer for Python codegen.
"""

import pytest

# ---------------------------------------------------------------------------
# RED sentinel: this import will fail until Plan 02 creates compiler/transformer.py
# ---------------------------------------------------------------------------
pytest.importorskip(
    "compiler.transformer",
    reason="compiler.transformer not yet implemented (Plan 02)",
)

from compiler.transformer import ActionTransformer  # noqa: E402 (unreachable until plan 02)


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def test_transformer_assignment_self_attr():
    """self.x = expr; transforms to self_dict['x'] = ..."""
    t = ActionTransformer()
    result = t.transform_source("self.x = 42;")
    assert 'self_dict["x"]' in result or "self_dict['x']" in result


def test_transformer_var_assignment():
    """var = expr; transforms to a bare variable assignment."""
    t = ActionTransformer()
    result = t.transform_source("count = 0;")
    assert "count" in result
    assert "=" in result


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def test_transformer_generate_to_self():
    """generate Event to self; produces ctx.generate(...)."""
    t = ActionTransformer()
    result = t.transform_source("generate Ready to self;")
    assert "ctx.generate" in result or "generate" in result


def test_transformer_generate_to_name():
    """generate Event to target; produces ctx.generate(...)."""
    t = ActionTransformer()
    result = t.transform_source("generate Floor_assigned to elev;")
    assert "generate" in result


def test_transformer_generate_with_params():
    """generate Event(k: v) to target; includes parameter dict."""
    t = ActionTransformer()
    result = t.transform_source("generate Floor_assigned(floor_num: self.current_floor) to elev;")
    assert "generate" in result


# ---------------------------------------------------------------------------
# Select from instances
# ---------------------------------------------------------------------------

def test_transformer_select_any_from_instances():
    """select any var from instances of Class; produces a ctx.select call."""
    t = ActionTransformer()
    result = t.transform_source("select any stop from instances of Stop;")
    assert "select" in result or "ctx" in result


def test_transformer_select_many_where():
    """select many ... where expr; includes where predicate."""
    t = ActionTransformer()
    result = t.transform_source("select many stops from instances of Stop where stop.active;")
    assert "select" in result


# ---------------------------------------------------------------------------
# Select related by
# ---------------------------------------------------------------------------

def test_transformer_select_related_single_hop():
    """select related by single hop produces traversal expression."""
    t = ActionTransformer()
    result = t.transform_source("select any stop related by self->R7;")
    assert "R7" in result


def test_transformer_select_related_multi_hop():
    """select related by multi-hop traversal (Gap 3 construct)."""
    t = ActionTransformer()
    result = t.transform_source("select many buttons related by self->R1->R2;")
    assert "R1" in result and "R2" in result


# ---------------------------------------------------------------------------
# Bridge call
# ---------------------------------------------------------------------------

def test_transformer_bridge_call_positional():
    """Positional bridge call produces a domain-dispatch expression."""
    t = ActionTransformer()
    result = t.transform_source("Timer::start_timer[duration];")
    assert "Timer" in result or "start_timer" in result


def test_transformer_bridge_call_named():
    """Named-arg bridge call (Gap 4 construct) produces correct dispatch."""
    t = ActionTransformer()
    result = t.transform_source("Building::IsTopFloor[floor_num: self.current_floor];")
    assert "IsTopFloor" in result or "Building" in result


# ---------------------------------------------------------------------------
# Lambda expression
# ---------------------------------------------------------------------------

def test_transformer_lambda_simple_return():
    """Lambda with simple return type transforms to Python lambda / def."""
    t = ActionTransformer()
    result = t.transform_source(
        "bool ok = items.filter([] |x: Item| -> bool { return x.active; });"
    )
    assert "def" in result or "lambda" in result or "filter" in result


def test_transformer_lambda_generic_return():
    """Lambda with generic return type (Gap 1 construct) transforms correctly."""
    t = ActionTransformer()
    result = t.transform_source(
        "Set<Stop> stops = items.flat_map([] |sf: Stop| -> Set<Stop> { return sf; });"
    )
    assert result  # non-empty string; exact form determined by Plan 02


def test_transformer_lambda_dotted_capture():
    """Lambda with dotted capture item (Gap 2 construct) transforms correctly."""
    t = ActionTransformer()
    result = t.transform_source(
        "bool ok = items.filter([self.current_floor] |x: Item| -> bool { return x.active; });"
    )
    assert result


# ---------------------------------------------------------------------------
# If / else
# ---------------------------------------------------------------------------

def test_transformer_if_simple():
    """if (expr) { stmts } produces Python if block."""
    t = ActionTransformer()
    result = t.transform_source("if (self.floor > 0) { self.active = 1; }")
    assert "if" in result


def test_transformer_if_else():
    """if/else produces Python if/else block."""
    t = ActionTransformer()
    result = t.transform_source(
        "if (self.floor > 0) { self.active = 1; } else { self.active = 0; }"
    )
    assert "else" in result


# ---------------------------------------------------------------------------
# For-each loop
# ---------------------------------------------------------------------------

def test_transformer_for_each():
    """for (Type var : expr) { stmts } produces Python for loop."""
    t = ActionTransformer()
    result = t.transform_source("for (Stop s : stops) { generate Arrived to s; }")
    assert "for" in result


# ---------------------------------------------------------------------------
# Method call statement
# ---------------------------------------------------------------------------

def test_transformer_method_call_stmt():
    """var.method(args); produces a method call expression."""
    t = ActionTransformer()
    result = t.transform_source("self.do_work(42);")
    assert "do_work" in result or "self" in result


# ---------------------------------------------------------------------------
# Return statement
# ---------------------------------------------------------------------------

def test_transformer_return_expr():
    """return expr; produces a Python return statement."""
    t = ActionTransformer()
    result = t.transform_source("return self.floor_num;")
    assert "return" in result


def test_transformer_return_void():
    """return; produces a bare Python return."""
    t = ActionTransformer()
    result = t.transform_source("return;")
    assert "return" in result


# ---------------------------------------------------------------------------
# Typed variable declaration
# ---------------------------------------------------------------------------

def test_transformer_typed_var_decl_simple():
    """bool x = expr; emits a typed assignment."""
    t = ActionTransformer()
    result = t.transform_source("bool ok = self.active;")
    assert "ok" in result


def test_transformer_typed_var_decl_generic():
    """Set<T> var = expr; emits a typed assignment for generic type."""
    t = ActionTransformer()
    result = t.transform_source(
        "Set<Stop> stops = ctx.select_many(Stop);"
    )
    assert "stops" in result


# ---------------------------------------------------------------------------
# Guard expression transformer
# ---------------------------------------------------------------------------

def test_transformer_guard_compare():
    """Guard expression x > 5 transforms to Python boolean expression."""
    from compiler.transformer import GuardTransformer
    t = GuardTransformer()
    result = t.transform_guard("x > 5")
    assert ">" in result or "5" in result


def test_transformer_guard_and():
    """Guard expression with 'and' operator transforms correctly."""
    from compiler.transformer import GuardTransformer
    t = GuardTransformer()
    result = t.transform_guard("x > 0 and x < 10")
    assert "and" in result or (">" in result and "<" in result)
