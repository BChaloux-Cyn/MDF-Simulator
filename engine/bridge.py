"""Bridge mock registry for the MDF simulation engine.

Per CONTEXT.md decisions D-29 and D-30:

- D-29: Bridge operations are mocked from a YAML file mapping
  {operation_name: return_value}. Loaded once at simulation startup.
- D-30: Undefined operations return None without raising — they are
  recorded as a BridgeCalled micro-step with mock_return=None so the
  trace still captures the call.

Per threat model T-5.1-01: YAML loading uses yaml.safe_load() only,
never yaml.load(), to prevent arbitrary Python object instantiation.

This module has no imports from schema/, tools/, or pycca/ (SC-11).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from engine.microstep import BridgeCalled


class BridgeMockRegistry:
    """Registry of mocked bridge operations.

    Maps operation name -> return value. Calls record a BridgeCalled
    micro-step regardless of whether the operation is defined.
    """

    def __init__(self, mocks: dict[str, Any] | None = None):
        self._mocks: dict[str, Any] = dict(mocks) if mocks else {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BridgeMockRegistry":
        """Load mock registry from a YAML file.

        Uses yaml.safe_load() per T-5.1-01 — never yaml.load().
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(
                f"bridge mock YAML must be a mapping, got {type(data).__name__}"
            )
        return cls(mocks=data)

    def call(
        self, operation: str, args: dict[str, Any]
    ) -> tuple[Any, BridgeCalled]:
        """Call a bridge operation.

        Returns (return_value, BridgeCalled micro-step). Undefined
        operations return None per D-30.
        """
        mock_return = self._mocks.get(operation, None)
        step = BridgeCalled(
            operation=operation,
            args=args,
            mock_return=mock_return,
        )
        return mock_return, step
