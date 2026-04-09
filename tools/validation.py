"""
validation — Model validation tools: validate_model, validate_domain, validate_class.

Implemented in plan 03-03 (Phase 3).
Guard completeness added in plan 03-04.
"""
from pathlib import Path

import networkx as nx
import yaml
import z3
from lark import UnexpectedInput
from pydantic import ValidationError

from pycca.grammar import GUARD_PARSER
from schema.yaml_schema import (
    ClassDiagramFile,
    DomainsFile,
    EnumType,
    ScalarType,
    StateDiagramFile,
    TypesFile,
    _SCALAR_PRIMITIVES,
)
from tools.model_io import _pydantic_errors_to_issues, _resolve_domain_path

MODEL_ROOT = Path(".design/model")


# ---------------------------------------------------------------------------
# Issue helpers
# ---------------------------------------------------------------------------


def _make_issue(
    issue: str,
    location: str,
    value: object = None,
    fix: str | None = None,
    severity: str = "error",
) -> dict:
    """Return the extended issue dict with all five fields."""
    return {
        "issue": issue,
        "location": location,
        "value": value,
        "fix": fix,
        "severity": severity,
    }


def _make_pydantic_issues(e: ValidationError, location_prefix: str) -> list[dict]:
    """Convert a Pydantic ValidationError into extended MDF issue dicts."""
    issues = []
    for err in e.errors():
        loc_parts = [str(p) for p in err["loc"]]
        location = f"{location_prefix}::{'.'.join(loc_parts)}" if loc_parts else location_prefix
        issues.append(_make_issue(
            issue=err["msg"],
            location=location,
            value=err.get("input"),
        ))
    return issues


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def _load_yaml_file(path: Path) -> tuple[dict | None, list[dict]]:
    """Load and YAML-parse a file. Returns (data, []) on success, (None, [issue]) on error."""
    try:
        text = path.read_text()
    except OSError as exc:
        return None, [_make_issue(
            issue=f"Cannot read file: {exc}",
            location=str(path),
        )]
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        return None, [_make_issue(
            issue=f"YAML parse error: {getattr(exc, 'problem', str(exc))}",
            location=f"{path}:line {mark.line + 1}" if mark else str(path),
            value=text[:200],
        )]
    return data, []


# ---------------------------------------------------------------------------
# Missing-file checks
# ---------------------------------------------------------------------------


def _check_missing_class_diagram(
    domain: str, domain_path: Path, report_missing: bool
) -> list[dict]:
    issues = []
    cd = domain_path / "class-diagram.yaml"
    if not cd.exists() and report_missing:
        issues.append(_make_issue(
            issue=f"Missing class-diagram.yaml for domain '{domain}'",
            location=f"{domain}::class-diagram.yaml",
        ))
    return issues


def _check_missing_state_diagram(
    domain: str, domain_path: Path, class_name: str, class_defs: list, report_missing: bool
) -> list[dict]:
    """Check if an active class is missing its state diagram (with specializes exception)."""
    issues = []
    state_file = domain_path / "state-diagrams" / f"{class_name}.yaml"
    if not state_file.exists() and report_missing:
        # Exception: subtype (specializes is set) — skip if any supertype has a state diagram
        # We defer that lookup and just check the class's own specializes field
        cls_def = next((c for c in class_defs if c.name == class_name), None)
        if cls_def and cls_def.specializes is not None:
            # Subtype class — check if supertype state diagram exists
            # For the missing-file check: if the class specializes, allow missing state diagram
            pass
        else:
            issues.append(_make_issue(
                issue=f"Missing state diagram for active class '{class_name}'",
                location=f"{domain}::state-diagrams/{class_name}.yaml",
                fix=f"Create .design/model/{domain}/state-diagrams/{class_name}.yaml",
            ))
    return issues


# ---------------------------------------------------------------------------
# Type resolution
# ---------------------------------------------------------------------------


def _load_domain_types(domain_path: Path) -> frozenset[str]:
    """Load domain types.yaml if present. Returns frozenset of defined type names."""
    types_path = domain_path / "types.yaml"
    if not types_path.exists():
        return frozenset()
    data, errs = _load_yaml_file(types_path)
    if data is None:
        return frozenset()
    try:
        tf = TypesFile.model_validate(data)
        return frozenset(t.name for t in tf.types)
    except ValidationError:
        return frozenset()


_BUILTIN_TYPES = frozenset({"Timestamp", "Duration"})
_GENERIC_WRAPPERS = frozenset({"Set", "List", "Optional"})


def _is_valid_type(
    type_str: str,
    domain_types: frozenset[str],
    class_names: frozenset[str] | set[str] = frozenset(),
) -> bool:
    # Scalar primitives, built-in types, domain-defined types, and class names
    if type_str in _SCALAR_PRIMITIVES or type_str in _BUILTIN_TYPES:
        return True
    if type_str in domain_types or type_str in class_names:
        return True
    # Generic wrappers: Set<T>, List<T>, Optional<T>
    if "<" in type_str and type_str.endswith(">"):
        wrapper = type_str[: type_str.index("<")]
        inner = type_str[type_str.index("<") + 1 : -1]
        if wrapper in _GENERIC_WRAPPERS:
            return _is_valid_type(inner, domain_types, class_names)
    return False


