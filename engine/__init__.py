"""engine - MDF simulation engine runtime framework."""

ENGINE_VERSION = "0.1.0"  # must match compiler.COMPILER_VERSION
from engine.microstep import (
    MicroStep,
    SchedulerSelected,
    EventReceived,
    GuardEvaluated,
    TransitionFired,
    ActionExecuted,
    GenerateDispatched,
    EventDelayed,
    EventDelayExpired,
    EventCancelled,
    InstanceCreated,
    InstanceDeleted,
    BridgeCalled,
    ErrorMicroStep,
)
from engine.event import Event, make_instance_key
from engine.manifest import (
    AssociationManifest,
    ClassManifest,
    DomainManifest,
    TransitionEntry,
)
from engine.registry import InstanceRegistry
from engine.relationship import RelationshipStore
from engine.scheduler import ThreeQueueScheduler
from engine.clock import SimulationClock
from engine.bridge import BridgeMockRegistry
from engine.ctx import SimulationContext, run_simulation

__all__ = [
    "SimulationContext",
    "run_simulation",
    "DomainManifest",
    "ClassManifest",
    "AssociationManifest",
    "TransitionEntry",
    "InstanceRegistry",
    "RelationshipStore",
    "ThreeQueueScheduler",
    "SimulationClock",
    "BridgeMockRegistry",
    "MicroStep",
    "SchedulerSelected",
    "EventReceived",
    "GuardEvaluated",
    "TransitionFired",
    "ActionExecuted",
    "GenerateDispatched",
    "EventDelayed",
    "EventDelayExpired",
    "EventCancelled",
    "InstanceCreated",
    "InstanceDeleted",
    "BridgeCalled",
    "ErrorMicroStep",
    "Event",
    "make_instance_key",
]
