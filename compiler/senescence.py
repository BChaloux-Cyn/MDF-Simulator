"""compiler/senescence.py — Static senescent state classifier (D-14).

A state is **senescent** iff its entry action contains zero ``generate ... to self``
statements (syntactic, conservative — any guarded self-generate still counts).
States with no entry action are senescent by definition.

Exports:
    has_self_generate(tree) -> bool
    classify_senescent_states(sd, parser) -> list[str]   (sorted)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from lark import Tree, Token

if TYPE_CHECKING:
    from lark import Lark
    from schema.drawio_canonical import CanonicalStateDiagram


def has_self_generate(tree: Tree) -> bool:
    """Return True if *tree* contains any ``generate <event> to self`` statement.

    Conservative: recurses into all children, including if/for bodies, so any
    syntactic occurrence counts even if it is unreachable at runtime (D-14 rationale).
    """
    if not isinstance(tree, Tree):
        return False

    if tree.data == "generate_stmt":
        # Grammar: "generate" NAME ("(" arg_list ")")? "to" NAME ("delay" expr)? ";"
        # The target is the last NAME token child.
        name_tokens = [c for c in tree.children if isinstance(c, Token) and c.type == "NAME"]
        if name_tokens and str(name_tokens[-1]) == "self":
            return True

    return any(has_self_generate(child) for child in tree.children if isinstance(child, Tree))


def classify_senescent_states(
    sd: "CanonicalStateDiagram",
    parser: "Lark",
) -> list[str]:
    """Return a sorted list of senescent state names in *sd*.

    A state is senescent when its entry action (if any) contains no
    ``generate ... to self`` statement (D-14).  States with no entry action
    are senescent by definition.

    Args:
        sd:     CanonicalStateDiagram to classify.
        parser: STATEMENT_PARSER from pycca.grammar (Earley, start="start").
    """
    senescent: list[str] = []

    for state in sd.states:
        if state.entry_action is None or state.entry_action.strip() == "":
            senescent.append(state.name)
            continue

        try:
            tree = parser.parse(state.entry_action)
        except Exception:
            # Unparseable entry action — conservatively treat as non-senescent
            # (self-generate may be present; we cannot confirm absence).
            continue

        if not has_self_generate(tree):
            senescent.append(state.name)

    return sorted(senescent)
