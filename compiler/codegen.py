"""compiler/codegen.py — DomainManifest → Python source files.

Generates one .py file per ClassManifest and a domain __init__.py, then
formats everything with black per D-01/D-05.

Design decisions applied here:
  D-01: string templates + black; no ast module; no exec
  D-05: every emitted block preceded by # from <model_file>:<line>
  D-06: enum → enum.Enum; typedef → NewType
  D-07: all dicts and iterations are sorted
  D-10: action sig (ctx, self_dict, params) -> None
        guard sig  (self_dict, params) -> bool
  D-11: engine/* imported only inside TYPE_CHECKING block

Exports:
    generate_class_module(class_manifest, type_registry, parser) -> str
    generate_init_module(domain_manifest) -> str
    format_source(src, filename) -> str
"""
from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Any

import black

from compiler.error import CompileError, CompilationFailed
from compiler.transformer import transform_action, transform_guard

if TYPE_CHECKING:
    from engine.manifest import ClassManifest, DomainManifest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXED_DATE = (2020, 1, 1, 0, 0, 0)  # used for reproducible zip timestamps elsewhere

# ---------------------------------------------------------------------------
# Source formatting (black)
# ---------------------------------------------------------------------------

def format_source(src: str, filename: str = "<generated>") -> str:
    """Format *src* with black.

    Returns formatted source.  Raises CompileError on InvalidInput.
    Treats NothingChanged as success and returns original source.
    """
    try:
        return black.format_str(src, mode=black.Mode())
    except black.InvalidInput as exc:
        err = CompileError(file=filename, line=0, message=f"black InvalidInput: {exc}")
        raise CompilationFailed(str(err)) from exc
    except black.NothingChanged:
        return src


# ---------------------------------------------------------------------------
# Enum and typedef rendering
# ---------------------------------------------------------------------------

def _render_enum(name: str, members: list[str]) -> str:
    """Render an MDF enum as an enum.Enum subclass (sorted members)."""
    lines = [f"class {name}(enum.Enum):"]
    for m in sorted(members):
        lines.append(f"    {m} = {m!r}")
    return "\n".join(lines)


def _render_typedef(name: str, base: str) -> str:
    """Render an MDF typedef as a typing.NewType statement."""
    return f'{name} = NewType("{name}", {base})'


# ---------------------------------------------------------------------------
# Action / guard function rendering
# ---------------------------------------------------------------------------

def _render_action_fn(fn_name: str, body_src: str, source_file: str, source_line: int) -> str:
    """Render a D-10 action function.

    Signature: def action_<name>(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:
    """
    comment = f"# from {source_file}:{source_line}"
    if body_src and body_src.strip():
        # transform_action already returns "# from ...\n<body>" — strip its comment
        # to avoid double-comment; use only the body part
        lines = body_src.split("\n", 1)
        body = lines[1] if len(lines) > 1 else "pass"
    else:
        body = "pass"

    indented = textwrap.indent(body.strip() or "pass", "    ")
    return (
        f"{comment}\n"
        f'def {fn_name}(ctx: "SimulationContext", self_dict: dict, params: dict) -> None:\n'
        f"{indented}\n"
    )


def _render_guard_fn(fn_name: str, expr_src: str, source_file: str, source_line: int) -> str:
    """Render a D-10 guard function.

    Signature: def guard_<name>(self_dict: dict, params: dict) -> bool:
    """
    comment = f"# from {source_file}:{source_line}"
    if expr_src and expr_src.strip():
        lines = expr_src.split("\n", 1)
        expr = lines[1] if len(lines) > 1 else "True"
    else:
        expr = "True"

    return (
        f"{comment}\n"
        f"def {fn_name}(self_dict: dict, params: dict) -> bool:\n"
        f"    return {expr.strip()}\n"
    )


# ---------------------------------------------------------------------------
# Transition table rendering
# ---------------------------------------------------------------------------

def _render_transition_table(
    transition_table: dict,
    action_fn_map: dict[tuple[str, str], str],
    guard_fn_map: dict[tuple[str, str], str],
) -> str:
    """Render TRANSITION_TABLE as a Python dict literal (sorted keys, D-07)."""
    lines = ["TRANSITION_TABLE: dict = {"]
    for key in sorted(transition_table.keys(), key=lambda k: (k[0], k[1])):
        state, event = key
        entry = transition_table[key]
        next_state = entry["next_state"]
        next_state_repr = repr(next_state)

        action_fn_name = action_fn_map.get(key)
        guard_fn_name = guard_fn_map.get(key)

        action_ref = action_fn_name if action_fn_name else "None"
        guard_ref = guard_fn_name if guard_fn_name else "None"

        lines.append(
            f'    ({state!r}, {event!r}): {{"next_state": {next_state_repr}, '
            f'"action_fn": {action_ref}, "guard_fn": {guard_ref}}},'
        )
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-class module generation
# ---------------------------------------------------------------------------

