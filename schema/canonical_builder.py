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
    CanonicalBridgeImpl,      # NEW
    CanonicalClassDiagram,
    CanonicalClassEntry,
    CanonicalGeneralization,
    CanonicalMethod,          # NEW
    CanonicalState,
    CanonicalStateDiagram,
    CanonicalTransition,
)

if TYPE_CHECKING:
    from schema.yaml_schema import ClassDef, ClassDiagramFile, StateDiagramFile

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
    virtual: bool = False,
    action: str | None = None,
) -> str:
    """Format a UML method label. Class-scope names are underlined; virtual/abstract are italic."""
    sym = _VIS.get(vis, "-")
    param_sig = ", ".join(f"{p.name}: {_html_escape_type(p.type)}" for p in params)
    ret = f": {_html_escape_type(return_type)}" if return_type else ""
    sig = f"{name}({param_sig}){ret}"
    if virtual:
        tag = "{abstract}" if action is None else "{virtual}"
        sig = f"<i>{tag} {sig}</i>"
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


def yaml_to_canonical_state(
    domain: str,
    sd: "StateDiagramFile",
    class_def: "ClassDef | None" = None,
) -> CanonicalStateDiagram:
    """Convert a StateDiagramFile to a CanonicalStateDiagram object."""
    event_map = {e.name: e for e in sd.events} if sd.events else {}

    canonical_states = sorted(
        [CanonicalState(name=st.name, entry_action=st.entry_action) for st in sd.states],
        key=lambda s: s.name,
    )

    canonical_transitions: list[CanonicalTransition] = []
    for trans in sd.transitions:
        event_def = event_map.get(trans.event) if trans.event else None
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
    canonical_transitions.sort(key=lambda t: (t.from_state, t.event or "", t.to))

    methods: list[CanonicalMethod] = []
    if class_def is not None:
        for m in class_def.methods:
            if m.action is None:
                continue
            params_sig = ", ".join(f"{p.name}: {p.type}" for p in m.params)
            methods.append(CanonicalMethod(
                name=m.name,
                visibility=m.visibility,
                params_sig=params_sig,
                return_type=m.return_type,
                action=m.action,
            ))
        methods.sort(key=lambda m: m.name)

    return CanonicalStateDiagram(
        type="state_diagram",
        domain=domain,
        class_name=sd.class_name,
        initial_state=sd.initial_state,
        states=canonical_states,
        transitions=canonical_transitions,
        methods=methods,
    )


def yaml_to_canonical_class(
    domain: str,
    cd: "ClassDiagramFile",
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> CanonicalClassDiagram:
    """Convert a ClassDiagramFile to a CanonicalClassDiagram object."""
    from schema.yaml_schema import ProvidedBridge

    # Build gen_map from partition declarations on supertype classes
    gen_map: dict[str, dict] = {}
    for cls in cd.classes:
        if cls.partitions:
            for p in cls.partitions:
                gen_map[p.name] = {"supertype": cls.name, "subtypes": sorted(p.subtypes)}

    canonical_classes: list[CanonicalClassEntry] = []
    for cls in sorted(cd.classes, key=lambda c: c.name):
        is_abstract = any(m.virtual and m.action is None for m in cls.methods)
        stereotype = f"{cls.stereotype}, abstract" if is_abstract else cls.stereotype
        attrs = [
            _attr_label(a.visibility, a.scope, a.name, a.type, a.identifier, a.referential)
            for a in cls.attributes
        ]
        methods = [
            _method_label(m.visibility, m.scope, m.name, m.params, m.return_type, m.virtual, m.action)
            for m in cls.methods
        ]
        canonical_classes.append(
            CanonicalClassEntry(
                name=cls.name,
                stereotype=stereotype,
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

    bridge_impls: list[CanonicalBridgeImpl] = []
    if op_lookup is not None:
        for bridge in cd.bridges:
            if not isinstance(bridge, ProvidedBridge):
                continue
            for impl in bridge.implementations:
                op = op_lookup.get(bridge.to_domain, {}).get(impl.name)
                if op is None:
                    continue
                params_sig = ", ".join(
                    f"{p.name}: {p.type}" for p in op.params
                )
                bridge_impls.append(CanonicalBridgeImpl(
                    name=impl.name,
                    to_domain=bridge.to_domain,
                    params_sig=params_sig,
                    return_type=op.return_type,
                    action=impl.action,
                ))
    bridge_impls.sort(key=lambda b: (b.to_domain, b.name))

    return CanonicalClassDiagram(
        type="class_diagram",
        domain=domain.lower(),
        classes=canonical_classes,
        associations=canonical_assocs,
        generalizations=canonical_gens,
        bridge_impls=bridge_impls,
    )


def yaml_to_canonical_class_json(
    domain: str,
    cd: "ClassDiagramFile",
    op_lookup: "dict[str, dict[str, object]] | None" = None,
) -> str:
    """Return canonical JSON string (drop-in for drawio.py's _yaml_to_canonical_class)."""
    return json.dumps(
        yaml_to_canonical_class(domain, cd, op_lookup).model_dump(by_alias=True),
        sort_keys=True,
    )


def yaml_to_canonical_state_json(
    domain: str,
    sd: "StateDiagramFile",
    class_def: "ClassDef | None" = None,
) -> str:
    """Return canonical JSON string (drop-in for drawio.py's _yaml_to_canonical_state)."""
    return json.dumps(
        yaml_to_canonical_state(domain, sd, class_def).model_dump(by_alias=True),
        sort_keys=True,
    )
