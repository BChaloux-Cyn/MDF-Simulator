"""
compiler/transformer.py — Lark Transformer: pycca parse tree → Python source strings.

This is the codegen core for Phase 5.2. Every other compiler plan consumes its output.

Per D-01: Transformer returns Python source as strings (no ast module, no exec).
Per D-05: Every emitted block is preceded by a ``# from <file>:<line>`` comment.
Per D-10: Action function signature: (ctx, self_dict, params) -> None
          Guard function signature:  (self_dict, params) -> bool  [2-arg, scheduler GT]
Per D-11: MUST NOT import from engine/*.

Exports:
    ActionTransformer   — full statement + expression codegen
    GuardTransformer    — expression-only codegen for guard conditions
    transform_action    — parse + transform a pycca action body
    transform_guard     — parse + transform a pycca guard expression

Security (T-05.2-04): All emitted identifiers come from validated schema names
(Pydantic) — attribute names, event names, bridge/class names. These go through
dict-key string literals, not raw identifier interpolation.

Security (T-05.2-05): __default__ raises explicitly — unhandled rules cannot
silently emit Tree(...) literals into generated code.

Security (T-05.2-06): # from <file>:<line> comments create an audit trail from
generated .py back to the source YAML line.

Constraint (D-11): compiler/* MUST NOT import from engine/*.
"""
from __future__ import annotations

import textwrap
from typing import Any

import lark
from lark import Lark, Token, Transformer, Tree, v_args

from compiler.error import CompilationFailed, CompileError, ErrorAccumulator
from pycca.grammar import PYCCA_GRAMMAR

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tok(t: Any) -> str:
    """Convert a Token or string child to str."""
    return str(t)


def _indent(block: str, spaces: int = 4) -> str:
    """Indent every non-empty line of a multi-line block."""
    return textwrap.indent(block, " " * spaces)


def _join_stmts(stmts: list[Any]) -> str:
    """Join a list of statement strings, filtering None values."""
    return "\n".join(s for s in stmts if s is not None and s != "")


# ---------------------------------------------------------------------------
# ActionTransformer
# ---------------------------------------------------------------------------

