"""Simulation clock for the MDF simulation engine.

Per design doc rules 20-22 and CONTEXT.md decisions D-31 through D-34:

- Tracks simulation time in milliseconds, independent of wall clock (D-31).
- speed_multiplier scales delay-queue expiry only — it does NOT speed up
  action execution (D-32).
- Supports pause / resume; advance() is a no-op while paused (D-33).
- now() returns current simulation time as a float in milliseconds (D-34).

This module has no imports from schema/, tools/, or pycca/ (SC-11).
"""
from __future__ import annotations


class SimulationClock:
    """Simulation clock tracking sim time in milliseconds."""

    def __init__(self, speed_multiplier: float = 1.0):
        self._time_ms: float = 0.0
        self._speed_multiplier: float = speed_multiplier
        self._paused: bool = False

    def now(self) -> float:
        """Return current simulation time in milliseconds (D-34)."""
        return self._time_ms

    def advance(self, delta_ms: float) -> None:
        """Advance simulation time by delta_ms * speed_multiplier.

        No-op if paused (D-33). Speed multiplier affects only delay-queue
        expiry, not action execution speed (D-32).
        """
        if not self._paused:
            self._time_ms += delta_ms * self._speed_multiplier

    def pause(self) -> None:
        """Pause the clock (D-33). Consumed by debugger in plans 5.4 / 5.5."""
        self._paused = True

    def resume(self) -> None:
        """Resume the clock (D-33)."""
        self._paused = False

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def speed_multiplier(self) -> float:
        return self._speed_multiplier

    @speed_multiplier.setter
    def speed_multiplier(self, value: float) -> None:
        self._speed_multiplier = value
