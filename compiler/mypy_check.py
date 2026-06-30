"""compiler/mypy_check.py — Run mypy on generated sources and map errors to MDF source."""
from __future__ import annotations

import re
from pathlib import Path

from mypy import api as mypy_api

from compiler.error import CompileError

_MYPY_ERROR_RE = re.compile(r"^(.+?):(\d+): error: (.+)$")
_SOURCE_COMMENT_RE = re.compile(r"^# from (.+?):(\d+)\s*$")


def check_generated_files(paths: list[str]) -> list[CompileError]:
    """Run mypy on generated Python source files and return mapped CompileErrors.

    Args:
        paths: file paths to generated .py files (already written to disk).

    Returns:
        List of CompileErrors with MDF source file/line recovered from
        ``# from <file>:<line>`` comments (D-05).
    """
    if not paths:
        return []

    stdout, _stderr, exit_code = mypy_api.run([
        "--no-error-summary",
        "--ignore-missing-imports",
        "--follow-imports=skip",
        "--no-incremental",
        *paths,
    ])

    if exit_code == 0:
        return []

    source_maps = {p: _build_source_map(p) for p in paths}
    return _parse_mypy_output(stdout, source_maps)


def _build_source_map(path: str) -> list[tuple[int, str, int]]:
    """Return (gen_line, mdf_file, mdf_line) for each ``# from`` comment."""
    result: list[tuple[int, str, int]] = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return result
    for i, line in enumerate(lines, start=1):
        m = _SOURCE_COMMENT_RE.match(line)
        if m:
            result.append((i, m.group(1), int(m.group(2))))
    return result


def _resolve_source(
    lineno: int,
    source_map: list[tuple[int, str, int]],
) -> tuple[str, int]:
    """Find the nearest ``# from`` comment at or before lineno."""
    best_file, best_line = "<generated>", 0
    for gen_line, mdf_file, mdf_line in source_map:
        if gen_line <= lineno:
            best_file, best_line = mdf_file, mdf_line
        else:
            break
    return best_file, best_line


def _parse_mypy_output(
    stdout: str,
    source_maps: dict[str, list[tuple[int, str, int]]],
) -> list[CompileError]:
    """Parse mypy stdout and return CompileErrors with MDF locations."""
    errors: list[CompileError] = []
    for line in stdout.splitlines():
        m = _MYPY_ERROR_RE.match(line)
        if not m:
            continue
        gen_file, lineno_str, message = m.groups()
        lineno = int(lineno_str)
        # Normalize path separators for lookup
        normalized = gen_file.replace("\\", "/")
        source_map: list[tuple[int, str, int]] = []
        for key, smap in source_maps.items():
            if key.replace("\\", "/") == normalized:
                source_map = smap
                break
        if not source_map:
            # Try exact key match as fallback
            source_map = source_maps.get(gen_file, [])
        mdf_file, mdf_line = _resolve_source(lineno, source_map)
        errors.append(CompileError(file=mdf_file, line=mdf_line, message=message))
    return errors
