"""compiler/manifest_builder.py — Canonical objects → DomainManifest.

Takes LoadedModel (CanonicalClassDiagram + dict[str, CanonicalStateDiagram])
and produces a fully-populated DomainManifest ready for Plan 04 codegen.

Design decisions applied here:
  D-03: generalization transition table cases A/B/C
  D-04: attribute flattening (subtype wins on conflict)
  D-06: type system mapping (enum/typedef/refinement noted in manifest)
  D-07: deterministic sorted dicts throughout
  D-11: no runtime engine import (TYPE_CHECKING only)
  D-13: can't_happen = absent cell; event_ignored = all-None cell
  D-14: senescent_states populated via compiler.senescence

Exports:
    build_domain_manifest(loaded, parser) -> DomainManifest
    build_class_manifest(...)             -> ClassManifest
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from schema.drawio_canonical import CanonicalClassEntry, CanonicalStateDiagram

if TYPE_CHECKING:
    from lark import Lark
    from engine.manifest import ClassManifest, DomainManifest, TransitionEntry, AssociationManifest
    from compiler.loader import LoadedModel

# ---------------------------------------------------------------------------
# Attribute label parser
# ---------------------------------------------------------------------------

_VIS_SYM = {"+": "public", "-": "private", "#": "protected", "~": "package"}
# Label format (from canonical_builder): "<sym> <name>: <type> [{tag, ...}]"
# scope=class wraps the body in <u>...</u>
_ATTR_RE = re.compile(
    r"^([+\-#~])\s+"           # visibility symbol + space
    r"(?:<u>)?"                 # optional class-scope underline open
    r"([^:]+?)"                 # name (non-greedy, stops at colon)
    r"(?:</u>)?"                # optional class-scope underline close
    r":\s*"                     # colon separator
    r"([^{<\n]+?)"              # type (stop at { or < or newline)
    r"(?:\s*\{([^}]+)\})?"      # optional {tags}
    r"\s*$"
)


def _parse_attr_label(label: str) -> dict[str, Any]:
    """Parse a UML attribute label string into a structured dict.

    Examples::

        "+ car_id: int"          → {name, type, visibility, scope, identifier, referential}
        "- name: String {I1}"   → ... identifier=[1]
        "- id: UniqueID {I1, R6}" → ... identifier=[1], referential="R6"
        "+ <u>count: int</u>"   → ... scope="class"
    """
    # Unescape HTML entities from _html_escape_type
    clean = label.replace("&lt;", "<").replace("&gt;", ">")
    m = _ATTR_RE.match(clean.strip())
    if not m:
        # Fallback: return minimal dict with raw label
        return {"raw": label, "type": "Unknown", "visibility": "private", "scope": "instance"}

    vis_sym, raw_name, type_str, tags_str = m.groups()
    scope = "class" if "<u>" in label else "instance"
    # Strip residual <u></u> from name if scope extraction missed them
    name = raw_name.strip().replace("<u>", "").replace("</u>", "")

    identifier: list[int] | None = None
    referential: str | None = None
    if tags_str:
        for tag in tags_str.split(","):
            tag = tag.strip()
            if re.match(r"^I\d+$", tag):
                idx = int(tag[1:])
                identifier = (identifier or []) + [idx]
            elif re.match(r"^R\d+$", tag):
                referential = tag

    return {
        "name": name,
        "type": type_str.strip(),
        "visibility": _VIS_SYM.get(vis_sym, "private"),
        "scope": scope,
        "identifier": sorted(identifier) if identifier else None,
        "referential": referential,
    }


def _parse_attrs(entry: CanonicalClassEntry) -> dict[str, Any]:
    """Return a sorted attribute dict from a CanonicalClassEntry."""
    result: dict[str, Any] = {}
    for label in entry.attributes:
        info = _parse_attr_label(label)
        name = info.get("name") or label
        result[name] = info
    return dict(sorted(result.items()))


# ---------------------------------------------------------------------------
# Transition table builder
# ---------------------------------------------------------------------------

def _build_transition_table(
    sd: CanonicalStateDiagram,
) -> "dict[tuple[str, str], list[TransitionEntry]]":
    """Build transition_table from a CanonicalStateDiagram.

    Encoding (D-13 / scheduler ground truth):
      explicit transition → cell present with next_state set
      event_ignored       → cell present with next_state=None, action_fn=None, guard_fn=None
      can't_happen        → cell absent (KeyError in scheduler → ErrorMicroStep)

    action_fn is left as None — Plan 04 codegen fills it.
    guard_fn stores the raw guard expression string (or None) for codegen to compile.
    Multiple transitions sharing the same (from_state, event) key are stored as a list
    to support guard siblings (D-06 conformance).
    """
    table: dict[tuple[str, str], list[TransitionEntry]] = {}

    for trans in sd.transitions:
        key = (trans.from_state, trans.event)
        entry: TransitionEntry = {
            "next_state": trans.to,
            "action_fn": None,
            "guard_fn": trans.guard,
        }
        table.setdefault(key, []).append(entry)

    # Sort by key for determinism (D-07)
    return dict(sorted(table.items(), key=lambda kv: (kv[0][0], kv[0][1])))


# ---------------------------------------------------------------------------
# Class manifest builder
# ---------------------------------------------------------------------------

def build_class_manifest(
    entry: CanonicalClassEntry,
    sd: CanonicalStateDiagram | None,
    supertype_manifest: "ClassManifest | None",
    parser: "Lark",
) -> "ClassManifest":
    """Build a ClassManifest for *entry*.

    Handles D-03 generalization cases:
      Case A: entity supertype + active subtype → build own transition table
      Case B: active supertype + active subtype, no SM redefinition → copy super table
      Case C: active supertype + active subtype, redefines SM → build own table

    Attribute flattening (D-04): supertype attrs + own attrs; subtype wins on conflict.
    """
    from compiler.senescence import classify_senescent_states

    # ------------------------------------------------------------------
    # Attributes — flatten supertype first, then overlay own (D-04)
    # ------------------------------------------------------------------
    attrs: dict[str, Any] = {}
    if supertype_manifest:
        attrs.update(supertype_manifest["attributes"])
    own_attrs = _parse_attrs(entry)
    attrs.update(own_attrs)
    attrs = dict(sorted(attrs.items()))

    identifier_attrs = sorted(
        name for name, info in attrs.items()
        if isinstance(info, dict) and info.get("identifier")
    )

    # ------------------------------------------------------------------
    # State machine — D-03 cases
    # ------------------------------------------------------------------
    is_abstract = False  # canonical doesn't expose abstract; default false

    if sd is not None:
        # Has own SM → Case A (entity super) or Case C (active super, redefines)
        transition_table = _build_transition_table(sd)
        initial_state = sd.initial_state
        # Final states: states with no outgoing transitions (true xUML final states).
        # States without entry actions are NOT final — they are common resting states.
        states_with_outgoing = {s for (s, _e) in _build_transition_table(sd).keys()}
        final_states = sorted(
            st.name for st in sd.states
            if st.name not in states_with_outgoing
        )
        entry_actions = {st.name: st.entry_action for st in sd.states}
        senescent_states = classify_senescent_states(sd, parser)
    elif supertype_manifest and supertype_manifest.get("transition_table"):
        # Case B: active supertype with SM, subtype has no SM → copy super table
        transition_table = dict(supertype_manifest["transition_table"])
        initial_state = supertype_manifest.get("initial_state")
        final_states = list(supertype_manifest.get("final_states", []))
        entry_actions = dict(supertype_manifest.get("entry_actions", {}))
        senescent_states = list(supertype_manifest.get("senescent_states", []))
    else:
        # No SM, no super SM → entity class
        transition_table = {}
        initial_state = None
        final_states = []
        entry_actions = {}
        senescent_states = []

    return {
        "name": entry.name,
        "is_abstract": is_abstract,
        "identifier_attrs": identifier_attrs,
        "attributes": attrs,
        "entry_actions": dict(sorted(entry_actions.items())),
        "initial_state": initial_state,
        "final_states": sorted(final_states),
        "senescent_states": senescent_states,
        "transition_table": transition_table,
        "supertype": None,   # filled in by build_domain_manifest post-walk
        "subtypes": [],      # filled in by build_domain_manifest post-walk
    }


# ---------------------------------------------------------------------------
# Domain manifest builder
# ---------------------------------------------------------------------------

def build_domain_manifest(
    loaded: "LoadedModel",
    parser: "Lark | None" = None,
) -> "DomainManifest":
    """Build a DomainManifest from *loaded* canonical objects.

    All dicts are sorted by key (D-07). Generalization inheritance is resolved
    in parents-first topological order so subtype manifests can reference
    the already-built supertype manifest.

    Args:
        loaded: LoadedModel from compiler.loader.load_model.
        parser: STATEMENT_PARSER from pycca.grammar. If None, a fresh instance
                is created (for tests that don't want to manage the parser).
    """
    if parser is None:
        from pycca.grammar import STATEMENT_PARSER
        parser = STATEMENT_PARSER

    cd = loaded.class_diagram

    # ------------------------------------------------------------------
    # Build name → entry map
    # ------------------------------------------------------------------
    entry_map: dict[str, CanonicalClassEntry] = {e.name: e for e in cd.classes}

    # ------------------------------------------------------------------
    # Build generalization maps from CanonicalClassDiagram
    # ------------------------------------------------------------------
    # supertype_of[class_name] → R-name of the generalization
    # parent_of[class_name]    → supertype class name
    # children_of[class_name]  → list of subtype class names
    parent_of: dict[str, str] = {}   # subtype → supertype
    children_of: dict[str, list[str]] = {}

    for gen in cd.generalizations:
        children_of[gen.supertype] = sorted(gen.subtypes)
        for sub in gen.subtypes:
            parent_of[sub] = gen.supertype

    # ------------------------------------------------------------------
    # Topological sort: parents before children
    # ------------------------------------------------------------------
    ordered: list[str] = []
    visited: set[str] = set()

    def _visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        if name in parent_of:
            _visit(parent_of[name])
        ordered.append(name)

    for name in sorted(entry_map):
        _visit(name)

    # ------------------------------------------------------------------
    # Build class manifests in topological order
    # ------------------------------------------------------------------
    class_defs: dict[str, ClassManifest] = {}

    for name in ordered:
        entry = entry_map[name]
        sd = loaded.state_diagrams.get(name)
        supertype_name = parent_of.get(name)
        supertype_manifest = class_defs.get(supertype_name) if supertype_name else None

        manifest = build_class_manifest(entry, sd, supertype_manifest, parser)

        # Wire supertype/subtypes
        manifest["supertype"] = supertype_name
        manifest["subtypes"] = sorted(children_of.get(name, []))

        class_defs[name] = manifest

    # ------------------------------------------------------------------
    # Associations (D-07: sorted by rel_id)
    # ------------------------------------------------------------------
    associations: dict[str, AssociationManifest] = {}
    for assoc in cd.associations:
        associations[assoc.name] = {
            "rel_id": assoc.name,
            "class_a": assoc.point_1,
            "class_b": assoc.point_2,
            "mult_a_to_b": assoc.mult_1_2,
            "mult_b_to_a": assoc.mult_2_1,
        }
    associations = dict(sorted(associations.items()))

    # Generalizations map: supertype → sorted list of subtypes (D-07)
    generalizations: dict[str, list[str]] = {
        gen.supertype: sorted(gen.subtypes)
        for gen in sorted(cd.generalizations, key=lambda g: g.supertype)
    }

    return {
        "class_defs": dict(sorted(class_defs.items())),
        "associations": associations,
        "generalizations": generalizations,
    }
