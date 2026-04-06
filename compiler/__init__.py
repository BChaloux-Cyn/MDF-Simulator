"""
compiler/__init__.py — Public API for the MDF model compiler.

CONSTRAINT (D-11): This package MUST NOT import from engine/*.
  - compiler/ may import from schema/ (to load YAML) and pycca/ (to parse action bodies).
  - Generated code imports engine/; the compiler itself does not.
  - Future contributors: enforce this rule at review time and in CI.

Public surface:
    compile_model(model_root, output_dir) -> Path  — placeholder; filled in by Plan 04
    CompileError                                    — immutable error dataclass
    ErrorAccumulator                                — collect + bulk-raise errors
"""
from __future__ import annotations

from pathlib import Path

from compiler.error import CompileError, CompilationFailed, ErrorAccumulator

__all__ = [
    "compile_model",
    "CompileError",
    "CompilationFailed",
    "ErrorAccumulator",
]


def compile_model(model_root: Path, output_dir: Path) -> Path:
    """Compile an MDF domain model to a self-contained ``.mdfbundle``.

    Args:
        model_root: Path to the domain model root directory
                    (e.g. ``examples/elevator/.design/model/Elevator``).
        output_dir: Directory where the bundle will be written.

    Returns:
        Path to the generated ``.mdfbundle`` file.

    Raises:
        NotImplementedError: Always — this placeholder is filled in by Plan 04.
        CompilationFailed:   When the model contains compile errors (Plan 04).
    """
    raise NotImplementedError("compile_model: filled in by Plan 04")
