"""InstanceRegistry — instance lifecycle store for the MDF simulation engine.

Per design doc D-01..D-06: manages instance creation (sync/async), deletion
(sync/async), lookup, and per-instance attribute / state access. Operations
return micro-step records (or Events for async paths) and never raise on
domain-level errors — failures become ErrorMicroStep records per D-28.

The registry is intentionally schema/-tools/-pycca/-free per D-37; it consumes
a `dict[str, ClassManifest]` produced upstream by the compiler.
"""
from __future__ import annotations

from typing import Any

from engine.event import Event, make_instance_key
from engine.manifest import ClassManifest
from engine.microstep import (
    ErrorMicroStep,
    InstanceCreated,
    InstanceDeleted,
    MicroStep,
)


class InstanceRegistry:
    """Stores instance dicts keyed by (class_name, frozenset_identifier)."""

    def __init__(self, class_defs: dict[str, ClassManifest]):
        self._class_defs = class_defs
        self._store: dict[str, dict[frozenset, dict]] = {
            name: {} for name in class_defs
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _class_or_error(self, class_name: str) -> tuple[ClassManifest | None, list[MicroStep]]:
        cdef = self._class_defs.get(class_name)
        if cdef is None:
            return None, [
                ErrorMicroStep(
                    error_kind="unknown_class",
                    message=f"Unknown class {class_name}",
                    context={"class": class_name},
                )
            ]
        return cdef, []

    def _build_instance(
        self,
        cdef: ClassManifest,
        identifier: dict,
        attrs: dict | None,
        class_name: str = "",
    ) -> dict:
        instance: dict[str, Any] = {}

        # D-04: merge supertype declared attributes first (chain upward)
        super_name = cdef.get("supertype")
        while super_name is not None:
            sdef = self._class_defs.get(super_name)
            if sdef is None:
                break
            for k, v in sdef.get("attributes", {}).items():
                instance.setdefault(k, v)
            super_name = sdef.get("supertype")

        # Own declared attribute defaults
        for k, v in cdef.get("attributes", {}).items():
            instance[k] = v

        # Identifier values override defaults
        for k, v in identifier.items():
            instance[k] = v

        # Caller overrides last
        if attrs:
            for k, v in attrs.items():
                instance[k] = v

        # Generated-code contract: every instance dict carries identity metadata
        instance["__instance_key__"] = make_instance_key(identifier)
        instance["__class_name__"] = class_name or cdef.get("name", "")

        return instance

    # ------------------------------------------------------------------
    # Lifecycle: create / delete
    # ------------------------------------------------------------------

    def create_sync(
        self,
        class_name: str,
        identifier: dict,
        initial_state: str,
        attrs: dict | None = None,
    ) -> list[MicroStep]:
        cdef, err = self._class_or_error(class_name)
        if err:
            return err
        assert cdef is not None
        if cdef.get("is_abstract"):
            return [
                ErrorMicroStep(
                    error_kind="abstract_instantiation",
                    message=f"Cannot instantiate abstract class {class_name}",
                    context={"class": class_name},
                )
            ]

        instance = self._build_instance(cdef, identifier, attrs, class_name=class_name)
        instance["curr_state"] = initial_state

        key = make_instance_key(identifier)
        self._store.setdefault(class_name, {})[key] = instance

        return [
            InstanceCreated(
                class_name=class_name,
                instance_id=dict(identifier),
                initial_attrs=dict(instance),
                mode="sync",
            )
        ]

    def create_async(
        self,
        class_name: str,
        identifier: dict,
        initial_state: str,
        attrs: dict | None = None,
    ) -> tuple[list[MicroStep], Event | None]:
        cdef, err = self._class_or_error(class_name)
        if err:
            return err, None
        assert cdef is not None
        if cdef.get("is_abstract"):
            return (
                [
                    ErrorMicroStep(
                        error_kind="abstract_instantiation",
                        message=f"Cannot instantiate abstract class {class_name}",
                        context={"class": class_name},
                    )
                ],
                None,
            )

        instance = self._build_instance(cdef, identifier, attrs, class_name=class_name)
        # curr_state is set when the __creation__ event is processed by the
        # scheduler; pre-seed with None so attribute access is safe.
        instance["curr_state"] = None

        key = make_instance_key(identifier)
        self._store.setdefault(class_name, {})[key] = instance

        evt = Event(
            event_type="__creation__",
            sender_class=class_name,
            sender_id=dict(identifier),
            target_class=class_name,
            target_id=dict(identifier),
            args={"initial_state": initial_state},
        )
        return (
            [
                InstanceCreated(
                    class_name=class_name,
                    instance_id=dict(identifier),
                    initial_attrs=dict(instance),
                    mode="async",
                )
            ],
            evt,
        )

    def delete_sync(self, class_name: str, identifier: dict) -> list[MicroStep]:
        bucket = self._store.get(class_name, {})
        key = make_instance_key(identifier)
        if key not in bucket:
            return [
                ErrorMicroStep(
                    error_kind="double_deletion",
                    message=f"{class_name} {identifier} does not exist",
                    context={"class": class_name, "id": dict(identifier)},
                )
            ]
        del bucket[key]
        return [
            InstanceDeleted(
                class_name=class_name,
                instance_id=dict(identifier),
                mode="sync",
            )
        ]

    def delete_async(self, class_name: str, identifier: dict) -> Event | None:
        bucket = self._store.get(class_name, {})
        key = make_instance_key(identifier)
        if key not in bucket:
            return None
        return Event(
            event_type="__deletion__",
            sender_class=class_name,
            sender_id=dict(identifier),
            target_class=class_name,
            target_id=dict(identifier),
        )

    def process_deletion(self, class_name: str, identifier: dict) -> list[MicroStep]:
        bucket = self._store.get(class_name, {})
        key = make_instance_key(identifier)
        if key not in bucket:
            return [
                ErrorMicroStep(
                    error_kind="double_deletion",
                    message=f"{class_name} {identifier} does not exist",
                    context={"class": class_name, "id": dict(identifier)},
                )
            ]
        del bucket[key]
        return [
            InstanceDeleted(
                class_name=class_name,
                instance_id=dict(identifier),
                mode="async",
            )
        ]

    # ------------------------------------------------------------------
    # Lookup / accessors
    # ------------------------------------------------------------------

    def lookup(self, class_name: str, identifier: dict) -> dict | None:
        bucket = self._store.get(class_name, {})
        return bucket.get(make_instance_key(identifier))

    def lookup_all(self, class_name: str) -> list[dict]:
        return list(self._store.get(class_name, {}).values())

    def get_state(self, class_name: str, identifier: dict) -> str | None:
        inst = self.lookup(class_name, identifier)
        if inst is None:
            return None
        return inst.get("curr_state")

    def set_state(self, class_name: str, identifier: dict, new_state: str) -> None:
        inst = self.lookup(class_name, identifier)
        if inst is None:
            return
        inst["curr_state"] = new_state

    def get_attr(self, class_name: str, identifier: dict, attr_name: str) -> Any:
        inst = self.lookup(class_name, identifier)
        if inst is None:
            return None
        return inst.get(attr_name)

    def set_attr(
        self, class_name: str, identifier: dict, attr_name: str, value: Any
    ) -> None:
        inst = self.lookup(class_name, identifier)
        if inst is None:
            return
        inst[attr_name] = value