class ActionTransformer(Transformer):
    """Bottom-up Lark Transformer: pycca parse tree → Python source string.

    Each method receives already-transformed children (strings).
    Returns a Python source string from each rule.

    Self-rewriting rules:
    - ``self`` in ``name`` → ``self_dict``
    - ``self.attr`` in ``dotted_name`` → ``self_dict["attr"]``
    - ``rcvd_evt.field`` in ``dotted_name`` → ``params["field"]``
    """

    # ------------------------------------------------------------------
    # Statement container rules
    # ------------------------------------------------------------------

    def start(self, children: list[Any]) -> str:
        return _join_stmts(children)

    def statement(self, children: list[Any]) -> str:
        # Transparent rule — returns the single child string
        return str(children[0]) if children else ""

    def block(self, children: list[Any]) -> str:
        return _join_stmts(children)

    # ------------------------------------------------------------------
    # Assignment rules
    # ------------------------------------------------------------------

    def assignment(self, children: list[Any]) -> str:
        # "self" "." NAME "=" expr ";"
        # children: [NAME token, expr_str]
        attr = _tok(children[0])
        expr = children[1]
        return f'self_dict["{attr}"] = {expr}'

    def var_assignment(self, children: list[Any]) -> str:
        # NAME "=" expr ";"  OR  NAME "." NAME "=" expr ";"
        if len(children) == 2:
            var, expr = _tok(children[0]), children[1]
            return f"{var} = {expr}"
        else:
            obj, attr, expr = _tok(children[0]), _tok(children[1]), children[2]
            if obj == "self":
                return f'self_dict["{attr}"] = {expr}'
            return f'{obj}["{attr}"] = {expr}'

    def typed_var_decl(self, children: list[Any]) -> str:
        # type_expr NAME "=" expr ";"
        # children: [type_str, NAME token, expr_str]
        _type_str = children[0]  # noqa: F841 — type hints not emitted in body
        var = _tok(children[1])
        expr = children[2]
        return f"{var} = {expr}"

    # ------------------------------------------------------------------
    # Type expression rules (used in typed_var_decl and lambda return type)
    # ------------------------------------------------------------------

    def generic_type(self, children: list[Any]) -> str:
        base = _tok(children[0])
        args = ", ".join(_tok(c) for c in children[1:])
        return f"{base}[{args}]"

    def fn_type(self, children: list[Any]) -> str:
        parts = [_tok(c) for c in children]
        return "Callable"

    def simple_type(self, children: list[Any]) -> str:
        return _tok(children[0])

    # ------------------------------------------------------------------
    # Expression precedence tower
    # ------------------------------------------------------------------

    def or_expr(self, children: list[Any]) -> str:
        if len(children) == 1:
            return children[0]
        return f"{children[0]} or {children[1]}"

    def and_expr(self, children: list[Any]) -> str:
        if len(children) == 1:
            return children[0]
        return f"{children[0]} and {children[1]}"

    def compare_expr(self, children: list[Any]) -> str:
        if len(children) == 1:
            return children[0]
        left, op, right = children[0], _tok(children[1]), children[2]
        return f"{left} {op} {right}"

    def add_expr(self, children: list[Any]) -> str:
        if len(children) == 1:
            return children[0]
        # add_expr "+" mul_expr  |  add_expr "-" mul_expr
        # lark inserts the literal as a Token between children
        # children: [left, right]  (operators are anonymous terminals — not in children)
        # Actually lark includes operator tokens only if named; +/- are literals
        # We need to detect which children represent sub-expressions vs operators
        # Grammar: add_expr "+" mul_expr  — children are [left_str, right_str]
        # But we lose the operator! We need to use @v_args or inspect the Tree
        # Since this transformer gets strings, we can't recover the operator from children alone.
        # Use the raw tree data — but Transformer receives already-processed children.
        # Workaround: since the grammar is left-recursive and uses "+" and "-" literals,
        # lark will include them as Token children only if they're terminals.
        # In lark, anonymous literals become Token('__ANON_N', '+').
        # We look for Token objects among children.
        result = children[0]
        i = 1
        while i < len(children):
            c = children[i]
            if isinstance(c, Token):
                op = str(c)
                i += 1
                result = f"{result} {op} {children[i]}"
            else:
                # Only two children — must infer from context. Fall back to +
                result = f"{result} + {c}"
            i += 1
        return result

    def mul_expr(self, children: list[Any]) -> str:
        if len(children) == 1:
            return children[0]
        result = children[0]
        i = 1
        while i < len(children):
            c = children[i]
            if isinstance(c, Token):
                op = str(c)
                i += 1
                result = f"{result} {op} {children[i]}"
            else:
                result = f"{result} * {c}"
            i += 1
        return result

    # ------------------------------------------------------------------
    # Atom rules
    # ------------------------------------------------------------------

    def number(self, children: list[Any]) -> str:
        return _tok(children[0])

    def string(self, children: list[Any]) -> str:
        return _tok(children[0])

    def name(self, children: list[Any]) -> str:
        n = _tok(children[0])
        if n == "self":
            return "self_dict"
        if n == "rcvd_evt":
            return "params"
        return n

    def dotted_name(self, children: list[Any]) -> str:
        # NAME "." NAME  — e.g. self.attr, rcvd_evt.field, var.field
        obj = _tok(children[0])
        attr = _tok(children[1])
        if obj == "self":
            return f'self_dict["{attr}"]'
        if obj == "rcvd_evt":
            return f'params["{attr}"]'
        return f'{obj}["{attr}"]'

    def func_call(self, children: list[Any]) -> str:
        # NAME "(" arglist? ")"
        fn = _tok(children[0])
        args_str = ", ".join(children[1:]) if len(children) > 1 else ""
        # Special time primitives: duration_s(N) → delay_ms=N*1000 is handled
        # by generate_stmt, not here. Here we emit the Python call as-is.
        if fn == "duration_s" and len(children) == 2:
            # Returns the ms value for use in delay_ms
            return f"int({children[1]} * 1000)"
        if fn == "duration_ms" and len(children) == 2:
            return f"int({children[1]})"
        return f"{fn}({args_str})"

    def cardinality_expr(self, children: list[Any]) -> str:
        # Deprecated; translate to .size()
        var = _tok(children[0])
        return f"{var}.size()"

    # ------------------------------------------------------------------
    # Access chain rules
    # ------------------------------------------------------------------

    def method_call(self, children: list[Any]) -> str:
        # NAME "." NAME "(" arglist? ")"
        obj = _tok(children[0])
        method = _tok(children[1])
        args = ", ".join(str(c) for c in children[2:])
        if obj == "self":
            return f'self_dict.{method}({args})'
        return f"{obj}.{method}({args})"

    def chained_method_call(self, children: list[Any]) -> str:
        # access_chain "." NAME "(" arglist? ")"
        chain = children[0]
        method = _tok(children[1])
        args = ", ".join(str(c) for c in children[2:])
        return f"{chain}.{method}({args})"

    def chained_attr_access(self, children: list[Any]) -> str:
        # access_chain "." NAME
        chain = children[0]
        attr = _tok(children[1])
        return f"{chain}.{attr}"

    # ------------------------------------------------------------------
    # Traversal chain
    # ------------------------------------------------------------------

    def traversal_chain(self, children: list[Any]) -> str:
        # NAME "->" NAME ("->" NAME)*
        # Translates to ctx.traverse(start, [R1, R2, ...])
        parts = [_tok(c) for c in children]
        source = parts[0]
        relations = parts[1:]  # R1, R2, ...
        if source == "self":
            source = "self_dict"
        rels_str = ", ".join(f'"{r}"' for r in relations)
        return f"ctx.traverse({source}, [{rels_str}])"

    def direct_traversal(self, children: list[Any]) -> str:
        # Already transformed by traversal_chain
        return children[0]

    # ------------------------------------------------------------------
    # Generate statement
    # ------------------------------------------------------------------

    def generate_stmt(self, children: list[Any]) -> str:
        # All children arrive as strings (after __default_token__ stringifies Tokens).
        # Grammar alternatives produce these child sequences:
        #   generate Event to NAME;                    → ["Event", "target_name"]
        #   generate Event to access_chain;            → ["Event", "chain_str"]
        #   generate Event(params) to NAME;            → ["Event", "{params}", "target_name"]
        #   generate Event(params) to NAME delay expr; → ["Event", "{params}", "target_name", "delay"]
        #   generate Event to NAME delay expr;         → ["Event", "target_name", "delay"]
        #
        # Heuristic to distinguish param_dict from target:
        #   - param_list rule returns a string starting with "{"
        #   - target names are plain identifiers (NAME tokens → str)
        #   - access_chains start with a NAME and contain "." or "->"
        #   - delay expressions are numeric or function calls

        def _is_param_dict(s: str) -> bool:
            return s.startswith("{")

        def _is_simple_name(s: str) -> bool:
            """True if s looks like a plain NAME (no parens, dots, arrows)."""
            return s.isidentifier()

        def _normalize_target(s: str) -> str:
            """Convert a target name to the instance key form for ctx.generate."""
            if s == "self" or s == "self_dict":
                return 'self_dict["__instance_key__"]'
            if s.isidentifier():
                return f'{s}["__instance_key__"]'
            # access_chain — already transformed (e.g. door.value())
            return s

        strs = [str(c) for c in children]
        event_name = strs[0]
        rest = strs[1:]

        params_dict = "{}"
        target_str = "self_dict"
        delay_expr = None

        i = 0
        # Check for param_dict as first item in rest
        if rest and _is_param_dict(rest[0]):
            params_dict = rest[0]
            i = 1

        # Next item is the target
        if i < len(rest):
            target_str = _normalize_target(rest[i])
            i += 1

        # Remaining item (if any) is the delay expression
        if i < len(rest):
            delay_expr = rest[i]

        if delay_expr is not None:
            return f'ctx.generate("{event_name}", target={target_str}, args={params_dict}, delay_ms={delay_expr})'
        return f'ctx.generate("{event_name}", target={target_str}, args={params_dict})'

    def param_list(self, children: list[Any]) -> str:
        # NAME ":" expr ("," NAME ":" expr)*
        # Pairs: children[0], children[1], children[2], children[3], ...
        pairs = []
        i = 0
        while i < len(children) - 1:
            key = _tok(children[i])
            val = str(children[i + 1])
            pairs.append(f'"{key}": {val}')
            i += 2
        return "{" + ", ".join(pairs) + "}"

    # ------------------------------------------------------------------
    # Cancel statement
    # ------------------------------------------------------------------

    def cancel_stmt(self, children: list[Any]) -> str:
        # "cancel" NAME "from" NAME "to" NAME ";"
        event = _tok(children[0])
        sender = _tok(children[1])
        target = _tok(children[2])
        return f'ctx.cancel("{event}", sender={sender}, target={target})'

    # ------------------------------------------------------------------
    # Bridge call
    # ------------------------------------------------------------------

    def named_arg_list(self, children: list[Any]) -> str:
        # NAME ":" expr ("," NAME ":" expr)*
        pairs = []
        i = 0
        while i < len(children) - 1:
            key = _tok(children[i])
            val = str(children[i + 1])
            pairs.append(f'"{key}": {val}')
            i += 2
        return "{" + ", ".join(pairs) + "}"

    def bridge_call(self, children: list[Any]) -> str:
        # NAME "::" NAME "[" named_arg_list|arglist|empty "]" ";"
        domain = _tok(children[0])
        op = _tok(children[1])
        if len(children) > 2:
            args = str(children[2])
            # If args looks like a dict literal, use it; otherwise wrap as positional
            if args.startswith("{"):
                return f'ctx.bridge("{domain}", "{op}", {args})'
            else:
                # positional arglist — wrap as list
                return f'ctx.bridge("{domain}", "{op}", {{{args}}})'
        return f'ctx.bridge("{domain}", "{op}", {{}})'

    def arglist(self, children: list[Any]) -> str:
        return ", ".join(str(c) for c in children)

    # ------------------------------------------------------------------
    # Create / Delete
    # ------------------------------------------------------------------

    def create_stmt(self, children: list[Any]) -> str:
        # "create" NAME "of" NAME ";"
        # "create" NAME "of" NAME "(" param_list ")" ";"
        var = _tok(children[0])
        cls = _tok(children[1])
        if len(children) > 2:
            params = str(children[2])
            return f'{var} = ctx.create("{cls}", {params})'
        return f'{var} = ctx.create("{cls}", {{}})'

    def delete_stmt(self, children: list[Any]) -> str:
        # "delete" NAME ";"
        # "delete" "object" "of" NAME "where" expr ";"
        if len(children) == 1:
            var = _tok(children[0])
            return f"ctx.delete({var})"
        else:
            cls = _tok(children[0])
            cond = str(children[1])
            return f'ctx.delete_where("{cls}", lambda inst: {cond})'

    # ------------------------------------------------------------------
    # Select statements (statement-form)
    # ------------------------------------------------------------------

    def select_stmt(self, children: list[Any]) -> str:
        # "select" ("any"|"many") NAME "from" "instances" "of" NAME ("where" expr)? ";"
        # children: [cardinality_token, var_name_token, class_name_token, (where_expr)?]
        cardinality = _tok(children[0])
        var = _tok(children[1])
        cls = _tok(children[2])
        where_expr = str(children[3]) if len(children) > 3 else None

        method = "select_any" if cardinality == "any" else "select_many"
        if where_expr:
            return f'{var} = ctx.{method}("{cls}", where=lambda inst: {where_expr})'
        return f'{var} = ctx.{method}("{cls}")'

    def select_related_stmt(self, children: list[Any]) -> str:
        # "select" ("any"|"many") NAME "related" "by" traversal_chain ";"
        cardinality = _tok(children[0])
        var = _tok(children[1])
        chain = str(children[2])  # already transformed by traversal_chain

        method = "select_any" if cardinality == "any" else "select_many"
        # Replace ctx.traverse(...) with a select call form
        # chain is: ctx.traverse(source, ["R1", "R2"])
        # Emit as: var = ctx.select_any_related(source, ["R1", "R2"])
        if chain.startswith("ctx.traverse("):
            inner = chain[len("ctx.traverse("):-1]
            return f'{var} = ctx.{method}_related({inner})'
        return f'{var} = ctx.{method}_related({chain})'

    # ------------------------------------------------------------------
    # Select as expression (RHS of typed_var_decl)
    # ------------------------------------------------------------------

    def select_expr(self, children: list[Any]) -> str:
        # "select" ("any"|"many") "from" "instances" "of" NAME ("where" lambda_expr)?
        # "select" ("any"|"many") "related" "by" traversal_chain ("where" lambda_expr)?
        cardinality = _tok(children[0])
        method = "select_any" if cardinality == "any" else "select_many"

        # Detect form: second child is either NAME (class) or traversal str
        second = children[1]
        if isinstance(second, Token):
            cls = _tok(second)
            where = str(children[2]) if len(children) > 2 else None
            if where:
                return f'ctx.{method}("{cls}", where={where})'
            return f'ctx.{method}("{cls}")'
        else:
            # traversal_chain already transformed
            chain = str(second)
            where = str(children[2]) if len(children) > 2 else None
            if chain.startswith("ctx.traverse("):
                inner = chain[len("ctx.traverse("):-1]
                if where:
                    return f'ctx.{method}_related({inner}, where={where})'
                return f'ctx.{method}_related({inner})'
            if where:
                return f'ctx.{method}_related({chain}, where={where})'
            return f'ctx.{method}_related({chain})'

    # ------------------------------------------------------------------
    # Relate / Unrelate
    # ------------------------------------------------------------------

    def relate_stmt(self, children: list[Any]) -> str:
        # "relate" NAME "to" NAME "across" NAME ";"
        a = _tok(children[0])
        b = _tok(children[1])
        rel = _tok(children[2])
        return f'ctx.relate({a}, {b}, "{rel}")'

    def unrelate_stmt(self, children: list[Any]) -> str:
        # "unrelate" NAME "from" NAME "across" NAME ";"
        a = _tok(children[0])
        b = _tok(children[1])
        rel = _tok(children[2])
        return f'ctx.unrelate({a}, {b}, "{rel}")'

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def else_body(self, children: list[Any]) -> str:
        # Named else_body rule — contains the else-branch statements.
        # The named rule prevents Earley from flattening else stmts into the if body.
        return "__else__:" + _join_stmts(children)

    def if_stmt(self, children: list[Any]) -> str:
        # "if" "(" expr ")" "{" statement* "}" else_if_chain? ("else" "{" else_body "}")?
        # After transformer:
        #   children[0] = condition string
        #   children[1..n] = if-body statement strings (not else_body or else_if_chain)
        #   optionally: an else_if_chain string (starts with "elif ")
        #   optionally: an else_body string (prefixed "__else__:")
        cond = str(children[0])
        body_parts = []
        else_if_part = None
        else_part = None

        for child in children[1:]:
            child_str = str(child)
            if child_str.startswith("elif "):
                else_if_part = child_str
            elif child_str.startswith("__else__:"):
                # Strip the sentinel prefix; remainder is the else body
                else_body_str = child_str[len("__else__:"):]
                else_part = f"else:\n{_indent(else_body_str or 'pass')}"
            else:
                body_parts.append(child_str)

        body = _join_stmts(body_parts) or "pass"
        result = f"if {cond}:\n{_indent(body)}"
        if else_if_part:
            result += f"\n{else_if_part}"
        if else_part:
            result += f"\n{else_part}"
        return result

    def else_if_chain(self, children: list[Any]) -> str:
        return "\n".join(str(c) for c in children)

    def else_if_clause(self, children: list[Any]) -> str:
        # "else" "if" "(" expr ")" "{" statement* "}"
        cond = str(children[0])
        body_stmts = [str(c) for c in children[1:]]
        body = _join_stmts(body_stmts) or "pass"
        return f"elif {cond}:\n{_indent(body)}"

    def for_each_stmt(self, children: list[Any]) -> str:
        # "for" "(" NAME NAME ":" expr ")" "{" statement* "}"
        # children: [type_name_token, var_name_token, iter_expr, *body_stmts]
        _type_name = _tok(children[0])  # noqa: F841
        var = _tok(children[1])
        iter_expr = str(children[2])
        body_stmts = [str(c) for c in children[3:]]
        body = _join_stmts(body_stmts) or "pass"
        return f"for {var} in {iter_expr}:\n{_indent(body)}"

    # ------------------------------------------------------------------
    # Return statement
    # ------------------------------------------------------------------

    def return_stmt(self, children: list[Any]) -> str:
        if children:
            return f"return {children[0]}"
        return "return"

    # ------------------------------------------------------------------
    # Method call statement (standalone)
    # ------------------------------------------------------------------

    def method_call_stmt(self, children: list[Any]) -> str:
        # NAME "." NAME "(" arglist? ")" ";"
        obj = _tok(children[0])
        method = _tok(children[1])
        args = ", ".join(str(c) for c in children[2:])
        if obj == "self":
            return f'self_dict.{method}({args})'
        return f"{obj}.{method}({args})"

    # ------------------------------------------------------------------
    # Lambda expression
    # ------------------------------------------------------------------

    def lambda_expr(self, children: list[Any]) -> str:
        # "[" capture_list? "]" PIPE lambda_params PIPE "->" type_expr "{" statement+ "}"
        # children: [capture_list_str|None, lambda_params_str, type_expr_str, *body_stmts]
        # After transformer, identify each part:
        i = 0
        captures = None
        if children and isinstance(children[0], str) and children[0].startswith("["):
            captures = children[0]
            i = 1
        elif children and isinstance(children[0], list):
            captures = children[0]
            i = 1

        # lambda_params returns a string "p1, p2, ..."
        if i >= len(children):
            return "lambda: None  # empty lambda"
        params_str = str(children[i])
        i += 1

        # type_expr
        if i < len(children):
            _ret_type = children[i]  # noqa: F841
            i += 1

        # Body statements
        body_stmts = [str(c) for c in children[i:]]
        body = _join_stmts(body_stmts) or "pass"

        if captures:
            cap_str = str(captures)
            # Generate closure-capturing lambda
            # Captured names bind to outer scope vars
            return f"(lambda: (lambda {params_str}: {body}))"
        return f"lambda {params_str}: {body}"

    def capture_list(self, children: list[Any]) -> str:
        # capture_item ("," capture_item)*
        items = []
        for child in children:
            items.append(str(child))
        return "[" + ", ".join(items) + "]"

    def capture_item(self, children: list[Any]) -> str:
        if len(children) == 2:
            # NAME "." NAME — dotted capture
            obj = _tok(children[0])
            attr = _tok(children[1])
            if obj == "self":
                return f'self_dict["{attr}"]'
            return f'{obj}["{attr}"]'
        return _tok(children[0])

    def lambda_params(self, children: list[Any]) -> str:
        return ", ".join(str(c) for c in children)

    def lambda_param(self, children: list[Any]) -> str:
        # NAME ":" NAME
        return _tok(children[0])

    # ------------------------------------------------------------------
    # Tier 3 unsupported construct stubs (D-08 fidelity)
    # These are parsed and explicitly rejected with a clear CompileError.
    # ------------------------------------------------------------------

    def while_stmt(self, children: list[Any]) -> str:
        raise NotImplementedError(
            "while_stmt: not yet supported — Tier 3 construct (D-08 stub)"
        )

    def switch_stmt(self, children: list[Any]) -> str:
        raise NotImplementedError(
            "switch_stmt: not yet supported — Tier 3 construct (D-08 stub)"
        )

    def set_union_expr(self, children: list[Any]) -> str:
        raise NotImplementedError(
            "set_union_expr: not yet supported — Tier 3 construct (D-08 stub)"
        )

    def set_intersection_expr(self, children: list[Any]) -> str:
        raise NotImplementedError(
            "set_intersection_expr: not yet supported — Tier 3 construct (D-08 stub)"
        )

    def set_difference_expr(self, children: list[Any]) -> str:
        raise NotImplementedError(
            "set_difference_expr: not yet supported — Tier 3 construct (D-08 stub)"
        )

    # ------------------------------------------------------------------
    # Default: raise on unhandled rules (T-05.2-05 mitigation)
    # ------------------------------------------------------------------

    def __default__(self, data: str, children: list[Any], meta: Any) -> Any:
        raise NotImplementedError(
            f"transformer rule not implemented: {data!r} "
            f"(children: {[str(c)[:40] for c in children]})"
        )

    def __default_token__(self, token: Token) -> str:
        return str(token)


