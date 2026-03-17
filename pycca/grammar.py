"""
pycca/grammar.py — MDF action language grammar (lark).

Exports:
  PYCCA_GRAMMAR  — raw grammar string (importable by Phase 5 transformer)
  GUARD_PARSER   — pre-compiled Earley parser, start="expr" (guard expressions)
  STATEMENT_PARSER — pre-compiled LALR parser, start="start" (full action blocks)

Grammar covers all MDF action language constructs defined in SYNTAX.md.
NOT derived from upstream pycca compiler (which uses plain C + macros).
This is an MDF-project-specific DSL.

Extensions added in Phase 04.1-04:
  - dotted_name in atom (var.attr, self.attr, rcvd_evt.param)
  - generate to any NAME variable; generate with param_list
  - select_related_stmt (relationship traversal)
  - relate_stmt, unrelate_stmt
  - delete <var> (variable form alongside delete object of ...)
  - create <var> of <Class> and create <var> of <Class>(<params>)
  - if_stmt with brace syntax and optional else clause
"""
from lark import Lark

PYCCA_GRAMMAR = r"""
    start: statement+

    statement: assignment
             | generate_stmt
             | bridge_call
             | create_stmt
             | delete_stmt
             | select_related_stmt
             | select_stmt
             | relate_stmt
             | unrelate_stmt
             | if_stmt

    // --- Assignment ---
    // self.attr = expr;
    assignment: "self" "." NAME "=" expr ";"

    // --- Generate ---
    // generate Event to NAME;
    // generate Event(param: expr, ...) to NAME;
    generate_stmt: "generate" NAME "to" NAME ";"
                 | "generate" NAME "(" param_list ")" "to" NAME ";"

    param_list: NAME ":" expr ("," NAME ":" expr)*

    // --- Bridge call ---
    // Domain::Operation[args];
    bridge_call: NAME "::" NAME "[" arglist? "]" ";"

    // --- Create ---
    // create var of Class;
    // create var of Class(param: expr, ...);
    create_stmt: "create" NAME "of" NAME ";"
               | "create" NAME "of" NAME "(" param_list ")" ";"

    // --- Delete ---
    // delete var;
    // delete object of Class where expr;
    delete_stmt: "delete" NAME ";"
               | "delete" "object" "of" NAME "where" expr ";"

    // --- Select from instances ---
    // select any/many var from instances of Class [where expr];
    select_stmt: "select" ("any"|"many") NAME "from" "instances" "of" NAME ("where" expr)? ";"

    // --- Select related by ---
    // select any/many var related by NAME->NAME;
    select_related_stmt: "select" ("any"|"many") NAME "related" "by" NAME "->" NAME ";"

    // --- Relate / Unrelate ---
    // relate var1 to var2 across RN;
    relate_stmt: "relate" NAME "to" NAME "across" NAME ";"
    // unrelate var1 from var2 across RN;
    unrelate_stmt: "unrelate" NAME "from" NAME "across" NAME ";"

    // --- If / else ---
    // if (expr) { stmts } [else { stmts }]
    if_stmt: "if" "(" expr ")" "{" statement* "}" ("else" "{" statement* "}")?

    // --- Expressions ---
    ?expr: simple_compare
         | and_expr
         | or_expr
         | cardinality_expr
         | atom

    simple_compare: atom OP atom
    and_expr: expr "and" expr
    or_expr: expr "or" expr
    cardinality_expr: "cardinality" NAME

    // atom: dotted_name must appear before plain name to ensure LALR picks the longer match
    atom: NUMBER -> number
        | ESCAPED_STRING -> string
        | NAME "." NAME -> dotted_name
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
