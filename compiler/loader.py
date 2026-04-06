"""compiler/loader.py — Walk a model root and return a LoadedModel.

The canonical JSON format (CanonicalClassDiagram / CanonicalStateDiagram) is the
compiler's primary input format — YAML parsing is handled here as an implementation
detail so the rest of the compiler never touches yaml_schema directly.

Exports:
    LoadedModel   — dataclass holding canonical objects + optional TypesFile
    load_model    — walk model root → LoadedModel
"""
from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path

from schema.canonical_builder import yaml_to_canonical_class, yaml_to_canonical_state
from schema.drawio_canonical import CanonicalClassDiagram, CanonicalStateDiagram
from schema.yaml_schema import ClassDiagramFile, StateDiagramFile, TypesFile
from compiler.error import CompileError, CompilationFailed, ErrorAccumulator


@dataclass
class LoadedModel:
    """Canonical representation of a compiled domain model.

    class_diagram   — structural model (classes, assocs, generalizations)
    state_diagrams  — behavioural model, keyed by class name
    types_raw       — type definitions (enums, typedefs, refinements); None if absent
    root            — original model root (for error messages)
    """

    class_diagram: CanonicalClassDiagram
    state_diagrams: dict[str, CanonicalStateDiagram] = field(default_factory=dict)
    types_raw: TypesFile | None = None
    root: Path = field(default_factory=Path)


def load_model(model_root: Path) -> LoadedModel:
    """Walk *model_root* and return a LoadedModel with canonical objects.

    Expected layout (matches elevator example)::

        <model_root>/
            <Domain>/
                class-diagram.yaml
                types.yaml          (optional)
                state-diagrams/
                    <ClassName>.yaml
                    ...

    Raises CompilationFailed (via ErrorAccumulator) on any parse or I/O error.
    """
    acc = ErrorAccumulator()

    if not model_root.exists():
        raise CompilationFailed(
            f"Model root does not exist: {model_root}"
        )

    # Discover domain directory (first non-hidden subdirectory)
    domain_dirs = sorted(
        d for d in model_root.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    if not domain_dirs:
        raise CompilationFailed(
            f"No domain directory found under: {model_root}"
        )

    domain_dir = domain_dirs[0]
    domain = domain_dir.name

    # ------------------------------------------------------------------
    # Class diagram (required)
    # ------------------------------------------------------------------
    class_diag_path = domain_dir / "class-diagram.yaml"
    class_diagram: CanonicalClassDiagram | None = None

    if not class_diag_path.exists():
        acc.add(CompileError(
            file=str(class_diag_path), line=0,
            message="class-diagram.yaml not found",
        ))
    else:
        try:
            raw = yaml.safe_load(class_diag_path.read_text(encoding="utf-8"))
            cd = ClassDiagramFile.model_validate(raw)
            class_diagram = yaml_to_canonical_class(domain, cd)
        except Exception as exc:
            acc.add(CompileError(
                file=str(class_diag_path), line=0,
                message=f"Failed to parse class diagram: {exc}",
            ))

    acc.raise_if_any()
    assert class_diagram is not None  # guaranteed by raise_if_any above

    # ------------------------------------------------------------------
    # State diagrams (optional directory)
    # ------------------------------------------------------------------
    state_diagrams: dict[str, CanonicalStateDiagram] = {}
    sd_dir = domain_dir / "state-diagrams"
    if sd_dir.exists():
        for sd_path in sorted(sd_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(sd_path.read_text(encoding="utf-8"))
                sd = StateDiagramFile.model_validate(raw)
                state_diagrams[sd.class_name] = yaml_to_canonical_state(domain, sd)
            except Exception as exc:
                acc.add(CompileError(
                    file=str(sd_path), line=0,
                    message=f"Failed to parse state diagram: {exc}",
                ))

    acc.raise_if_any()

    # ------------------------------------------------------------------
    # Types file (optional)
    # ------------------------------------------------------------------
    types_raw: TypesFile | None = None
    types_path = domain_dir / "types.yaml"
    if types_path.exists():
        try:
            raw = yaml.safe_load(types_path.read_text(encoding="utf-8"))
            types_raw = TypesFile.model_validate(raw)
        except Exception as exc:
            acc.add(CompileError(
                file=str(types_path), line=0,
                message=f"Failed to parse types.yaml: {exc}",
            ))

    acc.raise_if_any()

    return LoadedModel(
        class_diagram=class_diagram,
        state_diagrams=state_diagrams,
        types_raw=types_raw,
        root=model_root,
    )
