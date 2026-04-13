"""Bundle loader: unpack .mdfbundle, verify version, rebind callables into DomainManifest.

Design decisions (05.3-CONTEXT.md):
  D-01: Extract to temp dir, import via spec_from_file_location (real stack traces).
  D-02: Hard fail on engine_version mismatch — BundleVersionError with both versions.
  D-03: Rebind action_fn/guard_fn from generated/<Class>.py into ClassManifest dicts.

Security (threat model T-5.3-05):
  Path traversal guard: every extracted path verified to be within tmpdir.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from engine import ENGINE_VERSION


class BundleVersionError(Exception):
    """Raised when bundle.json engine_version != installed ENGINE_VERSION."""


class BundleCorruptError(Exception):
    """Raised on path traversal or missing required bundle entries."""


def load_bundle(bundle_path: Path) -> tuple[dict, Path]:
    """Extract bundle, verify version, import generated modules, rebind callables.

    Args:
        bundle_path: Path to a .mdfbundle zip file.

    Returns:
        (domain_manifest, tmpdir_path) — caller is responsible for cleanup of tmpdir.

    Raises:
        BundleVersionError: bundle.json engine_version != ENGINE_VERSION.
        BundleCorruptError: path traversal entry or missing required files.
    """
    bundle_path = Path(bundle_path)
    tmpdir = Path(tempfile.mkdtemp(prefix="mdfbundle_"))
    try:
        with zipfile.ZipFile(bundle_path) as zf:
            # T-5.3-05: Path traversal guard — verify every entry resolves within tmpdir.
            # Lower-case both sides on Windows where drive letters may differ in case.
            # Append os.sep so a prefix-match against a sibling dir cannot pass.
            tmpdir_prefix = str(tmpdir.resolve()).lower() + os.sep
            for name in zf.namelist():
                resolved = str((tmpdir / name).resolve()).lower()
                if not resolved.startswith(tmpdir_prefix):
                    raise BundleCorruptError(f"Bundle contains unsafe path: {name!r}")
            zf.extractall(tmpdir)

        bundle_json_path = tmpdir / "bundle.json"
        manifest_json_path = tmpdir / "manifest.json"
        if not bundle_json_path.exists() or not manifest_json_path.exists():
            raise BundleCorruptError(
                f"Bundle missing bundle.json or manifest.json in {bundle_path}"
            )

        bundle_meta = json.loads(bundle_json_path.read_text(encoding="utf-8"))
        bundle_engine_version = bundle_meta.get("engine_version")
        if bundle_engine_version != ENGINE_VERSION:
            raise BundleVersionError(
                f"Bundle {bundle_path.name} requires engine {bundle_engine_version!r}, "
                f"installed engine is {ENGINE_VERSION!r}. Recompile the bundle."
            )

        manifest = json.loads(manifest_json_path.read_text(encoding="utf-8"))

        # Reverse "state::event" string keys → (state, event) tuples
        # Values are list[TransitionEntry] (list format introduced in plan 05.3.1-03).
        for cls_name, cls_def in manifest.get("class_defs", {}).items():
            tt_serialized = cls_def.get("transition_table", {})
            restored: dict = {}
            for key_str, entries in tt_serialized.items():
                if "::" in key_str:
                    state_str, event = key_str.split("::", 1)
                    state: str | None = None if state_str == "None" else state_str
                    restored[(state, event)] = entries
                else:
                    restored[key_str] = entries
            cls_def["transition_table"] = restored

        # Import generated/<Class>.py modules and rebind action_fn/guard_fn callables (D-03).
        # TRANSITION_TABLE in generated modules is list[TransitionEntry] per key.
        # Match manifest entries to live entries by next_state for deterministic rebinding.
        generated_dir = tmpdir / "generated"
        for cls_name, cls_def in manifest.get("class_defs", {}).items():
            module_file = generated_dir / f"{cls_name}.py"
            if not module_file.exists():
                raise BundleCorruptError(f"Bundle missing generated/{cls_name}.py")
            module = _import_module_from_file(f"mdf_generated_{cls_name}", module_file)
            live_tt: dict = getattr(module, "TRANSITION_TABLE", {})
            manifest_tt = cls_def["transition_table"]
            for key, live_entries in live_tt.items():
                if key not in manifest_tt:
                    continue
                manifest_entries = manifest_tt[key]
                # live_entries is list[TransitionEntry]; manifest_entries may be list or
                # legacy single-dict depending on bundle age. Normalise to list.
                if isinstance(manifest_entries, dict):
                    manifest_entries = [manifest_entries]
                    manifest_tt[key] = manifest_entries
                # Match by index (same ordering guaranteed by sorted codegen, D-07).
                for idx, live_entry in enumerate(live_entries):
                    if idx < len(manifest_entries):
                        manifest_entries[idx]["action_fn"] = live_entry.get("action_fn")
                        manifest_entries[idx]["guard_fn"] = live_entry.get("guard_fn")

        return manifest, tmpdir
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def _import_module_from_file(module_name: str, file_path: Path):
    """Import a Python module from a file path via importlib.

    Uses spec_from_file_location so stack traces reference the real file path (D-01).
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise BundleCorruptError(f"Cannot load spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module
