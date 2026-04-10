# from elevator/DestFloorButton.yaml:0
"""Generated module for class DestFloorButton."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


# from elevator/DestFloorButton.yaml:0
def action_Idle_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    pass


# from elevator/DestFloorButton.yaml:0
def action_Lit_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    pass


TRANSITION_TABLE: dict = {
    ("Idle", "Activated"): {
        "next_state": "Lit",
        "action_fn": action_Idle_entry,
        "guard_fn": None,
    },
    ("Lit", "Floor_served"): {
        "next_state": "Idle",
        "action_fn": action_Lit_entry,
        "guard_fn": None,
    },
}
