# from elevator/ShaftDoor.yaml:0
"""Generated module for class ShaftDoor."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


# from elevator/ShaftDoor.yaml:0
def action_Closed_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    cd = ctx.traverse(self_dict, ["R8", "R2", "R1", "R7"])
    ctx.generate("Closed_now", target=cd["__instance_key__"], args={})


# from elevator/ShaftDoor.yaml:0
def action_Closing_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    ctx.generate(
        "Done_closing",
        target=self_dict["__instance_key__"],
        args={},
        delay_ms=int(10 * 1000),
    )


# from elevator/ShaftDoor.yaml:0
def action_Open_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    cd = ctx.traverse(self_dict, ["R8", "R2", "R1", "R7"])
    ctx.generate("Opened", target=cd["__instance_key__"], args={})


# from elevator/ShaftDoor.yaml:0
def action_Opening_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    ctx.generate(
        "Done_opening",
        target=self_dict["__instance_key__"],
        args={},
        delay_ms=int(10 * 1000),
    )


TRANSITION_TABLE: dict = {
    ("Closed", "Open_cmd"): {
        "next_state": "Opening",
        "action_fn": action_Closed_entry,
        "guard_fn": None,
    },
    ("Closing", "Done_closing"): {
        "next_state": "Closed",
        "action_fn": action_Closing_entry,
        "guard_fn": None,
    },
    ("Open", "Close_cmd"): {
        "next_state": "Closing",
        "action_fn": action_Open_entry,
        "guard_fn": None,
    },
    ("Opening", "Done_opening"): {
        "next_state": "Open",
        "action_fn": action_Opening_entry,
        "guard_fn": None,
    },
}