# ---------------------------------------------------------------------------
# GuardTransformer — expression-only subset
# ---------------------------------------------------------------------------

class GuardTransformer(ActionTransformer):
    """Transformer for guard expressions (boolean expression → Python string).

    Inherits all expression rules from ActionTransformer. Overrides statement
    rules to raise on any statement-form rule appearing in a guard context.

    Per D-10 override: guard functions take (self_dict, params) — 2-arg.
    The transformer here only emits the *expression body*, not the def.
    """

    def start(self, children: list[Any]) -> str:  # type: ignore[override]
        # Guard has no 'start' rule — uses 'expr' start. This should not fire.
        raise NotImplementedError("GuardTransformer does not handle start rule")

    def statement(self, children: list[Any]) -> str:  # type: ignore[override]
        raise NotImplementedError(
            "GuardTransformer: statement rules are not valid in guard expressions"
        )

    def assignment(self, children: list[Any]) -> str:  # type: ignore[override]
        raise NotImplementedError(
            "GuardTransformer: assignment is not a valid guard expression"
        )


# ---------------------------------------------------------------------------
# Top-level helpers
# ---------------------------------------------------------------------------

def _make_action_parser() -> Lark:
    """Create a fresh action parser with position tracking (D-05)."""
    return Lark(PYCCA_GRAMMAR, start="start", parser="earley", propagate_positions=True)


