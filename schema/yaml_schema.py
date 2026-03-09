"""
YAML model schema — Pydantic v2 models for all MDF YAML file types.
Implemented in plan 02 (01-02-PLAN.md).
"""
import re
from itertools import groupby
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Semver validation
# ---------------------------------------------------------------------------

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class SchemaVersionMixin(BaseModel):
    """Mixin that adds a required, semver-validated schema_version field."""

    schema_version: str  # Required — no default

    @field_validator("schema_version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not SEMVER_RE.match(v):
            raise ValueError(
                f"schema_version must be semver (e.g. '1.0.0'), got: {v!r}"
            )
        return v


# ---------------------------------------------------------------------------
# DOMAINS.yaml models
# ---------------------------------------------------------------------------


class DomainEntry(BaseModel):
    name: str
    type: Literal["application", "realized"]
    description: str


class OperationParam(BaseModel):
    name: str
    type: str


class BridgeOperation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    params: list[OperationParam] = []
    return_type: str | None = Field(default=None, alias="return")


class BridgeEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_domain: str = Field(alias="from")
    to: str
    operations: list[BridgeOperation]


class DomainsFile(SchemaVersionMixin):
    domains: list[DomainEntry]
    bridges: list[BridgeEntry] = []


# ---------------------------------------------------------------------------
# types.yaml models
# ---------------------------------------------------------------------------

_SCALAR_PRIMITIVES = frozenset(
    {"Boolean", "Integer", "Real", "String", "UniqueID"}
)


class EnumType(BaseModel):
    name: str
    base: Literal["enum"]
    values: list[str]
    description: str | None = None


class StructField(BaseModel):
    name: str
    type: str


class StructType(BaseModel):
    name: str
    base: Literal["struct"]
    description: str | None = None
    fields: list[StructField]


class ScalarType(BaseModel):
    """Fallback type — base must be one of the five xtUML primitives."""

    name: str
    base: str
    units: str | None = None
    range: list[float] | None = None
    description: str | None = None

    @model_validator(mode="after")
    def check_base_is_primitive(self) -> "ScalarType":
        if self.base not in _SCALAR_PRIMITIVES:
            raise ValueError(
                f"ScalarType.base must be one of {sorted(_SCALAR_PRIMITIVES)}, got: {self.base!r}"
            )
        return self


# Plain union — ScalarType is last (fallback). Cannot use discriminator
# because ScalarType.base accepts any of 5 primitives, not a single Literal.
# Pydantic tries each member left-to-right; ScalarType model_validator
# rejects invalid primitives after EnumType/StructType both fail.
TypeDef = Union[EnumType, StructType, ScalarType]


class TypesFile(SchemaVersionMixin):
    domain: str
    types: list[TypeDef]


# ---------------------------------------------------------------------------
# class-diagram.yaml models
# ---------------------------------------------------------------------------


class Attribute(BaseModel):
    name: str
    type: str
    visibility: Literal["public", "private", "protected"] = "private"
    scope: Literal["instance", "class"] = "instance"
    identifier: bool = False
    referential: str | None = None


class MethodParam(BaseModel):
    name: str
    type: str


class Method(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    visibility: Literal["public", "private", "protected"] = "private"
    scope: Literal["instance", "class"]
    params: list[MethodParam] = []
    return_type: str | None = Field(default=None, alias="return")
    action: str | None = None


class SubtypePartition(BaseModel):
    name: str  # R-number, e.g. "R2"
    discriminator: str
    subtypes: list[str]


class ClassDef(BaseModel):
    name: str
    stereotype: Literal["entity", "active", "associative"]
    specializes: str | None = None
    formalizes: str | None = None
    partitions: list[SubtypePartition] | None = None
    attributes: list[Attribute] = []
    methods: list[Method] = []

    @model_validator(mode="after")
    def check_associative_has_formalizes(self) -> "ClassDef":
        if self.stereotype == "associative" and self.formalizes is None:
            raise ValueError(
                f"Class {self.name!r}: stereotype 'associative' requires a 'formalizes' field"
            )
        return self


class BridgeImplementation(BaseModel):
    name: str
    action: str


class RequiredBridge(BaseModel):
    to_domain: str
    direction: Literal["required"]
    operations: list[str]


class ProvidedBridge(BaseModel):
    to_domain: str
    direction: Literal["provided"]
    implementations: list[BridgeImplementation]


BridgeStanza = Annotated[
    Union[RequiredBridge, ProvidedBridge],
    Field(discriminator="direction"),
]


class Association(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str  # R-number
    point_1: str
    point_2: str
    mult_1_to_2: str = Field(alias="1_mult_2")
    mult_2_to_1: str = Field(alias="2_mult_1")
    phrase_1_to_2: str = Field(alias="1_phrase_2")
    phrase_2_to_1: str = Field(alias="2_phrase_1")


class ClassDiagramFile(SchemaVersionMixin):
    domain: str
    classes: list[ClassDef] = []
    associations: list[Association] = []
    bridges: list[BridgeStanza] = []


# ---------------------------------------------------------------------------
# state-diagrams/<Class>.yaml models
# ---------------------------------------------------------------------------


class EventParam(BaseModel):
    name: str
    type: str


class EventDef(BaseModel):
    name: str
    params: list[EventParam] = []


class StateDef(BaseModel):
    name: str
    entry_action: str | None = None


class Transition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_state: str = Field(alias="from")
    to: str
    event: str
    guard: str | None = None
    action: str | None = None


class StateDiagramFile(SchemaVersionMixin):
    model_config = ConfigDict(populate_by_name=True)

    domain: str
    class_name: str = Field(alias="class")
    events: list[EventDef] = []
    states: list[StateDef]
    transitions: list[Transition] = []

    @model_validator(mode="after")
    def check_guard_consistency(self) -> "StateDiagramFile":
        key = lambda t: (t.from_state, t.event)  # noqa: E731
        for (from_state, event), group in groupby(
            sorted(self.transitions, key=key), key=key
        ):
            ts = list(group)
            guarded = [t for t in ts if t.guard is not None]
            if guarded and len(guarded) != len(ts):
                raise ValueError(
                    f"Transitions from '{from_state}' on '{event}': "
                    f"mix of guarded and unguarded — all must have guards"
                )
        return self
