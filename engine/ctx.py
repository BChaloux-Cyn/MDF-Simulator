"""SimulationContext (ctx) — the single API surface generated action code calls.

Per design doc D-35/D-36: ctx wires together the registry, relationship store,
scheduler, clock, and bridge mock registry. All methods either delegate to a
component or compose multiple components into one externally-coherent operation.

`run_simulation` is the top-level entry point — a generator that yields
micro-steps from a fresh ctx, set up by an optional scenario dict.

Per D-37: zero imports from schema/, tools/, or pycca/.
"""
from __future__ import annotations

from typing import Any, Callable, Generator

from engine.bridge import BridgeMockRegistry
from engine.clock import SimulationClock
from engine.event import Event
from engine.microstep import MicroStep
from engine.registry import InstanceRegistry
from engine.relationship import RelationshipStore
from engine.scheduler import ThreeQueueScheduler


class SimulationContext:
    """Single API surface that generated action code calls into (D-35).

    Owns: clock, registry, relationships, bridge_registry, scheduler.
    Methods follow D-36.
    """

    def __init__(self, domain_manifest: dict, bridge_mocks: dict | None = None):
        class_defs = domain_manifest["class_defs"]
        associations = domain_manifest.get("associations", {})
        generalizations = domain_manifest.get("generalizations", {})

        self.clock = SimulationClock()
        self.registry = InstanceRegistry(class_defs)
        self.relationships = RelationshipStore(associations)
        self.bridge_registry = BridgeMockRegistry(mocks=bridge_mocks)
        self.scheduler = ThreeQueueScheduler(
            registry=self.registry,
            clock=self.clock,
            class_defs=class_defs,
            generalizations=generalizations,
        )
        self._running = False
        self.event_duration_warn_ns: int | None = None

    # ------------------------------------------------------------------
    # Event generation / cancellation
    # ------------------------------------------------------------------

    def generate(
        self,
        event_type: str,
        sender_class: str,
        sender_id: dict,
        target_class: str,
        target_id: dict,
        args: dict | None = None,
        delay_ms: float | None = None,
    ) -> list[MicroStep]:
        evt = Event(
            event_type=event_type,
            sender_class=sender_class,
            sender_id=dict(sender_id),
            target_class=target_class,
            target_id=dict(target_id),
            args=dict(args or {}),
            delay_ms=delay_ms,
        )
        return self.scheduler.enqueue(evt)

    def cancel(
        self,
        event_type: str,
        sender_class: str,
        sender_id: dict,
        target_class: str,
        target_id: dict,
    ) -> list[MicroStep]:
        return self.scheduler.cancel(
            event_type, sender_class, sender_id, target_class, target_id
        )

    # ------------------------------------------------------------------
    # Instance lifecycle
    # ------------------------------------------------------------------

    def create_sync(
        self,
        class_name: str,
        identifier: dict,
        initial_state: str,
        attrs: dict | None = None,
    ) -> list[MicroStep]:
        return self.registry.create_sync(class_name, identifier, initial_state, attrs)

    def create_async(
        self,
        class_name: str,
        identifier: dict,
        initial_state: str,
        attrs: dict | None = None,
    ) -> list[MicroStep]:
        steps, evt = self.registry.create_async(
            class_name, identifier, initial_state, attrs
        )
        result = list(steps)
        if evt is not None:
            result.extend(self.scheduler.enqueue(evt))
        return result

    def delete(
        self, class_name: str, identifier: dict, sync: bool = False
    ) -> list[MicroStep]:
        if sync:
            return self.registry.delete_sync(class_name, identifier)
        evt = self.registry.delete_async(class_name, identifier)
        if evt is None:
            return []
        return self.scheduler.enqueue(evt)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def relate(
        self,
        rel_id: str,
        class_a: str,
        id_a: dict,
        class_b: str,
        id_b: dict,
    ) -> list[MicroStep]:
        return self.relationships.relate(rel_id, class_a, id_a, class_b, id_b)

    def unrelate(
        self,
        rel_id: str,
        class_a: str,
        id_a: dict,
        class_b: str,
        id_b: dict,
    ) -> list[MicroStep]:
        return self.relationships.unrelate(rel_id, class_a, id_a, class_b, id_b)

    def navigate(self, rel_id: str, from_class: str, from_id: dict) -> list[dict]:
        return self.relationships.navigate(rel_id, from_class, from_id)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_any(
        self, class_name: str, where: Callable[[dict], bool] | None = None
    ) -> dict | None:
        for inst in self.registry.lookup_all(class_name):
            if where is None or where(inst):
                return inst
        return None

    def select_many(
        self, class_name: str, where: Callable[[dict], bool] | None = None
    ) -> list[dict]:
        all_inst = self.registry.lookup_all(class_name)
        if where is None:
            return list(all_inst)
        return [i for i in all_inst if where(i)]

    # ------------------------------------------------------------------
    # Bridge / clock
    # ------------------------------------------------------------------

    def bridge(self, operation: str, args: dict | None = None) -> tuple[Any, list[MicroStep]]:
        value, step = self.bridge_registry.call(operation, dict(args or {}))
        return value, [step]

    def now(self) -> float:
        return self.clock.now()

    # ------------------------------------------------------------------
    # Scenario loading + execution
    # ------------------------------------------------------------------

    def load_scenario(self, scenario: dict) -> list[MicroStep]:
        steps: list[MicroStep] = []
        for inst in scenario.get("instances", []) or []:
            steps.extend(
                self.create_sync(
                    inst["class"],
                    inst["identifier"],
                    inst.get("initial_state"),
                    inst.get("attrs") or {},
                )
            )
        for ev in scenario.get("events", []) or []:
            target_class = ev["class"]
            target_id = ev["instance"]
            steps.extend(
                self.generate(
                    event_type=ev["event"],
                    sender_class=ev.get("sender_class", target_class),
                    sender_id=ev.get("sender_instance", target_id),
                    target_class=target_class,
                    target_id=target_id,
                    args=ev.get("args") or {},
                    delay_ms=ev.get("delay_ms"),
                )
            )
        return steps

    def execute(self) -> Generator[MicroStep, None, None]:
        self._running = True
        try:
            yield from self.scheduler.execute()
        finally:
            self._running = False


def run_simulation(
    domain_manifest: dict,
    scenario: dict | None = None,
    bridge_mocks: dict | None = None,
) -> Generator[MicroStep, None, None]:
    """Top-level entry point for running a simulation.

    Creates a SimulationContext, loads the scenario, and yields all
    micro-steps from setup and execution.
    """
    ctx = SimulationContext(domain_manifest, bridge_mocks)
    if scenario:
        for step in ctx.load_scenario(scenario):
            yield step
    yield from ctx.execute()
