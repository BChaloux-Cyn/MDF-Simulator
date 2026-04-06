"""RelationshipStore — inter-instance link store with multiplicity enforcement.

Per design doc D-07..D-09: maintains a set of (class_a, id_a, class_b, id_b)
tuples per relationship id. Multiplicity violations and unrelate-not-found
become ErrorMicroStep records (D-28); the store never raises domain errors.

Schema/-tools/-pycca/-free per D-37: consumes a `dict[str, AssociationManifest]`
produced upstream by the compiler.
"""
from __future__ import annotations

from engine.event import make_instance_key
from engine.manifest import AssociationManifest
from engine.microstep import ErrorMicroStep, MicroStep


def _is_one(mult: str) -> bool:
    return str(mult).strip() == "1"


class RelationshipStore:
    """Stores relationship links keyed by rel_id."""

    def __init__(self, associations: dict[str, AssociationManifest]):
        self._associations = associations
        # rel_id -> list of link dicts
        # Each link: {"class_a", "key_a", "id_a", "class_b", "key_b", "id_b"}
        self._links: dict[str, list[dict]] = {rid: [] for rid in associations}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_sides(
        self,
        assoc: AssociationManifest,
        class_x: str,
        id_x: dict,
        class_y: str,
        id_y: dict,
    ) -> tuple[str, dict, str, dict] | None:
        """Return (class_a, id_a, class_b, id_b) matching the assoc orientation,
        or None if classes don't match the assoc."""
        ca = assoc["class_a"]
        cb = assoc["class_b"]
        if class_x == ca and class_y == cb:
            return ca, id_x, cb, id_y
        if class_x == cb and class_y == ca:
            return ca, id_y, cb, id_x
        return None

    def _count_on_side(
        self, rel_id: str, side: str, class_name: str, key: frozenset
    ) -> int:
        """Count existing links involving (class_name, key) on the given side ('a'|'b')."""
        n = 0
        for link in self._links[rel_id]:
            if side == "a" and link["class_a"] == class_name and link["key_a"] == key:
                n += 1
            elif side == "b" and link["class_b"] == class_name and link["key_b"] == key:
                n += 1
        return n

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def relate(
        self,
        rel_id: str,
        class_a: str,
        id_a: dict,
        class_b: str,
        id_b: dict,
    ) -> list[MicroStep]:
        assoc = self._associations.get(rel_id)
        if assoc is None:
            return [
                ErrorMicroStep(
                    error_kind="unknown_relationship",
                    message=f"Unknown relationship {rel_id}",
                    context={"rel_id": rel_id},
                )
            ]

        norm = self._normalize_sides(assoc, class_a, id_a, class_b, id_b)
        if norm is None:
            return [
                ErrorMicroStep(
                    error_kind="relationship_class_mismatch",
                    message=f"Classes ({class_a},{class_b}) do not match {rel_id}",
                    context={
                        "rel_id": rel_id,
                        "class_a": class_a,
                        "class_b": class_b,
                    },
                )
            ]
        n_class_a, n_id_a, n_class_b, n_id_b = norm
        key_a = make_instance_key(n_id_a)
        key_b = make_instance_key(n_id_b)

        # Multiplicity check
        # mult_b_to_a == "1": each B can link to at most one A => check side B
        if _is_one(assoc["mult_b_to_a"]):
            if self._count_on_side(rel_id, "b", n_class_b, key_b) >= 1:
                return [
                    ErrorMicroStep(
                        error_kind="multiplicity_violation",
                        message=(
                            f"Multiplicity violation on {rel_id}: "
                            f"{n_class_b} {dict(n_id_b)} already linked"
                        ),
                        context={
                            "rel_id": rel_id,
                            "class": n_class_b,
                            "id": dict(n_id_b),
                        },
                    )
                ]
        # mult_a_to_b == "1": each A can link to at most one B => check side A
        if _is_one(assoc["mult_a_to_b"]):
            if self._count_on_side(rel_id, "a", n_class_a, key_a) >= 1:
                return [
                    ErrorMicroStep(
                        error_kind="multiplicity_violation",
                        message=(
                            f"Multiplicity violation on {rel_id}: "
                            f"{n_class_a} {dict(n_id_a)} already linked"
                        ),
                        context={
                            "rel_id": rel_id,
                            "class": n_class_a,
                            "id": dict(n_id_a),
                        },
                    )
                ]

        self._links[rel_id].append(
            {
                "class_a": n_class_a,
                "key_a": key_a,
                "id_a": dict(n_id_a),
                "class_b": n_class_b,
                "key_b": key_b,
                "id_b": dict(n_id_b),
            }
        )
        return []

    def unrelate(
        self,
        rel_id: str,
        class_a: str,
        id_a: dict,
        class_b: str,
        id_b: dict,
    ) -> list[MicroStep]:
        assoc = self._associations.get(rel_id)
        if assoc is None:
            return [
                ErrorMicroStep(
                    error_kind="unknown_relationship",
                    message=f"Unknown relationship {rel_id}",
                    context={"rel_id": rel_id},
                )
            ]
        norm = self._normalize_sides(assoc, class_a, id_a, class_b, id_b)
        if norm is None:
            return [
                ErrorMicroStep(
                    error_kind="unrelate_not_found",
                    message=f"No matching link for {rel_id}",
                    context={
                        "rel_id": rel_id,
                        "class_a": class_a,
                        "class_b": class_b,
                    },
                )
            ]
        n_class_a, n_id_a, n_class_b, n_id_b = norm
        key_a = make_instance_key(n_id_a)
        key_b = make_instance_key(n_id_b)

        for i, link in enumerate(self._links[rel_id]):
            if (
                link["class_a"] == n_class_a
                and link["key_a"] == key_a
                and link["class_b"] == n_class_b
                and link["key_b"] == key_b
            ):
                self._links[rel_id].pop(i)
                return []

        return [
            ErrorMicroStep(
                error_kind="unrelate_not_found",
                message=f"No matching link for {rel_id}",
                context={
                    "rel_id": rel_id,
                    "class_a": class_a,
                    "id_a": dict(id_a),
                    "class_b": class_b,
                    "id_b": dict(id_b),
                },
            )
        ]

    def navigate(
        self, rel_id: str, from_class: str, from_id: dict
    ) -> list[dict]:
        assoc = self._associations.get(rel_id)
        if assoc is None:
            return []
        from_key = make_instance_key(from_id)
        results: list[dict] = []
        for link in self._links[rel_id]:
            if link["class_a"] == from_class and link["key_a"] == from_key:
                results.append({"class": link["class_b"], "id": dict(link["id_b"])})
            elif link["class_b"] == from_class and link["key_b"] == from_key:
                results.append({"class": link["class_a"], "id": dict(link["id_a"])})
        return results

    def navigate_chain(
        self,
        chain: list[tuple[str, str]],
        start_class: str,
        start_id: dict,
    ) -> list[dict]:
        """Walk a chain of (rel_id, target_class) hops from a starting instance."""
        frontier: list[dict] = [{"class": start_class, "id": dict(start_id)}]
        for rel_id, target_class in chain:
            next_frontier: list[dict] = []
            seen: set[tuple[str, frozenset]] = set()
            for node in frontier:
                hops = self.navigate(rel_id, node["class"], node["id"])
                for h in hops:
                    if h["class"] != target_class:
                        continue
                    sig = (h["class"], make_instance_key(h["id"]))
                    if sig in seen:
                        continue
                    seen.add(sig)
                    next_frontier.append(h)
            frontier = next_frontier
        return frontier
