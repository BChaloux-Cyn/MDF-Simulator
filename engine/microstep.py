"""Micro-step dataclasses for the MDF simulation engine.

Per design doc D-26: 12 micro-step types covering every observable engine action.
Per D-28: ErrorMicroStep variant for runtime errors (cant_happen, missing instance, etc).

All micro-steps are frozen dataclasses with a Literal `type` field set via
`field(default=..., init=False)` so the discriminator is automatic and immutable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class MicroStep:
    """Base class for all micro-step records emitted by the engine."""


@dataclass(frozen=True)
class SchedulerSelected(MicroStep):
    queue: Literal["priority", "standard"]
    event_type: str
    target_class: str
    target_instance_id: dict
    type: Literal["scheduler_selected"] = field(default="scheduler_selected", init=False)


@dataclass(frozen=True)
class EventReceived(MicroStep):
    class_name: str
    instance_id: dict
    event_type: str
    args: dict
    queue: Literal["priority", "standard"]
    type: Literal["event_received"] = field(default="event_received", init=False)


@dataclass(frozen=True)
class GuardEvaluated(MicroStep):
    expression: str
    result: bool
    variable_values: dict
    type: Literal["guard_evaluated"] = field(default="guard_evaluated", init=False)


@dataclass(frozen=True)
class TransitionFired(MicroStep):
    from_state: str
    to_state: str
    class_name: str
    instance_id: dict
    type: Literal["transition_fired"] = field(default="transition_fired", init=False)


@dataclass(frozen=True)
class ActionExecuted(MicroStep):
    pycca_line: str
    assignments_made: dict
    type: Literal["action_executed"] = field(default="action_executed", init=False)


@dataclass(frozen=True)
class GenerateDispatched(MicroStep):
    event_type: str
    sending_class: str
    sending_instance_id: dict
    target_class: str
    target_instance_id: dict
    args: dict
    queue: Literal["priority", "standard", "delay"]
    type: Literal["generate_dispatched"] = field(default="generate_dispatched", init=False)


@dataclass(frozen=True)
class EventDelayed(MicroStep):
    event_type: str
    sending_class: str
    sending_instance_id: dict
    target_class: str
    target_instance_id: dict
    args: dict
    delay_ms: float
    type: Literal["event_delayed"] = field(default="event_delayed", init=False)


@dataclass(frozen=True)
class EventDelayExpired(MicroStep):
    event_type: str
    target_class: str
    target_instance_id: dict
    type: Literal["event_delay_expired"] = field(default="event_delay_expired", init=False)


@dataclass(frozen=True)
class EventCancelled(MicroStep):
    cancelled_event_type: str
    sender_id: dict
    target_id: dict
    type: Literal["event_cancelled"] = field(default="event_cancelled", init=False)


@dataclass(frozen=True)
class InstanceCreated(MicroStep):
    class_name: str
    instance_id: dict
    initial_attrs: dict
    mode: Literal["sync", "async"]
    type: Literal["instance_created"] = field(default="instance_created", init=False)


@dataclass(frozen=True)
class InstanceDeleted(MicroStep):
    class_name: str
    instance_id: dict
    mode: Literal["sync", "async"]
    type: Literal["instance_deleted"] = field(default="instance_deleted", init=False)


@dataclass(frozen=True)
class BridgeCalled(MicroStep):
    operation: str
    args: dict
    mock_return: Any
    type: Literal["bridge_called"] = field(default="bridge_called", init=False)


@dataclass(frozen=True)
class ErrorMicroStep(MicroStep):
    error_kind: str
    message: str
    context: dict
    type: Literal["error"] = field(default="error", init=False)


@dataclass(frozen=True)
class EventCompleted(MicroStep):
    target: str
    name: str
    duration_ns: int
    type: Literal["event_completed"] = field(default="event_completed", init=False)


@dataclass(frozen=True)
class LongEventWarning(MicroStep):
    target: str
    name: str
    duration_ns: int
    threshold_ns: int
    type: Literal["long_event_warning"] = field(default="long_event_warning", init=False)


@dataclass(frozen=True)
class SenescentEntered(MicroStep):
    instance: str
    state: str
    settled_at: int
    type: Literal["senescent_entered"] = field(default="senescent_entered", init=False)


@dataclass(frozen=True)
class SenescentExited(MicroStep):
    instance: str
    state: str
    exited_at: int
    by_event: str
    type: Literal["senescent_exited"] = field(default="senescent_exited", init=False)
