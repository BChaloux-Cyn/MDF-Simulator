"""Conditional trigger evaluation (D-18..D-21).

Triggers are evaluated after each micro-step during scenario execution.
A trigger fires when its `when` condition is fully satisfied (AND logic for
state + attr checks, per D-19). Triggers with repeat=False are disarmed after
the first fire; repeat=True triggers re-arm automatically.

Security (T-5.3-11): total fire count is capped at TRIGGER_FIRE_LIMIT to
prevent infinite loops from repeat:true triggers that always match.

Engine isolation (D-37): This module does NOT import from schema/, tools/, or
pycca/. TriggerDef and related types are accepted as plain `object` and accessed
via duck typing (attribute access on Pydantic model instances is fine at runtime).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRIGGER_FIRE_LIMIT = 10_000


@dataclass
class ArmedTrigger:
    definition: Any  # TriggerDef duck type — avoids schema/ import
    armed: bool = True
    fire_count: int = 0


class TriggerEvaluator:
    """Evaluates a list of TriggerDef conditions after each micro-step.

    Instance dicts are accessed directly (inst["curr_state"], inst[attr]) —
    no registry lookup needed since aliases already point to live instance dicts.
    """

    def __init__(self, triggers: list, alias_to_instance: dict[str, dict]):
        """
        Args:
            triggers: List of TriggerDef (duck-typed) from the scenario.
            alias_to_instance: Maps scenario instance name -> live instance dict.
        """
        self.armed: list[ArmedTrigger] = [ArmedTrigger(t) for t in triggers]
        self.aliases: dict[str, dict] = alias_to_instance
        self.total_fires: int = 0

    def evaluate(self, ctx) -> list:
        """Evaluate all armed triggers; return those that match now.

        Disarms non-repeat triggers after selection. Raises RuntimeError
        if total fires exceed TRIGGER_FIRE_LIMIT (T-5.3-11).

        Args:
            ctx: SimulationContext (passed for future extensibility; not used
                 directly since state/attrs are read from instance dicts).

        Returns:
            List of TriggerDef that fired this evaluation pass.
        """
        to_fire: list = []
        for at in self.armed:
            if not at.armed:
                continue
            if self._matches(at.definition, ctx):
                to_fire.append(at.definition)
                at.fire_count += 1
                self.total_fires += 1
                if not at.definition.repeat:
                    at.armed = False
        if self.total_fires > TRIGGER_FIRE_LIMIT:
            raise RuntimeError(
                f"Trigger fire limit {TRIGGER_FIRE_LIMIT} exceeded — possible infinite loop"
            )
        return to_fire

    def _matches(self, trig: Any, ctx) -> bool:
        """Return True if all conditions in trig.when are satisfied (AND logic)."""
        cond = trig.when
        inst = self.aliases.get(cond.instance)
        if inst is None:
            return False

        # State condition: compare against inst["curr_state"]
        if cond.state is not None:
            current_state = inst.get("curr_state")
            if current_state != cond.state:
                return False

        # Attribute condition: compare inst[attr] against eq value
        if cond.attr is not None:
            if inst.get(cond.attr) != cond.eq:
                return False

        return True
