"""
pycca/grammar.py — MDF action language grammar (lark).

Exports:
  PYCCA_GRAMMAR  — raw grammar string (importable by Phase 5 transformer)
  GUARD_PARSER   — pre-compiled Earley parser, start="expr" (guard expressions)
  STATEMENT_PARSER — pre-compiled LALR parser, start="start" (full action blocks)

Grammar covers all seven MDF action language constructs defined in CONTEXT.md.
NOT derived from upstream pycca compiler (which uses plain C + macros).
This is an MDF-project-specific DSL.
"""
from lark import Lark

PYCCA_GRAMMAR = r"""
    start: statement+

    statement: assignment
             | generate_stmt
             | bridge_call
             | create_stmt
             | delete_stmt
             | select_stmt
             | if_stmt

    assignment: "self" "." NAME "=" expr ";"
    generate_stmt: "generate" NAME "to" ("SELF" | "CLASS") ";"
    bridge_call: NAME "::" NAME "[" arglist? "]" ";"
    create_stmt: "create" "object" "of" NAME ";"
    delete_stmt: "delete" "object" "of" NAME "where" expr ";"
    select_stmt: "select" ("any"|"many") NAME "from" "instances" "of" NAME ("where" expr)? ";"
    if_stmt: "if" expr ";" statement* "end" "if" ";"

    ?expr: simple_compare
         | and_expr
         | or_expr
         | cardinality_expr
         | atom

    simple_compare: atom OP atom
    and_expr: expr "and" expr
    or_expr: expr "or" expr
    cardinality_expr: "cardinality" NAME
    atom: NUMBER -> number
        | ESCAPED_STRING -> string
        | NAME -> name
        | "(" expr ")"

    arglist: expr ("," expr)*

    OP: /[<>]=?|==|!=/
    NUMBER: /[0-9]+(\.[0-9]+)?/
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/

    %import common.ESCAPED_STRING
    %ignore /\s+/
    %ignore /\/\/[^\n]*/
"""

GUARD_PARSER = Lark(PYCCA_GRAMMAR, start="expr", parser="earley")
try:
    STATEMENT_PARSER = Lark(PYCCA_GRAMMAR, start="start", parser="lalr")
except Exception:
    # Fall back to Earley if LALR has grammar conflicts
    STATEMENT_PARSER = Lark(PYCCA_GRAMMAR, start="start", parser="earley")
