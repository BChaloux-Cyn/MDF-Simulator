"""Pre-flight checks run after bundle load, before simulation starts.

Design decisions (05.3-CONTEXT.md):
  D-13: Pre-flight multiplicity check — verify required relationship multiplicities
        from the domain manifest are satisfied by the scenario's initial population.
        Hard fail if violated.

AssociationManifest field names (engine/manifest.py):
  rel_id, class_a, class_b, mult_a_to_b, mult_b_to_a
  mult_a_to_b: multiplicity from A's perspective looking at B (what B must supply)
  mult_b_to_a: multiplicity from B's perspective looking at A (what A must supply)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PreflightIssue:
    """A single pre-flight validation failure."""
    code: str
    location: str
    message: str


def check_multiplicity(scenario: Any, manifest: dict) -> list[PreflightIssue]:
    """Verify scenario relationships satisfy required multiplicities in manifest associations.

    For each association with a required end (multiplicity "1" or "1..*"), confirm that
    every participating instance has at least one relationship link in the scenario's
    initial relationships list.

    Args:
        scenario: Validated ScenarioDef (instances + relationships populated).
        manifest: DomainManifest dict with "associations" mapping rel_id -> AssociationManifest.

    Returns:
        List of PreflightIssue. Empty list means no violations found.
    """
    issues: list[PreflightIssue] = []
    associations = manifest.get("associations", {})

    # Build alias → class lookup from scenario instances
    inst_class: dict[str, str] = {i.name: i.class_name for i in scenario.instances}

    # Index links per rel_id: rel_id → [(a_name, b_name)]
    links_by_rel: dict[str, list[tuple[str, str]]] = {}
    for r in scenario.relationships:
        links_by_rel.setdefault(r.rel, []).append((r.a, r.b))

    for rel_id, assoc in associations.items():
        class_a: str = assoc.get("class_a", "")
        class_b: str = assoc.get("class_b", "")
        # mult_a_to_b: multiplicity of the B end (how many B each A must have)
        mult_a_to_b: str = str(assoc.get("mult_a_to_b", ""))
        # mult_b_to_a: multiplicity of the A end (how many A each B must have)
        mult_b_to_a: str = str(assoc.get("mult_b_to_a", ""))

        links = links_by_rel.get(rel_id, [])

        # For each instance of class_a, if mult_a_to_b is required ("1" or "1..*"),
        # ensure it appears as `a` in at least one link for this rel.
        if mult_a_to_b.startswith("1"):
            for name, cls in inst_class.items():
                if cls == class_a:
                    if not any(a == name for a, _b in links):
                        issues.append(PreflightIssue(
                            code="missing-required-link",
                            location=f"{class_a}.{name} via {rel_id}",
                            message=(
                                f"Instance {name!r} ({class_a}) requires at least one {rel_id} "
                                f"link (mult_a_to_b={mult_a_to_b!r}) but none provided"
                            ),
                        ))

        # For each instance of class_b, if mult_b_to_a is required ("1" or "1..*"),
        # ensure it appears as `b` in at least one link for this rel.
        if mult_b_to_a.startswith("1"):
            for name, cls in inst_class.items():
                if cls == class_b:
                    if not any(b == name for _a, b in links):
                        issues.append(PreflightIssue(
                            code="missing-required-link",
                            location=f"{class_b}.{name} via {rel_id}",
                            message=(
                                f"Instance {name!r} ({class_b}) requires at least one {rel_id} "
                                f"link (mult_b_to_a={mult_b_to_a!r}) but none provided"
                            ),
                        ))

    return issues
