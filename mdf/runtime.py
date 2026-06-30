"""mdf/runtime.py — Runtime dispatch helpers for MDF-compiled action code."""
from __future__ import annotations


def _mdf_remove(container: object, item: object) -> None:
    """MDF remove() dispatch — Map -> dict.pop, Set -> set.discard, List -> list.remove."""
    if isinstance(container, dict):
        container.pop(item, None)  # type: ignore[call-arg]
    elif isinstance(container, set):
        container.discard(item)  # type: ignore[arg-type]
    elif isinstance(container, list):
        try:
            container.remove(item)  # type: ignore[arg-type]
        except ValueError:
            pass
    else:
        raise TypeError(
            f"_mdf_remove: unsupported container type {type(container).__name__}"
        )
