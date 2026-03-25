"""Canonical JSON schemas for drawio content comparison.

These Pydantic models define the intermediate representation used to
compare YAML source against existing drawio files. Both sides decompose
into the same structure; string comparison of the serialized JSON
determines whether a diagram needs to be re-rendered.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# State diagram canonical models
# ---------------------------------------------------------------------------

class CanonicalState(BaseModel):
    name: str
    entry_action: str | None


class CanonicalTransition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_state: str = Field(alias="from")
    to: str
    event: str
    params: str | None
    guard: str | None


class CanonicalStateDiagram(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["state_diagram"]
    domain: str
    class_name: str = Field(alias="class")
    initial_state: str
    states: list[CanonicalState]
    transitions: list[CanonicalTransition]


# ---------------------------------------------------------------------------
# Class diagram canonical models
# ---------------------------------------------------------------------------

class CanonicalClassEntry(BaseModel):
    name: str
    stereotype: str
    specializes: str | None
    attributes: list[str]
    methods: list[str]


class CanonicalAssociation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    point_1: str
    point_2: str
    mult_1_2: str = Field(alias="1_mult_2")
    mult_2_1: str = Field(alias="2_mult_1")
    phrase_1_2: str = Field(alias="1_phrase_2")
    phrase_2_1: str = Field(alias="2_phrase_1")


class CanonicalGeneralization(BaseModel):
    name: str
    supertype: str
    subtypes: list[str]


class CanonicalClassDiagram(BaseModel):
    type: Literal["class_diagram"]
    domain: str
    classes: list[CanonicalClassEntry]
    associations: list[CanonicalAssociation]
    generalizations: list[CanonicalGeneralization]
