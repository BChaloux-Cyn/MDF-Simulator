"""
pycca/grammar.py — MDF action language grammar (lark).

Exports:
  PYCCA_GRAMMAR  — raw grammar string (importable by Phase 5 transformer)
  GUARD_PARSER   — pre-compiled Earley parser, start="expr" (guard expressions)
  STATEMENT_PARSER — pre-compiled Earley parser, start="start" (full action blocks)

Grammar covers all MDF action language constructs defined in SYNTAX.md.
NOT derived from upstream pycca compiler (which uses plain C + macros).
This is an MDF-project-specific DSL. Both parsers use Earley (the grammar
has inherent ambiguities that LALR cannot resolve).

Supported constructs:
  - Typed variable declarations (type_expr NAME = expr;)
  - Assignments (self.attr, var, var.attr)
  - Arithmetic with precedence tower (or > and > compare > add > mul > atom)
  - Container types: List<T>, Set<T>, Optional<T>, Fn(T,...)->R
  - Lambda expressions with capture lists ([captures] |params| -> R { body })
  - Method calls and recursive chained access (a.b().c().d)
  - For-each loops (for (Type var : expr) { stmts })
  - Select as expression with lambda where clause
  - Chained relationship traversal (self->R1->R2->R3)
  - Generate with delay (generate Event to target delay duration;)
  - Cancel statement (cancel Event from sender to target;)
  - Function calls (now(), duration_s(5), etc.)
  - Return statements
  - All Phase 04.1-04 constructs (relate, unrelate, create, delete, bridge, if/else)
  - Legacy select with bare boolean where (backward compat)
  - Deprecated cardinality keyword (use .size() instead)
"""
from lark import Lark

PYCCA_GRAMMAR = r"""
    start: statement+

    statement: typed_var_decl
             | assignment
             | var_assignment
             | generate_stmt
             | cancel_stmt
             | bridge_call
             | create_stmt
             | delete_stmt
             | select_related_stmt
             | select_stmt
             | relate_stmt
             | unrelate_stmt
             | if_stmt
             | return_stmt
             | method_call_stmt
             | for_each_stmt

    // --- Standalone method call statement ---
    // var.method(args);
    method_call_stmt: NAME "." NAME "(" arglist? ")" ";"

    // --- Return ---
    // return expr;
    // return;
    return_stmt: "return" expr ";"
               | "return" ";"

    // --- Assignment ---
    // self.attr = expr;
    assignment: "self" "." NAME "=" expr ";"

    // --- Type expressions (simple, generic, or function types) ---
    // Name | Name<T> | Name<T,U> | Fn(T,...) -> R
    type_expr: NAME "<" NAME ("," NAME)* ">"  -> generic_type
             | NAME "(" NAME ("," NAME)* ")" "->" NAME  -> fn_type
             | NAME  -> simple_type

    // --- Typed variable declaration ---
    // Type var = expr;
    // List<T> var = expr;
    // Fn(T)->R var = expr;
    typed_var_decl: type_expr NAME "=" expr ";"

    // --- Variable assignment (non-self) ---
    // var = expr;
    // var.attr = expr;
    var_assignment: NAME "=" expr ";"
                 | NAME "." NAME "=" expr ";"

    // --- Generate ---
    // generate Event to NAME;
    // generate Event to access_chain;  (e.g. door.value())
    // generate Event(param: expr, ...) to NAME;
    // generate Event to NAME delay expr;
    // generate Event(param: expr, ...) to NAME delay expr;
    generate_stmt: "generate" NAME "to" NAME ";"
                 | "generate" NAME "to" access_chain ";"
                 | "generate" NAME "(" param_list ")" "to" NAME ";"
                 | "generate" NAME "(" param_list ")" "to" access_chain ";"
                 | "generate" NAME "to" NAME "delay" expr ";"
                 | "generate" NAME "(" param_list ")" "to" NAME "delay" expr ";"

    // --- Cancel ---
    // cancel Event from sender to target;
    cancel_stmt: "cancel" NAME "from" NAME "to" NAME ";"

    param_list: NAME ":" expr ("," NAME ":" expr)*

    // --- Bridge call ---
    // Domain::Operation[args];           (positional)
    // Domain::Operation[key: val, ...];  (named)
    named_arg_list: NAME ":" expr ("," NAME ":" expr)*
    bridge_call: NAME "::" NAME "[" named_arg_list "]" ";"
               | NAME "::" NAME "[" arglist "]" ";"
               | NAME "::" NAME "[" "]" ";"

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
    // select any/many var related by NAME->NAME (->NAME)*;
    select_related_stmt: "select" ("any"|"many") NAME "related" "by" traversal_chain ";"

    // --- Relate / Unrelate ---
    // relate var1 to var2 across RN;
    relate_stmt: "relate" NAME "to" NAME "across" NAME ";"
    // unrelate var1 from var2 across RN;
    unrelate_stmt: "unrelate" NAME "from" NAME "across" NAME ";"

    // --- If / else if / else ---
    // if (expr) { stmts } [else if (expr) { stmts }]* [else { stmts }]
    if_stmt: "if" "(" expr ")" "{" statement* "}" else_if_chain? ("else" "{" statement* "}")?
    else_if_chain: else_if_clause+
    else_if_clause: "else" "if" "(" expr ")" "{" statement* "}"

    // --- For-each loop ---
    // for (Type var : expr) { stmts }
    for_each_stmt: "for" "(" NAME NAME ":" expr ")" "{" statement* "}"

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

    // --- Select as expression (for typed_var_decl RHS) ---
    // select many from instances of Class [where lambda_expr]
    // select many related by NAME->NAME [where lambda_expr]
    select_expr: "select" ("any"|"many") "from" "instances" "of" NAME ("where" lambda_expr)?
               | "select" ("any"|"many") "related" "by" traversal_chain ("where" lambda_expr)?

    // --- Traversal chain: NAME->NAME (->NAME)* ---
    traversal_chain: NAME "->" NAME ("->" NAME)*

    // --- Lambda expressions ---
    // [] |a: T, b: T| -> RetType { stmts }
    // [capture1, capture2] |param: T| -> RetType { stmts }
    // [self.attr, var] captures (Gap 2: allow dotted name in capture list)
    // -> Set<T> return type (Gap 1: allow generic_type after ->)
    lambda_expr: "[" capture_list? "]" PIPE lambda_params PIPE "->" type_expr "{" statement+ "}"
    capture_item: NAME "." NAME | NAME
    capture_list: capture_item ("," capture_item)*
    lambda_params: lambda_param ("," lambda_param)*
    lambda_param: NAME ":" NAME
    PIPE: "|"

    // --- Chained method/attribute access ---
    // NAME.method(args)                    -> method_call
    // access_chain.method(args)            -> chained_method_call
    // access_chain.attr                    -> chained_attr_access
    access_chain: NAME "." NAME "(" arglist? ")"               -> method_call
                | access_chain "." NAME "(" arglist? ")"        -> chained_method_call
                | access_chain "." NAME                         -> chained_attr_access

    // atom: traversal_chain and dotted_name must appear before plain name to ensure longer match
    atom: NUMBER -> number
        | ESCAPED_STRING -> string
        | access_chain
        | traversal_chain -> direct_traversal
        | NAME "." NAME -> dotted_name
        | NAME "(" arglist? ")" -> func_call
        | NAME -> name
        | "(" expr ")"
        | "cardinality" NAME -> cardinality_expr
        | lambda_expr
        | select_expr

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
