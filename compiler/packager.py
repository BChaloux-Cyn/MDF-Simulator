"""compiler/packager.py — Deterministic .mdfbundle zip writer (D-12).

Produces a self-contained zip bundle with:
  bundle.json          — metadata (no timestamps, D-07)
  manifest.json        — serialized DomainManifest (callables stripped)
  generated/__init__.py
  generated/<Class>.py — one file per concrete class (sorted)

Design decisions:
  D-02: bundle.json contains engine_version, pycca_version, model_hash
  D-07: entries written in sorted order; no timestamps; sha256 hash stable
  D-12: bundle format spec — <domain>.mdfbundle

Exports:
    compute_model_hash(generated_files, manifest) -> str
    write_bundle(domain_name, files, manifest, output_dir,
                 engine_version, pycca_version) -> Path
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

# Fixed date tuple used for all ZipInfo entries to ensure byte-identical output.
# zipfile stores mtime in the central directory; using a constant eliminates
# the only remaining source of non-determinism in the zip byte stream.
_ZIP_DATE = (2020, 1, 1, 0, 0, 0)


def _strip_callables(obj: Any) -> Any:
    """Recursively replace callable values with None for JSON serialization.

    The Phase 5.3 loader rebinds action_fn/guard_fn from the generated .py
    modules; they must not be serialized into manifest.json (D-02).
    """
    if callable(obj) and not isinstance(obj, type):
        return None
    if isinstance(obj, dict):
        # Convert tuple keys (transition_table) to "state::event" strings so the
        # result is JSON-serializable. The Phase 5.3 loader reverses this.
        result = {}
        for k, v in obj.items():
            str_key = f"{k[0]}::{k[1]}" if isinstance(k, tuple) else k
            result[str_key] = _strip_callables(v)
        return result
    if isinstance(obj, (list, tuple)):
        return [_strip_callables(v) for v in obj]
    return obj


def _make_zip_entry(name: str, data: str | bytes) -> tuple[zipfile.ZipInfo, bytes]:
    """Build a ZipInfo with a fixed timestamp + the encoded data bytes."""
    info = zipfile.ZipInfo(filename=name, date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data
    return info, raw


def compute_model_hash(
    generated_files: dict[str, str],
    manifest: dict,
) -> str:
    """Return a stable sha256 hex digest over generated files + manifest.

    Inputs are serialized as sorted JSON so the hash is independent of dict
    insertion order.  No timestamps are included (D-07).

    Args:
        generated_files: class_name → Python source string.
        manifest:        DomainManifest dict (callables already stripped).

    Returns:
        64-char lowercase hex string.
    """
    payload = {
        "files": {k: generated_files[k] for k in sorted(generated_files)},
        "manifest": manifest,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_bundle(
    domain_name: str,
    files: dict[str, str],
    manifest: dict,
    output_dir: Path,
    engine_version: str,
    pycca_version: str,
) -> Path:
    """Write a deterministic .mdfbundle zip to *output_dir*.

    Args:
        domain_name:     Domain identifier (used as filename stem).
        files:           Dict of class_name → generated Python source.
                         Must NOT include "__init__" — that is generated here.
        manifest:        DomainManifest dict (callables will be stripped).
        output_dir:      Directory to write the bundle into (created if absent).
        engine_version:  Required engine version string written to bundle.json.
        pycca_version:   pycca version string written to bundle.json.

    Returns:
        Path to the created .mdfbundle file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = output_dir / f"{domain_name}.mdfbundle"

    # Strip callables before serialization (D-02)
    manifest_serializable = _strip_callables(manifest)

    # Compute model hash from generated files + stripped manifest
    model_hash = compute_model_hash(files, manifest_serializable)

    # Build bundle.json metadata (no timestamps, D-07; sorted keys)
    bundle_meta = {
        "compiler_version": "0.1.0",
        "engine_version": engine_version,
        "model_hash": model_hash,
        "pycca_version": pycca_version,
    }
    bundle_json = json.dumps(bundle_meta, sort_keys=True, indent=2, ensure_ascii=True)
    manifest_json = json.dumps(manifest_serializable, sort_keys=True, indent=2, ensure_ascii=True)

    # Build __init__.py: simple re-export from each class module (sorted)
    init_lines = ['"""Generated domain package."""', "from __future__ import annotations", ""]
    for cls_name in sorted(files.keys()):
        init_lines.append(f"from .{cls_name} import TRANSITION_TABLE as {cls_name}_TRANSITION_TABLE")
    init_lines.append("")
    init_src = "\n".join(init_lines)

    # Write zip in strictly sorted, deterministic order
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. bundle.json (always first)
        info, data = _make_zip_entry("bundle.json", bundle_json)
        zf.writestr(info, data)

        # 2. manifest.json (always second)
        info, data = _make_zip_entry("manifest.json", manifest_json)
        zf.writestr(info, data)

        # 3. generated/__init__.py
        info, data = _make_zip_entry("generated/__init__.py", init_src)
        zf.writestr(info, data)

        # 4. generated/<Class>.py in sorted class name order
        for cls_name in sorted(files.keys()):
            info, data = _make_zip_entry(f"generated/{cls_name}.py", files[cls_name])
            zf.writestr(info, data)

    return bundle_path