def _get_effective_attributes(cls, class_map: dict) -> list:
    """Return cls.attributes merged with supertype identifier attributes for subtypes.

    If cls.specializes is not None, find the supertype that declares a partition
    for cls.specializes and prepend its identifier attributes to cls.attributes.
    This implements ELV-001: subtypes inherit supertype identifier attributes.
    """
    if cls.specializes is None:
        return list(cls.attributes)
    # Find the supertype: a class with a partition whose name matches cls.specializes
    for candidate in class_map.values():
        for partition in (candidate.partitions or []):
            if partition.name == cls.specializes:
                # Return supertype identifiers + subtype attributes
                supertype_ids = [a for a in candidate.attributes if a.identifier is not None]
                return supertype_ids + list(cls.attributes)
    return list(cls.attributes)


# ---------------------------------------------------------------------------
# Referential integrity: class-diagram
# ---------------------------------------------------------------------------


def _check_referential_integrity_class_diagram(
    cd: ClassDiagramFile,
    domain: str,
    domain_types: frozenset[str],
) -> list[dict]:
    issues = []
    class_names = {c.name for c in cd.classes}
    class_map = {c.name: c for c in cd.classes}
    assoc_names = {a.name for a in cd.associations}
    loc_cd = f"{domain}::class-diagram.yaml"

    # Associations: point_1 and point_2 must exist as class names
    for assoc in cd.associations:
        for endpoint, val in [("point_1", assoc.point_1), ("point_2", assoc.point_2)]:
            if val not in class_names:
                issues.append(_make_issue(
                    issue=f"Association '{assoc.name}' references unknown class '{val}' in {endpoint}",
                    location=f"{loc_cd}::associations.{assoc.name}.{endpoint}",
                    value=val,
                    fix=f"Add class '{val}' to the domain or fix the association endpoint",
                ))

    # Build partition map: r_number -> set of listed subtype names, from all supertype classes
    partition_map: dict[str, set[str]] = {}
    for cls in cd.classes:
        if cls.partitions:
            for part in cls.partitions:
                partition_map.setdefault(part.name, set()).update(part.subtypes)

    # Build set of partition R-numbers (generalization relationships)
    partition_names = set(partition_map.keys())

    # Classes: specializes R-numbers must exist in associations or partitions
    for cls in cd.classes:
        if cls.specializes is not None and cls.specializes not in assoc_names and cls.specializes not in partition_names:
            issues.append(_make_issue(
                issue=f"Class '{cls.name}' specializes R-number '{cls.specializes}' which is not in associations or partitions",
                location=f"{loc_cd}::classes.{cls.name}.specializes",
                value=cls.specializes,
                fix=f"Add association or partition '{cls.specializes}' or correct the specializes field",
            ))
        if cls.specializes is not None:
            listed = partition_map.get(cls.specializes, set())
            if cls.name not in listed:
                issues.append(_make_issue(
                    issue=(
                        f"Class '{cls.name}' specializes '{cls.specializes}' "
                        f"but is not listed in any supertype's partitions for '{cls.specializes}'"
                    ),
                    location=f"{loc_cd}::classes.{cls.name}.specializes",
                    value=cls.name,
                    fix=(
                        f"Add '{cls.name}' to the partitions.subtypes list of the supertype "
                        f"that owns '{cls.specializes}'"
                    ),
                ))
        # ELV-001: check that subtypes do not re-declare identifier attributes
        # that already exist on the supertype.
        if cls.specializes is not None:
            effective_attrs = _get_effective_attributes(cls, class_map)
            subtype_attr_names = {a.name for a in cls.attributes}
            for supertype_attr in effective_attrs:
                if supertype_attr.identifier is not None and supertype_attr.name in subtype_attr_names:
                    issues.append(_make_issue(
                        issue=(
                            f"Subtype '{cls.name}' re-declares identifier attribute "
                            f"'{supertype_attr.name}' that exists on its supertype"
                        ),
                        location=f"{loc_cd}::classes.{cls.name}.attributes.{supertype_attr.name}",
                        value=supertype_attr.name,
                        fix=(
                            f"Remove '{supertype_attr.name}' from '{cls.name}' — "
                            f"it is inherited from the supertype via '{cls.specializes}'"
                        ),
                    ))

        # Attributes: type must be primitive or in types.yaml
        for attr in cls.attributes:
            if not _is_valid_type(attr.type, domain_types, class_names):
                issues.append(_make_issue(
                    issue=f"Attribute '{cls.name}.{attr.name}' has unknown type '{attr.type}'",
                    location=f"{loc_cd}::classes.{cls.name}.attributes.{attr.name}.type",
                    value=attr.type,
                    fix=f"Add type '{attr.type}' to types.yaml or use a primitive type",
                ))
            # UniqueID non-identifier warning (likely explicit relvar)
            if attr.type == "UniqueID" and attr.identifier is None:
                issues.append(_make_issue(
                    issue=(
                        f"Attribute '{cls.name}.{attr.name}' has type UniqueID but is not an identifier — "
                        f"this is likely an explicit relvar that should be derived from the relationship"
                    ),
                    location=f"{loc_cd}::classes.{cls.name}.attributes.{attr.name}",
                    value=attr.name,
                    fix=f"Remove '{attr.name}' and let the compiler derive it from the relationship",
                    severity="warning",
                ))

        # Every non-subtype class must have at least one identifier 1 attribute
        if cls.specializes is None:
            has_id1 = any(
                a.identifier is not None and 1 in a.identifier
                for a in cls.attributes
            )
            if not has_id1:
                issues.append(_make_issue(
                    issue=f"Class '{cls.name}' has no identifier 1 attribute",
                    location=f"{loc_cd}::classes.{cls.name}",
                    value=cls.name,
                    fix=f"Add 'identifier: 1' to at least one attribute of '{cls.name}'",
                ))

        # Methods: return_type and param types must be valid
        for method in cls.methods:
            if method.return_type is not None and not _is_valid_type(method.return_type, domain_types, class_names):
                issues.append(_make_issue(
                    issue=f"Method '{cls.name}.{method.name}' return type '{method.return_type}' is unknown",
                    location=f"{loc_cd}::classes.{cls.name}.methods.{method.name}.return",
                    value=method.return_type,
                    fix=f"Add type '{method.return_type}' to types.yaml or use a primitive type",
                ))
            for param in method.params:
                if not _is_valid_type(param.type, domain_types, class_names):
                    issues.append(_make_issue(
                        issue=f"Method '{cls.name}.{method.name}' param '{param.name}' has unknown type '{param.type}'",
                        location=f"{loc_cd}::classes.{cls.name}.methods.{method.name}.params.{param.name}.type",
                        value=param.type,
                        fix=f"Add type '{param.type}' to types.yaml or use a primitive type",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Bridge referential integrity vs DOMAINS.yaml
# ---------------------------------------------------------------------------


def _check_bridge_operations_vs_domains(
    cd: ClassDiagramFile,
    domain: str,
    domains_file: DomainsFile,
) -> list[dict]:
    """Check required/provided bridge operations against DOMAINS.yaml bridge declarations."""
    issues = []
    loc_cd = f"{domain}::class-diagram.yaml"

    for bridge_stanza in cd.bridges:
        to_domain = bridge_stanza.to_domain
        # Find bridge declaration in DOMAINS.yaml
        # Required: this domain calls out → from: domain, to: to_domain
        # Provided: other domain calls in → from: to_domain, to: domain
        if bridge_stanza.direction == "required":
            bridge_entry = next(
                (b for b in domains_file.bridges
                 if b.from_domain == domain and b.to == to_domain),
                None,
            )
        else:
            bridge_entry = next(
                (b for b in domains_file.bridges
                 if b.from_domain == to_domain and b.to == domain),
                None,
            )
        declared_ops = (
            {op.name for op in bridge_entry.operations}
            if bridge_entry is not None
            else set()
        )

        if bridge_stanza.direction == "required":
            for op_name in bridge_stanza.operations:
                if bridge_entry is None or op_name not in declared_ops:
                    issues.append(_make_issue(
                        issue=(
                            f"required_bridge operation '{op_name}' from domain '{domain}' "
                            f"to '{to_domain}' is not declared in DOMAINS.yaml"
                        ),
                        location=f"{loc_cd}::bridges.{to_domain}.operations",
                        value=op_name,
                        fix=f"Add operation '{op_name}' to the bridge entry in DOMAINS.yaml or remove it from class-diagram.yaml",
                    ))
        elif bridge_stanza.direction == "provided":
            impl_names = {impl.name for impl in bridge_stanza.implementations}
            # Every declared op must have an implementation
            for op_name in declared_ops:
                if op_name not in impl_names:
                    issues.append(_make_issue(
                        issue=(
                            f"provided_bridge for '{to_domain}' in domain '{domain}' "
                            f"is missing implementation for declared operation '{op_name}'"
                        ),
                        location=f"{loc_cd}::bridges.{to_domain}.implementations",
                        value=op_name,
                        fix=f"Add implementation for '{op_name}' in class-diagram.yaml",
                    ))
            # Every implementation must match a declared op
            for impl in bridge_stanza.implementations:
                if bridge_entry is None or impl.name not in declared_ops:
                    issues.append(_make_issue(
                        issue=(
                            f"provided_bridge for '{to_domain}' in domain '{domain}' "
                            f"has implementation '{impl.name}' not declared in DOMAINS.yaml"
                        ),
                        location=f"{loc_cd}::bridges.{to_domain}.implementations.{impl.name}",
                        value=impl.name,
                        fix=f"Add operation '{impl.name}' to the bridge entry in DOMAINS.yaml or remove the implementation",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Referential integrity: state-diagram
# ---------------------------------------------------------------------------


def _check_referential_integrity_state_diagram(
    sd: StateDiagramFile, domain: str
) -> list[dict]:
    issues = []
    state_names = {s.name for s in sd.states}
    event_names = {e.name for e in sd.events}
    loc_sd = f"{domain}::state-diagrams/{sd.class_name}.yaml"

    # initial_state must be in states list
    if sd.initial_state not in state_names:
        issues.append(_make_issue(
            issue=f"initial_state '{sd.initial_state}' is not in the states list",
            location=f"{loc_sd}::initial_state",
            value=sd.initial_state,
            fix=f"Add state '{sd.initial_state}' to states or update initial_state to an existing state",
        ))

    # Transitions: to and event must exist
    for i, t in enumerate(sd.transitions):
        if t.to not in state_names:
            issues.append(_make_issue(
                issue=f"Transition from '{t.from_state}' has unknown target state '{t.to}'",
                location=f"{loc_sd}::transitions[{i}].to",
                value=t.to,
                fix=f"Add state '{t.to}' to states or fix the transition target",
            ))
        if t.event not in event_names:
            issues.append(_make_issue(
                issue=f"Transition from '{t.from_state}' references unknown event '{t.event}'",
                location=f"{loc_sd}::transitions[{i}].event",
                value=t.event,
                fix=f"Add event '{t.event}' to events or fix the transition event",
            ))

    return issues


# ---------------------------------------------------------------------------
# Graph reachability
# ---------------------------------------------------------------------------


def _check_reachability(sd: StateDiagramFile, domain: str) -> list[dict]:
    """Build DiGraph from states/transitions, check reachability from initial_state."""
    issues = []
    state_names = {s.name for s in sd.states}
    loc_sd = f"{domain}::state-diagrams/{sd.class_name}.yaml::states"

    G = nx.DiGraph()
    G.add_nodes_from(state_names)
    for t in sd.transitions:
        # Only add edges for valid endpoints (referential integrity checked separately)
        if t.from_state in state_names and t.to in state_names:
            G.add_edge(t.from_state, t.to)

    # Guard: initial_state must be in graph to run descendants()
    if sd.initial_state not in G.nodes:
        return []  # Referential integrity already caught this

    reachable = nx.descendants(G, sd.initial_state) | {sd.initial_state}
    for state in state_names - reachable:
        issues.append(_make_issue(
            issue=f"State '{state}' is unreachable from initial state '{sd.initial_state}'",
            location=loc_sd,
            value=state,
            fix=f"Add a transition into '{state}' from a reachable state or remove it",
        ))

    # Build terminal state set for reference
    terminal_states = {s.name for s in sd.states if s.terminal}

    # Terminal states must not have outgoing transitions
    for state in terminal_states:
        if G.out_degree(state) > 0:
            issues.append(_make_issue(
                issue=f"Terminal state '{state}' has outgoing transitions",
                location=loc_sd,
                value=state,
                fix="Remove outgoing transitions from terminal states, or remove the terminal flag",
            ))

    # Trap states: no outgoing edges and not marked terminal (warning only)
    for state in state_names:
        if G.out_degree(state) == 0 and state not in terminal_states:
            issues.append(_make_issue(
                issue=f"State '{state}' has no outgoing transitions",
                location=loc_sd,
                value=state,
                fix="Add outgoing transitions or mark the state as terminal: true if it ends the object lifecycle",
                severity="warning",
            ))

    return issues


# ---------------------------------------------------------------------------
# Guard completeness helpers
# ---------------------------------------------------------------------------

def _load_types_map(domain_path: Path) -> dict | None:
    """Load types.yaml from domain_path. Returns {type_name: TypeDef} or None if absent/invalid."""
    types_path = domain_path / "types.yaml"
    if not types_path.exists():
        return None
    data, errs = _load_yaml_file(types_path)
    if data is None:
        return None
    try:
        tf = TypesFile.model_validate(data)
        return {t.name: t for t in tf.types}
    except ValidationError:
        return None


def _extract_var_names(tree) -> set[str]:
    """Walk a guard parse tree and collect variable names from the left side of compare_expr nodes."""
    from lark import Tree
    names = set()
    if not isinstance(tree, Tree):
        return names
    if tree.data == "compare_expr" and len(tree.children) == 3:
        left = tree.children[0]
        while isinstance(left, Tree) and left.data in {"add_expr", "mul_expr"}:
            child_trees = [c for c in left.children if isinstance(c, Tree)]
            if len(child_trees) == 1 and len(left.children) == 1:
                left = child_trees[0]
            else:
                break
        if isinstance(left, Tree) and left.data == "name":
            names.add(str(left.children[0]))
        elif isinstance(left, Tree) and left.data == "dotted_name":
            names.add(str(left.children[1]))
    for child in tree.children:
        names |= _extract_var_names(child)
    return names


def _tree_to_z3(tree, z3_vars: dict, enum_maps: dict):
    """Recursively convert a guard parse tree to a Z3 expression. Returns None if not analyzable."""
    from lark import Tree
    if not isinstance(tree, Tree):
        return None

    child_trees = [c for c in tree.children if isinstance(c, Tree)]

    if tree.data == "or_expr":
        if len(child_trees) == 2:
            left = _tree_to_z3(child_trees[0], z3_vars, enum_maps)
            right = _tree_to_z3(child_trees[1], z3_vars, enum_maps)
            if left is None or right is None:
                return None
            return z3.Or(left, right)
        elif len(child_trees) == 1:
            return _tree_to_z3(child_trees[0], z3_vars, enum_maps)
        return None

    elif tree.data == "and_expr":
        if len(child_trees) == 2:
            left = _tree_to_z3(child_trees[0], z3_vars, enum_maps)
            right = _tree_to_z3(child_trees[1], z3_vars, enum_maps)
            if left is None or right is None:
                return None
            return z3.And(left, right)
        elif len(child_trees) == 1:
            return _tree_to_z3(child_trees[0], z3_vars, enum_maps)
        return None

    elif tree.data == "compare_expr":
        if len(tree.children) == 3:
            left_node = tree.children[0]
            op = str(tree.children[1])
            right_node = tree.children[2]

            # Unwrap left to variable
            left = left_node
            while isinstance(left, Tree) and left.data in {"add_expr", "mul_expr"}:
                lc = [c for c in left.children if isinstance(c, Tree)]
                if len(lc) == 1 and len(left.children) == 1:
                    left = lc[0]
                else:
                    return None
            if not isinstance(left, Tree):
                return None
            if left.data == "name":
                var_name = str(left.children[0])
            elif left.data == "dotted_name":
                var_name = str(left.children[1])
            else:
                return None
            if var_name not in z3_vars:
                return None
            z3_var = z3_vars[var_name]

            # Unwrap right to literal
            right = right_node
            while isinstance(right, Tree) and right.data in {"add_expr", "mul_expr"}:
                rc = [c for c in right.children if isinstance(c, Tree)]
                if len(rc) == 1 and len(right.children) == 1:
                    right = rc[0]
                else:
                    return None
            if not isinstance(right, Tree):
                return None
            if right.data == "number":
                val_str = str(right.children[0])
                if z3.is_int(z3_var):
                    rhs = int(float(val_str))
                else:
                    rhs = float(val_str)
            elif right.data == "name":
                enum_map = enum_maps.get(var_name, {})
                enum_val_name = str(right.children[0])
                if enum_val_name not in enum_map:
                    return None
                rhs = enum_map[enum_val_name]
            else:
                return None

            ops = {
                "<": lambda a, b: a < b,
                "<=": lambda a, b: a <= b,
                ">": lambda a, b: a > b,
                ">=": lambda a, b: a >= b,
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
            }
            if op not in ops:
                return None
            return ops[op](z3_var, rhs)

        elif len(tree.children) == 1:
            child = tree.children[0]
            return _tree_to_z3(child, z3_vars, enum_maps) if isinstance(child, Tree) else None
        return None

    elif tree.data in {"add_expr", "mul_expr"}:
        if len(child_trees) == 1 and len(tree.children) == 1:
            return _tree_to_z3(child_trees[0], z3_vars, enum_maps)
        return None

    else:
        if len(child_trees) == 1:
            return _tree_to_z3(child_trees[0], z3_vars, enum_maps)
        return None


def _format_z3_value(val, var_name: str, enum_maps: dict) -> str:
    """Format a Z3 model value as a human-readable string."""
    if val is None:
        return "?"
    if var_name in enum_maps:
        try:
            idx = val.as_long()
            inv_map = {v: k for k, v in enum_maps[var_name].items()}
            return inv_map.get(idx, str(idx))
        except Exception:
            pass
    try:
        return str(val.as_long())
    except Exception:
        pass
    try:
        frac = val.as_fraction()
        if frac.denominator == 1:
            return str(frac.numerator)
        return f"{float(frac):.6g}"
    except Exception:
        pass
    return str(val)


def _check_guard_completeness(
    sd: "StateDiagramFile", domain: str, types_map: dict | None
) -> list[dict]:
    """
    Check guard completeness for all (from_state, event) groups in the state diagram.

    Rules:
    - Multiple unguarded transitions on same (from, event) -> error (ambiguous)
    - AND/OR compound guard -> warning (cannot determine completeness)
    - String-typed param in guard -> error
    - Enum-typed param: missing enum values -> error
    - Integer/Real-typed param with range: gap in interval coverage -> warning
    - Integer/Real-typed param without range: gap in interval coverage -> warning
    """
    issues = []
    loc_prefix = f"{domain}::state-diagrams/{sd.class_name}.yaml"

    # Build event param lookup: event_name -> {param_name: param_type_str}
    event_params: dict[str, dict[str, str]] = {}
    for ev in sd.events:
        event_params[ev.name] = {p.name: p.type for p in ev.params}

    # Group transitions by (from_state, event)
    from itertools import groupby
    key_fn = lambda t: (t.from_state, t.event)  # noqa: E731
    sorted_transitions = sorted(sd.transitions, key=key_fn)

    for (from_state, event), group in groupby(sorted_transitions, key=key_fn):
        ts = list(group)
        guards = [t.guard for t in ts]

        # Rule: multiple unguarded transitions -> error
        unguarded = [g for g in guards if g is None]
        if len(unguarded) > 1:
            issues.append(_make_issue(
                issue=(
                    f"Ambiguous transitions: {len(unguarded)} unguarded transitions "
                    f"from '{from_state}' on event '{event}'"
                ),
                location=f"{loc_prefix}::transitions",
                value=f"({from_state}, {event})",
                fix="Add guard expressions to disambiguate transitions",
                severity="error",
            ))
            continue

        # Skip groups with no guards (single unguarded transition is fine)
        if all(g is None for g in guards):
            continue

        # Parse each guard
        parse_results = []
        parse_failed = False
        for guard_str in guards:
            if guard_str is None:
                continue
            try:
                tree = GUARD_PARSER.parse(guard_str)
                parse_results.append(tree)
            except (UnexpectedInput, Exception):
                issues.append(_make_issue(
                    issue=f"Guard expression cannot be parsed: '{guard_str}'",
                    location=f"{loc_prefix}::transitions",
                    value=guard_str,
                    fix="Correct the guard expression syntax",
                    severity="warning",
                ))
                parse_failed = True

        if parse_failed:
            continue

        # Collect all variable names referenced across all guard trees
        all_var_names: set[str] = set()
        for tree in parse_results:
            all_var_names |= _extract_var_names(tree)

        if not all_var_names:
            continue

        # For each variable, validate type and build Z3 variable + domain constraints
        ev_params = event_params.get(event, {})
        z3_vars: dict = {}
        domain_constraints: list = []
        enum_maps: dict = {}
        skip = False

        for var in sorted(all_var_names):
            if var not in ev_params:
                issues.append(_make_issue(
                    issue=(
                        f"Guard on '{from_state}' -> '{event}': variable '{var}' "
                        f"is not a parameter of event '{event}'; "
                        f"type cannot be determined at compile time"
                    ),
                    location=f"{loc_prefix}::transitions",
                    value=var,
                    fix="Use only event parameter names in guard expressions",
                    severity="error",
                ))
                skip = True
                continue

            type_str = ev_params[var]

            if type_str == "String":
                issues.append(_make_issue(
                    issue=(
                        f"Guard on '{from_state}' -> '{event}': variable '{var}' "
                        f"has type 'String' which is forbidden in guard expressions"
                    ),
                    location=f"{loc_prefix}::transitions",
                    value=var,
                    fix="Use an Enum or numeric type for guard variables",
                    severity="error",
                ))
                skip = True
                continue

            type_def = types_map.get(type_str) if types_map else None

            if type_def is not None and isinstance(type_def, ScalarType) and type_def.base == "String":
                issues.append(_make_issue(
                    issue=(
                        f"Guard on '{from_state}' -> '{event}': variable '{var}' "
                        f"has type '{type_str}' (String base) which is forbidden in guard expressions"
                    ),
                    location=f"{loc_prefix}::transitions",
                    value=var,
                    fix="Use an Enum or numeric type for guard variables",
                    severity="error",
                ))
                skip = True
                continue

            if type_def is not None and isinstance(type_def, EnumType):
                z3_var = z3.Int(var)
                z3_vars[var] = z3_var
                enum_maps[var] = {name: idx for idx, name in enumerate(type_def.values)}
                n = len(type_def.values)
                domain_constraints.append(z3.Or(*[z3_var == i for i in range(n)]))
            elif type_str == "Integer" or (
                type_def is not None
                and isinstance(type_def, ScalarType)
                and type_def.base == "Integer"
            ):
                z3_var = z3.Int(var)
                z3_vars[var] = z3_var
                if type_def is not None and isinstance(type_def, ScalarType) and type_def.range:
                    lo, hi = int(type_def.range[0]), int(type_def.range[1])
                else:
                    lo, hi = -2_147_483_648, 2_147_483_647  # int32 default
                domain_constraints.append(z3_var >= lo)
                domain_constraints.append(z3_var <= hi)
            elif type_str == "Real" or (
                type_def is not None
                and isinstance(type_def, ScalarType)
                and type_def.base == "Real"
            ):
                z3_var = z3.Real(var)
                z3_vars[var] = z3_var
                if type_def is not None and isinstance(type_def, ScalarType) and type_def.range:
                    lo, hi = float(type_def.range[0]), float(type_def.range[1])
                else:
                    lo, hi = -3.4028235e38, 3.4028235e38  # float32 default
                domain_constraints.append(z3_var >= lo)
                domain_constraints.append(z3_var <= hi)
            else:
                issues.append(_make_issue(
                    issue=(
                        f"Guard on '{from_state}' -> '{event}': variable '{var}' "
                        f"has unresolvable type '{type_str}'"
                    ),
                    location=f"{loc_prefix}::transitions",
                    value=var,
                    fix="Ensure the variable's type is declared in types.yaml",
                    severity="error",
                ))
                skip = True

        if skip:
            continue

        # Convert each guard tree to a Z3 formula
        guard_formulas = []
        conversion_failed = False
        for tree in parse_results:
            formula = _tree_to_z3(tree, z3_vars, enum_maps)
            if formula is None:
                conversion_failed = True
                break
            guard_formulas.append(formula)

        if conversion_failed:
            issues.append(_make_issue(
                issue=(
                    f"Guard on '{from_state}' -> '{event}': guard expression is too complex "
                    f"for completeness analysis (non-linear or unsupported construct)"
                ),
                location=f"{loc_prefix}::transitions",
                value=f"({from_state}, {event})",
                fix="Simplify guards to simple comparisons if completeness checking is desired",
                severity="warning",
            ))
            continue

        if not guard_formulas:
            continue

        # Check satisfiability of NOT(g1 OR g2 OR ... OR gn) under domain constraints
        solver = z3.Solver()
        for constraint in domain_constraints:
            solver.add(constraint)
        combined = z3.Or(*guard_formulas) if len(guard_formulas) > 1 else guard_formulas[0]
        solver.add(z3.Not(combined))
        result = solver.check()

        if result == z3.sat:
            model = solver.model()
            parts = []
            for var in sorted(z3_vars.keys()):
                val = model[z3_vars[var]]
                parts.append(f"{var}={_format_z3_value(val, var, enum_maps)}")
            counterexample = ", ".join(parts)
            issues.append(_make_issue(
                issue=(
                    f"Incomplete guard on '{from_state}' -> '{event}': "
                    f"no guard fires when {counterexample}"
                ),
                location=f"{loc_prefix}::transitions",
                value=f"({from_state}, {event})",
                fix="Add or extend guard expressions to cover all cases",
                severity="error",
            ))
        elif result == z3.unknown:
            issues.append(_make_issue(
                issue=(
                    f"Z3 could not determine guard completeness for "
                    f"'{from_state}' -> '{event}'"
                ),
                location=f"{loc_prefix}::transitions",
                value=f"({from_state}, {event})",
                severity="warning",
            ))
        # z3.unsat → complete, no issue

    return issues


# ---------------------------------------------------------------------------
# Per-domain validation core
# ---------------------------------------------------------------------------


def _validate_active_class_state_diagram(
    domain: str,
    domain_path: Path,
    class_name: str,
    report_missing: bool,
) -> list[dict]:
    """Validate the state diagram for one active class. Returns list of issues."""
    issues = []
    state_file = domain_path / "state-diagrams" / f"{class_name}.yaml"

    if not state_file.exists():
        if report_missing:
            issues.append(_make_issue(
                issue=f"Missing state diagram for active class '{class_name}'",
                location=f"{domain}::state-diagrams/{class_name}.yaml",
                fix=f"Create .design/model/{domain}/state-diagrams/{class_name}.yaml",
            ))
        return issues

    data, load_errs = _load_yaml_file(state_file)
    issues.extend(load_errs)
    if data is None:
        return issues

    try:
        sd = StateDiagramFile.model_validate(data)
    except ValidationError as exc:
        issues.extend(_make_pydantic_issues(
            exc, f"{domain}::state-diagrams/{class_name}.yaml"
        ))
        return issues

    # Referential integrity (run first — reachability depends on it)
    ri_issues = _check_referential_integrity_state_diagram(sd, domain)
    issues.extend(ri_issues)

    # Guard completeness (after RI, before reachability)
    types_map = _load_types_map(domain_path)
    issues.extend(_check_guard_completeness(sd, domain, types_map))

    # Only run reachability if initial_state is valid (i.e., no initial_state issue)
    initial_state_ok = not any("initial_state" in i["location"] for i in ri_issues)
    if initial_state_ok:
        issues.extend(_check_reachability(sd, domain))

    return issues


def _validate_domain_data(
    domain: str,
    domain_path: Path,
    report_missing: bool,
    domains_file: DomainsFile | None = None,
) -> list[dict]:
    """Core per-domain validation. Returns accumulated issues."""
    issues = []

    # Check for class-diagram.yaml
    issues.extend(_check_missing_class_diagram(domain, domain_path, report_missing))

    cd_path = domain_path / "class-diagram.yaml"
    if not cd_path.exists():
        return issues  # Cannot continue without class diagram

    data, load_errs = _load_yaml_file(cd_path)
    issues.extend(load_errs)
    if data is None:
        return issues

    try:
        cd = ClassDiagramFile.model_validate(data)
    except ValidationError as exc:
        issues.extend(_make_pydantic_issues(exc, f"{domain}::class-diagram.yaml"))
        return issues

    # Load domain types (optional)
    domain_types = _load_domain_types(domain_path)

    # Referential integrity on class diagram
    issues.extend(_check_referential_integrity_class_diagram(cd, domain, domain_types))

    # Bridge operations vs DOMAINS.yaml (only when validate_model provides domains_file)
    if domains_file is not None:
        issues.extend(_check_bridge_operations_vs_domains(cd, domain, domains_file))

    # Validate active class state diagrams
    for cls in cd.classes:
        if cls.stereotype == "active":
            # Exception: subtype with specializes may not need its own state diagram
            if cls.specializes is not None:
                state_file = domain_path / "state-diagrams" / f"{cls.name}.yaml"
                if not state_file.exists():
                    # Specializes — skip missing-file check (inherits from supertype)
                    continue
            issues.extend(_validate_active_class_state_diagram(
                domain, domain_path, cls.name, report_missing
            ))

    return issues


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def validate_class(
    domain: str, class_name: str, report_missing: bool = True
) -> list[dict]:
    """
    Validate one class from class-diagram.yaml and its state diagram if active.

    Returns list[dict] with fields: issue, location, value, fix, severity.
    Never raises exceptions — all errors returned as structured data.
    """
    try:
        issues = []
        domain_path = _resolve_domain_path(domain)
        if domain_path is None:
            if report_missing:
                issues.append(_make_issue(
                    issue=f"Domain '{domain}' not found",
                    location=f"{domain}",
                    fix=f"Create .design/model/{domain}/class-diagram.yaml",
                ))
            return issues

        cd_path = domain_path / "class-diagram.yaml"
        if not cd_path.exists():
            if report_missing:
                issues.append(_make_issue(
                    issue=f"Missing class-diagram.yaml for domain '{domain}'",
                    location=f"{domain}::class-diagram.yaml",
                ))
            return issues

        data, load_errs = _load_yaml_file(cd_path)
        issues.extend(load_errs)
        if data is None:
            return issues

        try:
            cd = ClassDiagramFile.model_validate(data)
        except ValidationError as exc:
            issues.extend(_make_pydantic_issues(exc, f"{domain}::class-diagram.yaml"))
            return issues

        # Find the target class
        cls_def = next((c for c in cd.classes if c.name == class_name), None)
        if cls_def is None:
            issues.append(_make_issue(
                issue=f"Class '{class_name}' not found in domain '{domain}'",
                location=f"{domain}::class-diagram.yaml::classes",
                value=class_name,
            ))
            return issues

        # Load domain types
        domain_types = _load_domain_types(domain_path)

        # Check referential integrity for this class only (and its associations involving it)
        class_names = {c.name for c in cd.classes}
        assoc_names = {a.name for a in cd.associations}
        loc_cd = f"{domain}::class-diagram.yaml"

        partition_names = {
            part.name for c in cd.classes if c.partitions for part in c.partitions
        }
        if cls_def.specializes is not None and cls_def.specializes not in assoc_names and cls_def.specializes not in partition_names:
            issues.append(_make_issue(
                issue=f"Class '{cls_def.name}' specializes R-number '{cls_def.specializes}' which is not in associations or partitions",
                location=f"{loc_cd}::classes.{cls_def.name}.specializes",
                value=cls_def.specializes,
                fix=f"Add association or partition '{cls_def.specializes}' or correct the specializes field",
            ))
        for attr in cls_def.attributes:
            if not _is_valid_type(attr.type, domain_types, class_names):
                issues.append(_make_issue(
                    issue=f"Attribute '{cls_def.name}.{attr.name}' has unknown type '{attr.type}'",
                    location=f"{loc_cd}::classes.{cls_def.name}.attributes.{attr.name}.type",
                    value=attr.type,
                    fix=f"Add type '{attr.type}' to types.yaml or use a primitive type",
                ))
        for method in cls_def.methods:
            if method.return_type is not None and not _is_valid_type(method.return_type, domain_types, class_names):
                issues.append(_make_issue(
                    issue=f"Method '{cls_def.name}.{method.name}' return type '{method.return_type}' is unknown",
                    location=f"{loc_cd}::classes.{cls_def.name}.methods.{method.name}.return",
                    value=method.return_type,
                ))
            for param in method.params:
                if not _is_valid_type(param.type, domain_types, class_names):
                    issues.append(_make_issue(
                        issue=f"Method '{cls_def.name}.{method.name}' param '{param.name}' has unknown type '{param.type}'",
                        location=f"{loc_cd}::classes.{cls_def.name}.methods.{method.name}.params.{param.name}.type",
                        value=param.type,
                    ))

        # If active, validate state diagram
        if cls_def.stereotype == "active":
            issues.extend(_validate_active_class_state_diagram(
                domain, domain_path, class_name, report_missing
            ))

        return issues
    except Exception as exc:  # noqa: BLE001
        return [_make_issue(
            issue=f"Unexpected error validating class '{class_name}' in domain '{domain}': {exc}",
            location=f"{domain}::class-diagram.yaml",
        )]


def validate_domain(domain: str, report_missing: bool = True) -> list[dict]:
    """
    Validate one domain: class-diagram.yaml + state-diagrams/*.yaml.

    Returns list[dict] with fields: issue, location, value, fix, severity.
    Never raises exceptions — all errors returned as structured data.
    """
    try:
        issues = []
        domain_path = _resolve_domain_path(domain)
        if domain_path is None:
            if report_missing:
                issues.append(_make_issue(
                    issue=f"Domain '{domain}' directory not found",
                    location=f"{domain}",
                    fix=f"Create .design/model/{domain}/ directory",
                ))
            return issues
        return _validate_domain_data(domain, domain_path, report_missing)
    except Exception as exc:  # noqa: BLE001
        return [_make_issue(
            issue=f"Unexpected error validating domain '{domain}': {exc}",
            location=f"{domain}",
        )]


def validate_model(report_missing: bool = True) -> list[dict]:
    """
    Validate the entire model: DOMAINS.yaml + all domains + all active class state diagrams.

    Returns list[dict] with fields: issue, location, value, fix, severity.
    Never raises exceptions — all errors returned as structured data.
    """
    try:
        issues = []
        domains_path = MODEL_ROOT / "DOMAINS.yaml"

        if not domains_path.exists():
            if report_missing:
                issues.append(_make_issue(
                    issue="Missing DOMAINS.yaml",
                    location=f"{MODEL_ROOT}/DOMAINS.yaml",
                    fix="Create .design/model/DOMAINS.yaml",
                ))
            return issues

        data, load_errs = _load_yaml_file(domains_path)
        issues.extend(load_errs)
        if data is None:
            return issues

        try:
            domains_file = DomainsFile.model_validate(data)
        except ValidationError as exc:
            issues.extend(_make_pydantic_issues(exc, "DOMAINS.yaml"))
            return issues

        # Validate each domain (skip realized domains — they have no classes or state machines)
        for domain_entry in domains_file.domains:
            if domain_entry.type == "realized":
                continue
            domain = domain_entry.name
            domain_path = _resolve_domain_path(domain)
            if domain_path is None:
                if report_missing:
                    issues.append(_make_issue(
                        issue=f"Domain '{domain}' listed in DOMAINS.yaml has no directory",
                        location=f"DOMAINS.yaml::domains.{domain}",
                        value=domain,
                        fix=f"Create .design/model/{domain}/ directory",
                    ))
                continue
            issues.extend(_validate_domain_data(
                domain, domain_path, report_missing, domains_file=domains_file
            ))

        return issues
    except Exception as exc:  # noqa: BLE001
        return [_make_issue(
            issue=f"Unexpected error validating model: {exc}",
            location="model",
        )]
