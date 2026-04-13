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

    Two API shapes coexist:
    - Scenario-loading shape: explicit class/identifier args (used by load_scenario
      and test_engine.py tests).
    - Generated-code shape: instance-dict args (used by compiler-emitted Python,
      these are the ctx.create / ctx.delete / ctx.relate / ctx.traverse / etc.
      methods that operate on dicts carrying __class_name__ and __instance_key__).
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
            ctx=self,
        )
        self._running = False
        # The instance whose action is currently executing (set by scheduler
        # before invoking action_fn). Generated code uses this as implicit sender.
        self._current_instance: dict | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _instance_key_to_id_dict(self, instance_key: frozenset) -> dict:
        """Convert a frozenset instance key back to a plain dict."""
        return dict(instance_key)

    def _resolve_class_for_key(self, instance_key: frozenset) -> str | None:
        """Scan the registry to find the class that owns this instance key."""
        for class_name, bucket in self.registry._store.items():
            if instance_key in bucket:
                return class_name
        return None

    # ------------------------------------------------------------------
    # Event generation / cancellation
    # ------------------------------------------------------------------

    def generate(
        self,
        event_type: str,
        sender_class: str | None = None,
        sender_id: dict | None = None,
        target_class: str | None = None,
        target_id: dict | None = None,
        args: dict | None = None,
        delay_ms: float | None = None,
        *,
        target: frozenset | None = None,
        sender: dict | None = None,
    ) -> list[MicroStep]:
        """Enqueue an event.

        Scenario-loading shape (positional):
            generate(event_type, sender_class, sender_id, target_class, target_id, ...)

        Generated-code shape (keyword):
            generate(event_type, target=inst["__instance_key__"], args={}, sender=self_dict)
        """
        if target is not None and isinstance(target, frozenset):
            # Generated-code path: resolve class from registry
            resolved_class = self._resolve_class_for_key(target)
            if resolved_class is None:
                return []
            target_id_dict = self._instance_key_to_id_dict(target)
            # Sender: explicit kwarg > _current_instance > fallback
            sender_inst = sender if sender is not None else self._current_instance
            if sender_inst is not None:
                s_class = sender_inst.get("__class_name__", resolved_class)
                s_id = self._instance_key_to_id_dict(
                    sender_inst.get("__instance_key__", target)
                )
            else:
                s_class = resolved_class
                s_id = target_id_dict
            evt = Event(
                event_type=event_type,
                sender_class=s_class,
                sender_id=s_id,
                target_class=resolved_class,
                target_id=target_id_dict,
                args=dict(args or {}),
                delay_ms=delay_ms,
            )
        else:
            # Scenario-loading path: all positional args required
            evt = Event(
                event_type=event_type,
                sender_class=sender_class or "",
                sender_id=dict(sender_id or {}),
                target_class=target_class or "",
                target_id=dict(target_id or {}),
                args=dict(args or {}),
                delay_ms=delay_ms,
            )
        return self.scheduler.enqueue(evt)

    def cancel(
        self,
        event_type: str,
        sender_class: str | None = None,
        sender_id: dict | None = None,
        target_class: str | None = None,
        target_id: dict | None = None,
        *,
        sender: dict | None = None,
        target: dict | None = None,
    ) -> list[MicroStep]:
        """Cancel a pending delayed event.

        Scenario-loading shape: cancel(event_type, sender_class, sender_id, target_class, target_id)
        Generated-code shape: cancel(event_type, sender=sender_dict, target=target_dict)
        """
        if sender is not None and target is not None and isinstance(sender, dict):
            # Generated-code path using instance dicts
            s_class = sender.get("__class_name__", "")
            s_id = self._instance_key_to_id_dict(sender.get("__instance_key__", frozenset()))
            t_class = target.get("__class_name__", "")
            t_id = self._instance_key_to_id_dict(target.get("__instance_key__", frozenset()))
        else:
            s_class = sender_class or ""
            s_id = dict(sender_id or {})
            t_class = target_class or ""
            t_id = dict(target_id or {})
        return self.scheduler.cancel(event_type, s_class, s_id, t_class, t_id)

    # ------------------------------------------------------------------
    # Instance lifecycle — scenario-loading shape (existing API)
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
        self,
        class_name_or_inst: "str | dict",
        identifier: dict | None = None,
        sync: bool = False,
    ) -> list[MicroStep]:
        """Delete an instance.

        Scenario-loading shape: delete(class_name, identifier, sync=...)
        Generated-code shape:   delete(inst_dict)
        """
        if isinstance(class_name_or_inst, dict):
            inst = class_name_or_inst
            class_name = inst.get("__class_name__", "")
            id_dict = self._instance_key_to_id_dict(
                inst.get("__instance_key__", frozenset())
            )
            return self.registry.delete_sync(class_name, id_dict)
        # Scenario path
        class_name = class_name_or_inst
        id_dict = dict(identifier or {})
        if sync:
            return self.registry.delete_sync(class_name, id_dict)
        evt = self.registry.delete_async(class_name, id_dict)
        if evt is None:
            return []
        return self.scheduler.enqueue(evt)

    # ------------------------------------------------------------------
    # Instance lifecycle — generated-code shape (new)
    # ------------------------------------------------------------------

    def create(self, class_name: str, attrs: dict) -> dict:
        """Generated-code form. attrs must include identifier attributes.

        Determines initial_state from the ClassManifest and calls
        registry.create_sync. Returns the new instance dict (which already
        has __instance_key__ / __class_name__ set by registry).
        """
        cdef = self.registry._class_defs.get(class_name, {})
        initial_state = cdef.get("initial_state") or "Idle"
        # identifier_attrs listed in manifest — split identifier from full attrs
        id_attr_names: list[str] = cdef.get("identifier_attrs", [])
        if id_attr_names:
            identifier = {k: attrs[k] for k in id_attr_names if k in attrs}
        else:
            identifier = dict(attrs)
        self.registry.create_sync(class_name, identifier, initial_state, attrs)
        from engine.event import make_instance_key
        inst = self.registry.lookup(class_name, identifier)
        return inst  # type: ignore[return-value]

    def delete_where(self, class_name: str, predicate: Callable[[dict], bool]) -> None:
        """Delete all instances of class_name matching predicate(inst) -> bool."""
        to_delete = []
        for inst in self.registry.lookup_all(class_name):
            try:
                if predicate(inst):
                    to_delete.append(inst)
            except Exception:
                pass
        for inst in to_delete:
            id_dict = self._instance_key_to_id_dict(
                inst.get("__instance_key__", frozenset())
            )
            self.registry.delete_sync(class_name, id_dict)

    # ------------------------------------------------------------------
    # Relationships — dispatch on argument type
    # ------------------------------------------------------------------

    def relate(
        self,
        rel_id_or_a: "str | dict",
        class_a_or_b: "str | dict | None" = None,
        id_a_or_rel: "dict | str | None" = None,
        class_b: str | None = None,
        id_b: dict | None = None,
    ) -> list[MicroStep]:
        """Relate two instances.

        Scenario-loading shape: relate(rel_id, class_a, id_a, class_b, id_b)
        Generated-code shape:   relate(a_dict, b_dict, rel_id)
        """
        if isinstance(rel_id_or_a, dict):
            # Generated-code path: (a_dict, b_dict, rel_id)
            a_inst = rel_id_or_a
            b_inst = class_a_or_b  # type: ignore[assignment]
            rel_id = id_a_or_rel   # type: ignore[assignment]
            a_class = a_inst.get("__class_name__", "")
            a_id = self._instance_key_to_id_dict(a_inst.get("__instance_key__", frozenset()))
            b_class = b_inst.get("__class_name__", "")
            b_id = self._instance_key_to_id_dict(b_inst.get("__instance_key__", frozenset()))
            return self.relationships.relate(rel_id, a_class, a_id, b_class, b_id)
        # Scenario path
        return self.relationships.relate(
            rel_id_or_a,
            class_a_or_b,  # type: ignore[arg-type]
            id_a_or_rel,   # type: ignore[arg-type]
            class_b or "",
            id_b or {},
        )

    def unrelate(
        self,
        rel_id_or_a: "str | dict",
        class_a_or_b: "str | dict | None" = None,
        id_a_or_rel: "dict | str | None" = None,
        class_b: str | None = None,
        id_b: dict | None = None,
    ) -> list[MicroStep]:
        """Unrelate two instances (same dispatch pattern as relate)."""
        if isinstance(rel_id_or_a, dict):
            a_inst = rel_id_or_a
            b_inst = class_a_or_b  # type: ignore[assignment]
            rel_id = id_a_or_rel   # type: ignore[assignment]
            a_class = a_inst.get("__class_name__", "")
            a_id = self._instance_key_to_id_dict(a_inst.get("__instance_key__", frozenset()))
            b_class = b_inst.get("__class_name__", "")
            b_id = self._instance_key_to_id_dict(b_inst.get("__instance_key__", frozenset()))
            return self.relationships.unrelate(rel_id, a_class, a_id, b_class, b_id)
        return self.relationships.unrelate(
            rel_id_or_a,
            class_a_or_b,  # type: ignore[arg-type]
            id_a_or_rel,   # type: ignore[arg-type]
            class_b or "",
            id_b or {},
        )

    def navigate(self, rel_id: str, from_class: str, from_id: dict) -> list[dict]:
        """Scenario-loading shape: navigate by explicit class/id."""
        return self.relationships.navigate(rel_id, from_class, from_id)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_any(
        self, class_name: str, where: Callable[[dict], bool] | None = None
    ) -> dict | None:
        for inst in self.registry.lookup_all(class_name):
            if where is None:
                return inst
            try:
                if where(inst):
                    return inst
            except Exception:
                pass
        return None

    def select_many(
        self, class_name: str, where: Callable[[dict], bool] | None = None
    ) -> list[dict]:
        all_inst = self.registry.lookup_all(class_name)
        if where is None:
            return list(all_inst)
        result = []
        for inst in all_inst:
            try:
                if where(inst):
                    result.append(inst)
            except Exception:
                pass
        return result

    def traverse(self, source: dict, rel_chain: list[str]) -> list[dict]:
        """Navigate a chain of relationship IDs from source instance dict.

        For each hop, resolves neighbour class/id from RelationshipStore,
        then looks up the full instance dict from the registry.
        """
        class_name = source.get("__class_name__", "")
        instance_key = source.get("__instance_key__", frozenset())
        id_dict = self._instance_key_to_id_dict(instance_key)

        # frontier: list of (class_name, id_dict)
        frontier: list[tuple[str, dict]] = [(class_name, id_dict)]

        for rel_id in rel_chain:
            next_frontier: list[tuple[str, dict]] = []
            seen: set[tuple[str, Any]] = set()
            for cur_class, cur_id in frontier:
                neighbours = self.relationships.navigate(rel_id, cur_class, cur_id)
                for n in neighbours:
                    sig = (n["class"], frozenset(n["id"].items()))
                    if sig in seen:
                        continue
                    seen.add(sig)
                    next_frontier.append((n["class"], n["id"]))
            frontier = next_frontier

        # Resolve each (class, id) to a full instance dict
        result: list[dict] = []
        for cls, id_d in frontier:
            inst = self.registry.lookup(cls, id_d)
            if inst is not None:
                result.append(inst)
        return result

    def select_any_related(
        self,
        source: dict,
        rel_chain: list[str],
        where: Callable[[dict], bool] | None = None,
    ) -> dict | None:
        """Return first instance reachable via rel_chain from source, or None.

        Optional where predicate filters results before returning the first match.
        """
        result = self.traverse(source, rel_chain)
        if where is None:
            return result[0] if result else None
        for inst in result:
            try:
                if where(inst):
                    return inst
            except Exception:
                pass
        return None

    def select_many_related(
        self,
        source: dict,
        rel_chain: list[str],
        where: Callable[[dict], bool] | None = None,
    ) -> list[dict]:
        """Return all instances reachable via rel_chain from source.

        Optional where predicate filters results.
        """
        result = self.traverse(source, rel_chain)
        if where is None:
            return result
        out = []
        for inst in result:
            try:
                if where(inst):
                    out.append(inst)
            except Exception:
                pass
        return out

    # ------------------------------------------------------------------
    # Bridge / clock
    # ------------------------------------------------------------------

    def bridge(
        self,
        domain_or_op: str,
        op_or_args: "str | dict | None" = None,
        args: dict | None = None,
    ) -> "Any | tuple[Any, list[MicroStep]]":
        """Call a bridge operation.

        Old shape:  bridge(operation, args) -> (value, [step])
        New shape:  bridge(domain, op, args) -> value
        """
        if isinstance(op_or_args, str):
            # New generated-code shape: bridge(domain, op, args)
            operation = f"{domain_or_op}.{op_or_args}"
            call_args = dict(args or {})
            value, step = self.bridge_registry.call(operation, call_args)
            return value
        # Old scenario shape: bridge(operation, args)
        value, step = self.bridge_registry.call(domain_or_op, dict(op_or_args or {}))
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