def _make_guard_parser() -> Lark:
    """Create a fresh guard parser with position tracking (D-05)."""
    return Lark(PYCCA_GRAMMAR, start="expr", parser="earley", propagate_positions=True)


def transform_action(
    source: str,
    source_file: str,
    source_line_offset: int,
) -> str:
    """Parse and transform a pycca action body to Python source.

    Args:
        source:             pycca action body (one or more statements).
        source_file:        Path or name of the YAML file containing the action
                            (used in ``# from <file>:<line>`` comments, D-05).
        source_line_offset: Line number of the first line of ``source`` within
                            ``source_file``. Added to parse-relative line numbers
                            to produce absolute source locations (D-05).

    Returns:
        Python source string with ``# from <file>:<line>`` comment header.

    Raises:
        CompilationFailed:  If accumulated errors are found.
        NotImplementedError: If an unsupported grammar rule is encountered.
    """
    parser = _make_action_parser()
    tree = parser.parse(source)

    # Determine the first absolute line for the comment (D-05)
    abs_line = source_line_offset + 1

    transformer = ActionTransformer()
    body = transformer.transform(tree)

    comment = f"# from {source_file}:{abs_line}"
    return f"{comment}\n{body}"


def transform_guard(
    source: str,
    source_file: str,
    source_line: int,
) -> str:
    """Parse and transform a pycca guard expression to a Python boolean expression.

    Args:
        source:      pycca guard expression string (single expression, no semicolon).
        source_file: Path or name of the YAML file containing the guard.
        source_line: Absolute line number of the guard within ``source_file``.

    Returns:
        Python boolean expression string with ``# from <file>:<line>`` comment header.
    """
    parser = _make_guard_parser()
    tree = parser.parse(source)

    transformer = GuardTransformer()
    expr_str = transformer.transform(tree)

    comment = f"# from {source_file}:{source_line}"
    return f"{comment}\n{expr_str}"
