"""Scenario runner: alias resolution, event dispatch, trigger interleaving.

Drives scenario execution against a SimulationContext:
  1. Creates instances and builds alias -> instance_dict map
  2. Forces initial states from scenario (overriding class default)
  3. Applies initial relationships via ctx.relate()
  4. Enqueues scenario events (respecting at_ms / after_ms timing)
  5. Drives ctx.execute() with trigger evaluation after each micro-step
  6. Fires trigger actions into the same ctx

Security (T-5.3-11): trigger fire cap enforced by TriggerEvaluator.

Engine isolation (D-37): This module does NOT import from schema/, tools/, or
pycca/. ScenarioDef and related types are accepted as duck-typed objects.
"""
from __future__ import annotations

from typing import Any

from engine.trigger import TriggerEvaluator


def run_scenario(ctx, scenario: Any, manifest: dict):
    """Generator yielding MicroStep records from full scenario execution.

    Args:
        ctx: SimulationContext — must be freshly constructed.
        scenario: Validated ScenarioDef (duck-typed) from a .scenario.yaml file.
        manifest: DomainManifest dict (used for method dispatch in trigger actions).

    Yields:
        MicroStep records from ctx.execute() and trigger-fired events.
    """
    aliases: dict[str, dict] = {}

    # Step 1: Create instances; force initial state from scenario if specified
    for inst_def in scenario.instances:
        # Merge identifier + attrs into a single dict for ctx.create()
        all_attrs = {**inst_def.id, **inst_def.attrs}
        inst = ctx.create(inst_def.class_name, all_attrs)

        # Override initial state if the scenario specifies one
        if inst_def.state is not None:
            id_dict = dict(inst_def.id)
            ctx.registry.set_state(inst_def.class_name, id_dict, inst_def.state)
            inst["curr_state"] = inst_def.state

        aliases[inst_def.name] = inst

    # Step 2: Apply initial relationships
    for rel in scenario.relationships:
        a_inst = aliases[rel.a]
        b_inst = aliases[rel.b]
        ctx.relate(a_inst, b_inst, rel.rel)

    # Step 3: Enqueue scenario events with timing
    current_time = 0.0
    for ev in scenario.events:
        if ev.at_ms is not None:
            fire_time = ev.at_ms
        elif ev.after_ms is not None:
            fire_time = current_time + ev.after_ms
        else:
            fire_time = current_time
        current_time = fire_time

        target_inst = aliases[ev.target]
        sender_inst = aliases[ev.sender]

        if ev.event:
            ctx.generate(
                ev.event,
                target=target_inst["__instance_key__"],
                args=ev.args,
                sender=sender_inst,
                delay_ms=fire_time if fire_time > 0.0 else None,
            )
        elif ev.call:
            _invoke_method(ctx, sender_inst, target_inst, ev.call, ev.args, manifest)

    # Step 4: Drive execution with trigger evaluation after each micro-step
    evaluator = TriggerEvaluator(scenario.triggers, aliases)
    for step in ctx.execute():
        yield step
        for trig_def in evaluator.evaluate(ctx):
            _fire_trigger_action(ctx, trig_def.then, aliases, manifest)


def _fire_trigger_action(ctx, action: Any, aliases: dict, manifest: dict) -> None:
    """Post a trigger's then-action into the running ctx."""
    target = aliases[action.target]
    sender = aliases[action.sender]
    if action.event:
        ctx.generate(
            action.event,
            target=target["__instance_key__"],
            args=action.args,
            sender=sender,
        )
    elif action.call:
        _invoke_method(ctx, sender, target, action.call, action.args, manifest)


def _invoke_method(ctx, sender: dict, target: dict, method_name: str, args: dict, manifest: dict) -> None:
    """Execute a class method action body directly (D-17).

    Looks up method_fn from the manifest's class_defs and calls it with
    the correct ctx, self_dict (target), and args.
    """
    class_name = target.get("__class_name__", "")
    cls_def = manifest.get("class_defs", {}).get(class_name, {})
    methods: dict = cls_def.get("methods", {})
    method_fn = methods.get(method_name)
    if method_fn is None:
        raise RuntimeError(
            f"Method {class_name}.{method_name} not found in manifest for class {class_name!r}"
        )
    old_current = ctx._current_instance
    ctx._current_instance = sender
    try:
        method_fn(ctx, target, args)
    finally:
        ctx._current_instance = old_current
