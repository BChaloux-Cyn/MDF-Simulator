"""Event dataclass and instance-key helper for the MDF simulation engine.

Per design doc D-22: Event is the unit of asynchronous communication between
state machine instances. The optional delay_ms field carries D-23 delayed-event
semantics.

`make_instance_key` produces a hashable, order-independent key from a dict of
identifier attributes so registries can index instances by composite identifier
without depending on insertion order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    event_type: str
    sender_class: str
    sender_id: dict
    target_class: str
    target_id: dict
    args: dict[str, Any] = field(default_factory=dict)
    delay_ms: float | None = None


def make_instance_key(identifier_attrs: dict) -> frozenset:
    """Convert identifier attribute dict to an order-independent hashable key.

    Sorting before frozenset construction guarantees that two equal dicts
    produce equal keys regardless of insertion order.
    """
    return frozenset(sorted(identifier_attrs.items()))
