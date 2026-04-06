"""Domain manifest TypedDict spec for the MDF simulation engine.

The manifest is the compiled, runtime-ready view of a domain's structural and
behavioural model. It is produced upstream by the compilation pipeline (Phase 5
proper) and consumed by the runtime registry, scheduler, and dispatcher.

This module defines TypedDicts only — no parsing, no validation, no I/O — so
that engine/* stays free of schema/, tools/, and pycca/ imports per D-37.
"""
from __future__ import annotations

from typing import Any, Callable, NotRequired, TypedDict


class TransitionEntry(TypedDict):
    next_state: str | None
    action_fn: Callable | None
    guard_fn: Callable | None


class ClassManifest(TypedDict):
    name: str
    is_abstract: bool
    identifier_attrs: list[str]
    attributes: dict[str, Any]
    initial_state: str | None
    final_states: list[str]
    transition_table: dict[tuple[str, str], TransitionEntry]
    supertype: str | None
    subtypes: list[str]
    senescent_states: NotRequired[set[str]]


class AssociationManifest(TypedDict):
    rel_id: str
    class_a: str
    class_b: str
    mult_a_to_b: str
    mult_b_to_a: str


class DomainManifest(TypedDict):
    class_defs: dict[str, ClassManifest]
    associations: dict[str, AssociationManifest]
    generalizations: dict[str, list[str]]
