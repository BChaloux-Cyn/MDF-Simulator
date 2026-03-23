"""
pycca/grammar.py — MDF action language grammar (lark).

Exports:
  PYCCA_GRAMMAR  — raw grammar string (importable by Phase 5 transformer)
  GUARD_PARSER   — pre-compiled Earley parser, start="expr" (guard expressions)
  STATEMENT_PARSER — pre-compiled Earley parser, start="start" (full action blocks)

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

Extensions added in Task 1 (grammar extension plan):
  - typed_var_decl: Type var = expr;
  - var_assignment: var = expr; and var.attr = expr;
  - arithmetic precedence tower: or > and > compare > add > mul > atom
  - Both parsers switched to Earley (NAME NAME ambiguity requires it)
"""
from lark import Lark

PYCCA_GRAMMAR = r"""
    start: statement+

    statement: typed_var_decl
             | assignment
             | var_assignment
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

    // --- Typed variable declaration ---
    // Type var = expr;
    typed_var_decl: NAME NAME "=" expr ";"

    // --- Variable assignment (non-self) ---
    // var = expr;
    // var.attr = expr;
    var_assignment: NAME "=" expr ";"
                 | NAME "." NAME "=" expr ";"

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

    // --- Expressions (precedence tower: lowest to highest) ---
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

    // atom: dotted_name must appear before plain name to ensure longer match
    atom: NUMBER -> number
        | ESCAPED_STRING -> string
        | NAME "." NAME -> dotted_name
        | NAME -> name
        | "(" expr ")"
        | "cardinality" NAME -> cardinality_expr

    arglist: expr ("," expr)*

    OP: /[<>]=?|==|!=/
    NUMBER: /[0-9]+(\.[0-9]+)?/
    NAME: /[a-zA-Z_][a-zA-Z0-9_]*/

    %import common.ESCAPED_STRING
    %ignore /\s+/
    %ignore /\/\/[^\n]*/
"""

GUARD_PARSER = Lark(PYCCA_GRAMMAR, start="expr", parser="earley")
STATEMENT_PARSER = Lark(PYCCA_GRAMMAR, start="start", parser="earley")
