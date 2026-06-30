"""compiler/type_utils.py — MDF type string -> Python type string conversion."""
from __future__ import annotations

_PRIMITIVES: dict[str, str] = {
    "Integer": "int",
    "Real": "float",
    "String": "str",
    "Boolean": "bool",
}


def mdf_type_to_python(type_str: str) -> str:
    type_str = type_str.strip()
    if type_str in _PRIMITIVES:
        return _PRIMITIVES[type_str]
    if "<" in type_str:
        base, rest = type_str.split("<", 1)
        base = base.strip()
        params_str = rest.rstrip(">").strip()
        params = _split_params(params_str)
        py_params = ", ".join(mdf_type_to_python(p) for p in params)
        if base == "Map":
            return f"dict[{py_params}]"
        if base == "Set":
            return f"set[{py_params}]"
        if base == "List":
            return f"list[{py_params}]"
        if base == "Optional":
            return f"{py_params} | None"
    return type_str


def _split_params(params_str: str) -> list[str]:
    """Split comma-separated type params respecting angle bracket nesting."""
    params: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in params_str:
        if ch == "<":
            depth += 1
            current.append(ch)
        elif ch == ">":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            params.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        params.append("".join(current).strip())
    return params
