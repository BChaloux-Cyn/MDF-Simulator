"""schema/canonical_builder.py — YAML schema objects → canonical Pydantic objects.

Extracted from tools/drawio.py private functions so compiler/ and tools/ share
one YAML→canonical conversion path without either importing the other.

Public API:
    yaml_to_canonical_state(domain, sd) -> CanonicalStateDiagram
    yaml_to_canonical_class(domain, cd) -> CanonicalClassDiagram
    yaml_to_canonical_state_json(domain, sd) -> str   (JSON string, parity with drawio)
    yaml_to_canonical_class_json(domain, cd) -> str   (JSON string, parity with drawio)
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from schema.drawio_canonical import (
    CanonicalAssociation,
    CanonicalClassDiagram,
    CanonicalClassEntry,
    CanonicalGeneralization,
    CanonicalState,
    CanonicalStateDiagram,
    CanonicalTransition,
)

if TYPE_CHECKING:
    from schema.yaml_schema import ClassDiagramFile, StateDiagramFile

# ---------------------------------------------------------------------------
# Internal helpers (mirrors of tools/drawio.py private helpers)
# ---------------------------------------------------------------------------

_VIS: dict[str, str] = {"public": "+", "private": "-", "protected": "#"}
_PHRASE_TARGET_RATIO = 2.0


def _html_escape_type(t: str) -> str:
    """Escape < and > in type names for canonical label strings."""
    return t.replace("<", "&lt;").replace(">", "&gt;")


def _attr_label(
    vis: str,
    scope: str,
    name: str,
    type_: str,
    identifier: list[int] | None = None,
    referential: str | None = None,
) -> str:
    """Format a UML attribute label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    text = f"{name}: {_html_escape_type(type_)}"
    tags: list[str] = []
    if identifier:
        tags.extend(f"I{i}" for i in sorted(identifier))
    if referential:
        tags.append(referential)
    if tags:
        text += f" {{{', '.join(tags)}}}"
    if scope == "class":
        text = f"<u>{text}</u>"
    return f"{sym} {text}"


def _method_label(
    vis: str,
    scope: str,
    name: str,
    params: list,
    return_type: str | None,
) -> str:
    """Format a UML method label. Class-scope names are HTML-underlined."""
    sym = _VIS.get(vis, "-")
    param_sig = ", ".join(f"{p.name}: {_html_escape_type(p.type)}" for p in params)
    ret = f": {_html_escape_type(return_type)}" if return_type else ""
    sig = f"{name}({param_sig}){ret}"
    if scope == "class":
        sig = f"<u>{sig}</u>"
    return f"{sym} {sig}"


def _wrap_squarest(text: str) -> str:
    """Wrap text at the word boundary closest to a 2:1 width:height ratio."""
    words = text.split()
    n = len(words)
    if n <= 1:
        return text
    char_w, line_h = 7, 16

    def _score(lines: list[str]) -> float:
        w = max(len(line) for line in lines) * char_w
        h = len(lines) * line_h
        return abs(w / max(h, 1) - _PHRASE_TARGET_RATIO)

    best, best_score = text, _score([text])
    for i in range(1, n):
        candidate = " ".join(words[:i]) + "\n" + " ".join(words[i:])
        s = _score(candidate.split("\n"))
        if s < best_score:
            best_score, best = s, candidate
    return best


# ---------------------------------------------------------------------------
# Public conversion functions
# ---------------------------------------------------------------------------


def yaml_to_canonical_state(domain: str, sd: "StateDiagramFile") -> CanonicalStateDiagram:
    """Convert a StateDiagramFile to a CanonicalStateDiagram object."""
    event_map = {e.name: e for e in sd.events} if sd.events else {}

    canonical_states = sorted(
        [CanonicalState(name=st.name, entry_action=st.entry_action) for st in sd.states],
        key=lambda s: s.name,
    )

    canonical_transitions: list[CanonicalTransition] = []
    for trans in sd.transitions:
        event_def = event_map.get(trans.event)
        if event_def and event_def.params:
            params = ", ".join(f"{p.name}: {p.type}" for p in event_def.params)
        else:
            params = None
        canonical_transitions.append(
            CanonicalTransition(
                from_state=trans.from_state,
                to=trans.to,
                event=trans.event,
                params=params,
                guard=trans.guard,
            )
        )
    canonical_transitions.sort(key=lambda t: (t.from_state, t.event, t.to))

    return CanonicalStateDiagram(
        type="state_diagram",
        domain=domain,
        class_name=sd.class_name,
        initial_state=sd.initial_state,
        states=canonical_states,
        transitions=canonical_transitions,
    )


def yaml_to_canonical_class(domain: str, cd: "ClassDiagramFile") -> CanonicalClassDiagram:
    """Convert a ClassDiagramFile to a CanonicalClassDiagram object."""
    # Build gen_map from partition declarations on supertype classes
    gen_map: dict[str, dict] = {}
    for cls in cd.classes:
        if cls.partitions:
            for p in cls.partitions:
                gen_map[p.name] = {"supertype": cls.name, "subtypes": sorted(p.subtypes)}

    canonical_classes: list[CanonicalClassEntry] = []
    for cls in sorted(cd.classes, key=lambda c: c.name):
        attrs = [
            _attr_label(a.visibility, a.scope, a.name, a.type, a.identifier, a.referential)
            for a in cls.attributes
        ]
        methods = [
            _method_label(m.visibility, m.scope, m.name, m.params, m.return_type)
            for m in cls.methods
        ]
        canonical_classes.append(
            CanonicalClassEntry(
                name=cls.name,
                stereotype=cls.stereotype,
                specializes=cls.specializes,
                attributes=attrs,
                methods=methods,
            )
        )

    canonical_assocs: list[CanonicalAssociation] = []
    for assoc in sorted(cd.associations, key=lambda a: a.name):
        if assoc.name in gen_map:
            continue  # generalizations appear in their own section
        canonical_assocs.append(
            CanonicalAssociation(
                name=assoc.name,
                point_1=assoc.point_1,
                point_2=assoc.point_2,
                mult_1_2=assoc.mult_1_to_2,
                mult_2_1=assoc.mult_2_to_1,
                phrase_1_2=_wrap_squarest(assoc.phrase_1_to_2),
                phrase_2_1=_wrap_squarest(assoc.phrase_2_to_1),
            )
        )

    canonical_gens: list[CanonicalGeneralization] = [
        CanonicalGeneralization(
            name=rname,
            supertype=info["supertype"],
            subtypes=info["subtypes"],
        )
        for rname, info in sorted(gen_map.items())
    ]

    return CanonicalClassDiagram(
        type="class_diagram",
        domain=domain.lower(),
        classes=canonical_classes,
        associations=canonical_assocs,
        generalizations=canonical_gens,
    )


def yaml_to_canonical_state_json(domain: str, sd: "StateDiagramFile") -> str:
    """Return canonical JSON string (drop-in for drawio.py's _yaml_to_canonical_state)."""
    return json.dumps(
        yaml_to_canonical_state(domain, sd).model_dump(by_alias=True),
        sort_keys=True,
    )


def yaml_to_canonical_class_json(domain: str, cd: "ClassDiagramFile") -> str:
    """Return canonical JSON string (drop-in for drawio.py's _yaml_to_canonical_class)."""
    return json.dumps(
        yaml_to_canonical_class(domain, cd).model_dump(by_alias=True),
        sort_keys=True,
    )
