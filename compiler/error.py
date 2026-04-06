"""
compiler/error.py — Compile error dataclass and accumulator.

Per D-09: the compiler collects all errors across the entire model and raises a
single CompilationFailed exception containing the full error list.  This gives
the modeler the complete picture before reaching for the keyboard.

Exports:
    CompileError        — immutable dataclass with file, line, message
    ErrorAccumulator    — collect errors; raise_if_any() bulk-raises
    CompilationFailed   — exception type raised by raise_if_any()

Constraint (D-11): compiler/* MUST NOT import from engine/*.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompileError:
    """A single compile-time error with source location.

    Formats as ``file:line: message`` — consistent with compiler tool output
    convention (same as validate_model from Phase 3).
    """

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


class CompilationFailed(Exception):
    """Raised by ErrorAccumulator.raise_if_any() when errors have been collected.

    The exception message contains every collected error joined by newlines so
    that callers can display the full list with a single ``str(exc)``.
    """


class ErrorAccumulator:
    """Accumulates CompileError instances and raises at the end of a pass.

    Usage::

        acc = ErrorAccumulator()
        acc.add(CompileError(file="x.yaml", line=5, message="bad"))
        acc.add(CompileError(file="y.yaml", line=12, message="also bad"))
        acc.raise_if_any()  # raises CompilationFailed listing both errors
    """

    def __init__(self) -> None:
        self.errors: list[CompileError] = []

    def add(self, err: CompileError) -> None:
        """Append a single CompileError."""
        self.errors.append(err)

    def extend(self, errs: list[CompileError]) -> None:
        """Append a list of CompileErrors."""
        self.errors.extend(errs)

    def raise_if_any(self) -> None:
        """If any errors were collected, raise CompilationFailed with all messages.

        No-op when the error list is empty.
        """
        if not self.errors:
            return
        lines = [str(e) for e in self.errors]
        raise CompilationFailed("\n".join(lines))
