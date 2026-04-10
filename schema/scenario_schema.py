"""Pydantic v2 schema for .scenario.yaml files (Phase 5.3).

Design decisions (05.3-CONTEXT.md):
  D-08: Scenario files live in .design/scenarios/ with .scenario.yaml extension.
  D-09: Validated by Pydantic before simulation starts; validation errors are hard failures.
  D-10: No domain field — domain is supplied by the tool argument.
  D-11: Instances have a name alias local to the scenario file.
  D-12: Initial relationships expressed as top-level relationships list.
  D-15: sender is always required for all events and trigger actions.
  D-16: at_ms and after_ms are mutually exclusive.
  D-19: Trigger conditions can test instance state and/or attribute values.
  D-20: Trigger action uses same format as EventDef (event or call, sender required).

Security (T-5.3-04): YAML loaded with yaml.safe_load, then validated here before use.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InstanceDef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(alias="class")
    name: str
    id: dict[str, Any]
    state: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)


class RelationshipInit(BaseModel):
    rel: str
    a: str  # instance name alias (side A)
    b: str  # instance name alias (side B)


class EventDef(BaseModel):
    """A scenario event or method call entry.

    Exactly one of event/call is required. sender is always required (D-15).
    at_ms and after_ms are mutually exclusive (D-16).
    """
    model_config = ConfigDict(populate_by_name=True)

    event: str | None = None
    call: str | None = None
    target: str
    sender: str  # Required — D-15
    args: dict[str, Any] = Field(default_factory=dict)
    at_ms: float | None = None
    after_ms: float | None = None

    @model_validator(mode="after")
    def _event_xor_call(self) -> "EventDef":
        if (self.event is None) == (self.call is None):
            raise ValueError("EventDef requires exactly one of 'event' or 'call'")
        return self

    @model_validator(mode="after")
    def _at_ms_xor_after_ms(self) -> "EventDef":
        if self.at_ms is not None and self.after_ms is not None:
            raise ValueError("EventDef 'at_ms' and 'after_ms' are mutually exclusive (D-16)")
        return self


class TriggerCondition(BaseModel):
    """When-condition for a trigger (D-19).

    At least one of state or attr must be specified. When attr is present, eq is required.
    """
    instance: str
    state: str | None = None
    attr: str | None = None
    eq: Any = None

    @model_validator(mode="after")
    def _at_least_one_condition(self) -> "TriggerCondition":
        if self.state is None and self.attr is None:
            raise ValueError("TriggerCondition requires at least one of 'state' or 'attr'")
        if self.attr is not None and self.eq is None:
            raise ValueError("TriggerCondition with 'attr' requires 'eq'")
        return self


class TriggerAction(BaseModel):
    """Then-action for a trigger (D-20).

    Exactly one of event/call is required. sender is always required (D-15).
    """
    event: str | None = None
    call: str | None = None
    target: str
    sender: str  # Required — D-15
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _event_xor_call(self) -> "TriggerAction":
        if (self.event is None) == (self.call is None):
            raise ValueError("TriggerAction requires exactly one of 'event' or 'call'")
        return self


class TriggerDef(BaseModel):
    """Conditional trigger evaluated after each micro-step (D-18, D-19, D-21)."""
    when: TriggerCondition
    then: TriggerAction
    repeat: bool = False


class ScenarioDef(BaseModel):
    """Top-level scenario definition.

    Validated by Pydantic from a .scenario.yaml file before simulation starts (D-09).
    """
    model_config = ConfigDict(populate_by_name=True)

    instances: list[InstanceDef] = Field(default_factory=list)
    relationships: list[RelationshipInit] = Field(default_factory=list)
    events: list[EventDef] = Field(default_factory=list)
    triggers: list[TriggerDef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_instance_names(self) -> "ScenarioDef":
        names = [i.name for i in self.instances]
        if len(names) != len(set(names)):
            raise ValueError("Scenario instance names must be unique")
        return self
