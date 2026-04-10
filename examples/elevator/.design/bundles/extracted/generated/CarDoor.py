# from elevator/CarDoor.yaml:0
"""Generated module for class CarDoor."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


# from elevator/CarDoor.yaml:0
def action_Closed_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    elev = ctx.traverse(self_dict, ["R7"])
    ctx.generate("Door_closed", target=elev["__instance_key__"], args={})


# from elevator/CarDoor.yaml:0
def action_Closing_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    pass


# from elevator/CarDoor.yaml:0
def action_Open_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    ctx.generate(
        "Close_cmd",
        target=self_dict["__instance_key__"],
        args={},
        delay_ms=int(5 * 1000),
    )


# from elevator/CarDoor.yaml:0
def action_Opening_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    pass


TRANSITION_TABLE: dict = {
    ("Closed", "Closed_now"): {
        "next_state": "Closed",
        "action_fn": action_Closed_entry,
        "guard_fn": None,
    },
    ("Closed", "Open_cmd"): {
        "next_state": "Opening",
        "action_fn": action_Closed_entry,
        "guard_fn": None,
    },
    ("Closing", "Closed_now"): {
        "next_state": "Closed",
        "action_fn": action_Closing_entry,
        "guard_fn": None,
    },
    ("Open", "Close_cmd"): {
        "next_state": "Closing",
        "action_fn": action_Open_entry,
        "guard_fn": None,
    },
    ("Opening", "Opened"): {
        "next_state": "Open",
        "action_fn": action_Opening_entry,
        "guard_fn": None,
    },
}
