"""
compiler/__init__.py — Public API for the MDF model compiler.

CONSTRAINT (D-11): This package MUST NOT import from engine/*.
  - compiler/ may import from schema/ (to load YAML) and pycca/ (to parse action bodies).
  - Generated code imports engine/; the compiler itself does not.
  - Future contributors: enforce this rule at review time and in CI.

Public surface:
    compile_model(model_root, output_dir) -> Path
    CompileError                            — immutable error dataclass
    CompilationFailed                       — exception raised on compile errors
    ErrorAccumulator                        — collect + bulk-raise errors

Version constants (committed strategy per Plan 04):
    COMPILER_VERSION          — single source of truth for compiler version
    PYCCA_VERSION             — pycca grammar version pinned here (no importlib)
"""
from __future__ import annotations

from pathlib import Path

from compiler.error import CompileError, CompilationFailed, ErrorAccumulator

# ---------------------------------------------------------------------------
# Version constants (D-02 / Plan 04 committed strategy)
# No importlib.metadata; no try/except engine imports (D-11 boundary).
# Phase 5.3 loader checks engine_version against the installed engine/.
# ---------------------------------------------------------------------------
COMPILER_VERSION = "0.1.0"
PYCCA_VERSION = "0.1.0"

__all__ = [
    "compile_model",
    "CompileError",
    "CompilationFailed",
    "ErrorAccumulator",
    "COMPILER_VERSION",
    "PYCCA_VERSION",
]


def compile_model(model_root: Path, output_dir: Path) -> Path:
    """Compile an MDF domain model to a self-contained ``.mdfbundle``.

    Pipeline: load_model → build_domain_manifest → codegen → packager.

    Args:
        model_root: Path to a single-domain model root (parent of the domain
                    directory, e.g. ``examples/elevator/.design/model``).
                    The first non-hidden subdirectory is used as the domain.
        output_dir: Directory where the bundle will be written (created if absent).

    Returns:
        Path to the generated ``.mdfbundle`` file.

    Raises:
        CompilationFailed: When the model contains parse or compile errors.
    """
    from compiler.loader import load_model
    from compiler.manifest_builder import build_domain_manifest
    from compiler.codegen import generate_class_module, generate_init_module, format_source
    from compiler.packager import write_bundle
    from pycca.grammar import STATEMENT_PARSER

    model_root = Path(model_root)
    output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # 1. Load: YAML → canonical objects (raises CompilationFailed on error)
    # ------------------------------------------------------------------
    loaded = load_model(model_root)
    domain_name = loaded.class_diagram.domain

    # ------------------------------------------------------------------
    # 2. Build manifest: canonical → DomainManifest TypedDicts
    # ------------------------------------------------------------------
    manifest = build_domain_manifest(loaded, STATEMENT_PARSER)

    # ------------------------------------------------------------------
    # 3. Codegen: one .py per class, sorted
    # ------------------------------------------------------------------
    # Build type_registry from types_raw if present.
    # TypesFile.types is a list[TypeDef] (EnumType | StructType | ScalarType).
    # We emit enum and scalar (typedef) entries; struct types are skipped for now.
    type_registry: dict = {}
    if loaded.types_raw is not None:
        from schema.yaml_schema import EnumType, ScalarType
        for type_def in loaded.types_raw.types:
            if isinstance(type_def, EnumType):
                type_registry[type_def.name] = {
                    "kind": "enum",
                    "members": list(type_def.values),
                }
            elif isinstance(type_def, ScalarType):
                type_registry[type_def.name] = {
                    "kind": "typedef",
                    "base": type_def.base,
                }

    generated_files: dict[str, str] = {}
    acc = ErrorAccumulator()
    for cls_name in sorted(manifest["class_defs"].keys()):
        cls_manifest = manifest["class_defs"][cls_name]
        source_file = f"{domain_name}/{cls_name}.yaml"
        try:
            raw_src = generate_class_module(
                cls_manifest, type_registry, STATEMENT_PARSER, source_file=source_file
            )
            formatted = format_source(raw_src, filename=f"generated/{cls_name}.py")
            generated_files[cls_name] = formatted
        except CompilationFailed as exc:
            acc.add(CompileError(
                file=f"generated/{cls_name}.py",
                line=0,
                message=str(exc),
            ))

    acc.raise_if_any()

    # ------------------------------------------------------------------
    # 4. Package: deterministic .mdfbundle zip (D-12)
    # ------------------------------------------------------------------
    return write_bundle(
        domain_name=domain_name,
        files=generated_files,
        manifest=manifest,
        output_dir=output_dir,
        engine_version=COMPILER_VERSION,   # pinned; Phase 5.3 loader verifies
        pycca_version=PYCCA_VERSION,
    )
