# from elevator/Elevator.yaml:0
"""Generated module for class Elevator."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


# from elevator/Elevator.yaml:0
def action_Arriving_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    pass


# from elevator/Elevator.yaml:0
def action_Departing_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    self_dict["next_stop_floor"] = params["floor_num"]
    if self_dict["next_stop_floor"] > self_dict["current_floor"]:
        self_dict["direction"] = Up
    else:
        self_dict["direction"] = Down
    ctx.generate("Ready", target=self_dict["__instance_key__"], args={})


# from elevator/Elevator.yaml:0
def action_Exchanging_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    pass


# from elevator/Elevator.yaml:0
def action_Floor_Updating_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    self_dict["current_floor"] = params["floor_num"]
    if self_dict["current_floor"] == self_dict["next_stop_floor"]:
        ctx.generate("At_Destination", target=self_dict["__instance_key__"], args={})
    else:
        ctx.generate("Continue", target=self_dict["__instance_key__"], args={})


# from elevator/Elevator.yaml:0
def action_Idle_entry(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    pass


# from elevator/Elevator.yaml:0
def action_Moving_entry(
    ctx: "SimulationContext", self_dict: dict, params: dict
) -> None:
    pass


# from elevator/Elevator.yaml:0
def guard_Exchanging_Door_closed(self_dict: dict, params: dict) -> bool:
    return self_dict["next_stop_floor"] == self_dict["current_floor"]


TRANSITION_TABLE: dict = {
    ("Arriving", "Arrived"): {
        "next_state": "Exchanging",
        "action_fn": action_Arriving_entry,
        "guard_fn": None,
    },
    ("Departing", "Ready"): {
        "next_state": "Moving",
        "action_fn": action_Departing_entry,
        "guard_fn": None,
    },
    ("Exchanging", "Door_closed"): {
        "next_state": "Idle",
        "action_fn": action_Exchanging_entry,
        "guard_fn": guard_Exchanging_Door_closed,
    },
    ("Exchanging", "Floor_assigned"): {
        "next_state": "Exchanging",
        "action_fn": action_Exchanging_entry,
        "guard_fn": None,
    },
    ("Floor_Updating", "At_Destination"): {
        "next_state": "Arriving",
        "action_fn": action_Floor_Updating_entry,
        "guard_fn": None,
    },
    ("Floor_Updating", "Continue"): {
        "next_state": "Moving",
        "action_fn": action_Floor_Updating_entry,
        "guard_fn": None,
    },
    ("Idle", "Door_closed"): {
        "next_state": "Idle",
        "action_fn": action_Idle_entry,
        "guard_fn": None,
    },
    ("Idle", "Floor_assigned"): {
        "next_state": "Departing",
        "action_fn": action_Idle_entry,
        "guard_fn": None,
    },
    ("Moving", "Floor_reached"): {
        "next_state": "Floor_Updating",
        "action_fn": action_Moving_entry,
        "guard_fn": None,
    },
}