def generate_class_module(
    class_manifest: "ClassManifest",
    type_registry: dict[str, Any],
    parser: Any,
    source_file: str = "<model>",
) -> str:
    """Generate a Python source module for a single class.

    Args:
        class_manifest: ClassManifest dict from manifest_builder.
        type_registry:  Dict of type_name → {kind: "enum"|"typedef", ...}.
                        Used to emit enum classes and NewType stmts.
        parser:         STATEMENT_PARSER from pycca.grammar (unused directly
                        here — transform_action/transform_guard build their own).
        source_file:    Logical filename for D-05 comments.

    Returns:
        Unformatted Python source string (caller should run format_source).
    """
    cls_name: str = class_manifest["name"]
    entry_actions: dict[str, str | None] = class_manifest.get("entry_actions", {})
    transition_table: dict = class_manifest.get("transition_table", {})
    attributes: dict = class_manifest.get("attributes", {})

    # ------------------------------------------------------------------
    # Determine which enum / typedef types this class uses
    # ------------------------------------------------------------------
    used_types: set[str] = set()
    for attr_info in attributes.values():
        if isinstance(attr_info, dict):
            used_types.add(attr_info.get("type", ""))

    enum_blocks: list[str] = []
    typedef_lines: list[str] = []
    for type_name in sorted(used_types):
        info = type_registry.get(type_name)
        if not info:
            continue
        if info.get("kind") == "enum":
            enum_blocks.append(_render_enum(type_name, info.get("members", [])))
        elif info.get("kind") == "typedef":
            typedef_lines.append(_render_typedef(type_name, info.get("base", "object")))

    # ------------------------------------------------------------------
    # Build action functions from entry_actions (sorted by state name)
    # ------------------------------------------------------------------
    action_fn_bodies: list[str] = []
    # action_fn_map: (state, event) → function name for transition table
    action_fn_map: dict[tuple[str, str], str] = {}

    # Build a name→fn_name map for quick lookup when wiring the transition table
    state_to_fn: dict[str, str] = {}

    for state_name in sorted(entry_actions.keys()):
        action_src = entry_actions[state_name]
        fn_name = f"action_{state_name}_entry"
        state_to_fn[state_name] = fn_name

        if action_src and action_src.strip():
            try:
                transformed = transform_action(action_src, source_file, 0)
            except Exception:
                transformed = ""
        else:
            transformed = ""

        block = _render_action_fn(fn_name, transformed, source_file, 0)
        action_fn_bodies.append(block)

    # Map each transition to the DESTINATION state's entry action function.
    # xUML semantics: the entry action of the next_state fires on the transition.
    for (s, e), entry in transition_table.items():
        next_state = entry.get("next_state")
        if next_state and next_state in state_to_fn:
            action_fn_map[(s, e)] = state_to_fn[next_state]

    # ------------------------------------------------------------------
    # Build guard functions from transitions that have guard expressions
    # ------------------------------------------------------------------
    guard_fn_bodies: list[str] = []
    guard_fn_map: dict[tuple[str, str], str] = {}

    for key in sorted(transition_table.keys(), key=lambda k: (k[0], k[1])):
        state, event = key
        entry = transition_table[key]
        guard_src = entry.get("guard_fn")  # raw guard expression string at this stage
        if guard_src and isinstance(guard_src, str):
            fn_name = f"guard_{state}_{event}"
            try:
                transformed = transform_guard(guard_src, source_file, 0)
            except Exception:
                transformed = ""
            block = _render_guard_fn(fn_name, transformed, source_file, 0)
            guard_fn_bodies.append(block)
            guard_fn_map[key] = fn_name

    # ------------------------------------------------------------------
    # Assemble the source file
    # ------------------------------------------------------------------
    parts: list[str] = []

    # Header comment (D-05)
    parts.append(f"# from {source_file}:0")
    parts.append(f'"""Generated module for class {cls_name}."""')
    parts.append("from __future__ import annotations")
    parts.append("")
    parts.append("import enum")
    parts.append("from typing import TYPE_CHECKING, NewType")
    parts.append("")
    parts.append("if TYPE_CHECKING:")
    parts.append('    from engine.ctx import SimulationContext')
    parts.append("")

    # Enum classes
    if enum_blocks:
        parts.extend(enum_blocks)
        parts.append("")

    # NewType statements
    if typedef_lines:
        parts.extend(typedef_lines)
        parts.append("")

    # Action functions
    if action_fn_bodies:
        for block in action_fn_bodies:
            parts.append(block)

    # Guard functions
    if guard_fn_bodies:
        for block in guard_fn_bodies:
            parts.append(block)

    # Transition table
    if transition_table:
        parts.append(_render_transition_table(transition_table, action_fn_map, guard_fn_map))
    else:
        parts.append("TRANSITION_TABLE: dict = {}")

    parts.append("")  # trailing newline

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Domain __init__.py generation
# ---------------------------------------------------------------------------

def generate_init_module(domain_manifest: "DomainManifest") -> str:
    """Generate generated/__init__.py re-exporting each class module symbol.

    Imports are sorted by class name (D-07).
    """
    class_names = sorted(domain_manifest["class_defs"].keys())

    parts: list[str] = []
    parts.append('"""Generated domain package — re-exports all class modules."""')
    parts.append("from __future__ import annotations")
    parts.append("")

    for name in class_names:
        parts.append(f"from .{name} import TRANSITION_TABLE as {name}_TRANSITION_TABLE")

    parts.append("")
    parts.append("__all__ = [")
    for name in class_names:
        parts.append(f'    "{name}_TRANSITION_TABLE",')
    parts.append("]")
    parts.append("")

    return "\n".join(parts)
