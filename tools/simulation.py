"""MCP tool wrappers: simulate_domain, simulate_class (Phase 5.3).

Provides two MCP tools:
  simulate_domain(domain, scenario, mocks) -> dict
  simulate_class(class_name, scenario, mocks) -> dict

Both return the D-06 result dict:
  {
      "total_steps": int,
      "final_instance_states": {"ClassName": {"id_str": "StateName", ...}, ...},
      "errors": [{"type": str, "message": str}, ...],
      "trace_file": "path/to/trace.json",
  }

Security (threat model T-5.3-08..T-5.3-11):
  T-5.3-08: yaml.safe_load only (not yaml.load)
  T-5.3-09: scenario stem sanitized to [A-Za-z0-9_.-]+ before use in filename
  T-5.3-10: domain arg sanitized before joining with .design/bundles/ path
  T-5.3-11: trigger fire cap enforced by TriggerEvaluator (engine/trigger.py)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

import yaml

from engine.bundle_loader import BundleCorruptError, BundleVersionError, load_bundle
from engine.ctx import SimulationContext
from engine.preflight import check_multiplicity
from engine.scenario_runner import run_scenario
from schema.scenario_schema import ScenarioDef

# MODEL_ROOT anchored to CWD (established Phase 02 pattern — tools/model_io.py)
def _model_root() -> Path:
    return Path.cwd() / ".design"


# T-5.3-09 / T-5.3-10: safe name pattern
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _sanitize(name: str, label: str) -> str:
    """Raise ValueError if name contains characters outside the safe set."""
    if not _SAFE_NAME.match(name):
        raise ValueError(
            f"Invalid {label}: {name!r} — must match {_SAFE_NAME.pattern}"
        )
    return name


def _load_scenario(scenario_path: str) -> ScenarioDef:
    """Load and validate a .scenario.yaml file."""
    path = Path(scenario_path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))  # T-5.3-08
    return ScenarioDef.model_validate(data)


def _load_mocks(scenario_path: str, explicit_mocks: str | None) -> dict:
    """Load companion .mocks.yaml, or return empty dict if absent."""
    if explicit_mocks:
        mocks_path = Path(explicit_mocks)
    else:
        p = Path(scenario_path)
        stem = p.name
        for suffix in (".scenario.yaml", ".yaml"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        mocks_path = p.parent / f"{stem}.mocks.yaml"
    if not mocks_path.exists():
        return {}
    return yaml.safe_load(mocks_path.read_text(encoding="utf-8")) or {}  # T-5.3-08


def _write_trace(domain: str, scenario_path: str, steps: list) -> str:
    """Serialize micro-steps to a timestamped JSON file under .design/traces/.

    Scenario stem is sanitized (T-5.3-09) before interpolation into the filename.
    """
    raw_stem = Path(scenario_path).name
    for suffix in (".scenario.yaml", ".yaml"):
        if raw_stem.endswith(suffix):
            raw_stem = raw_stem[: -len(suffix)]
            break
    # T-5.3-09: sanitize stem for filename safety
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_stem)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    traces_dir = _model_root() / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    out_path = traces_dir / f"{domain}_{safe_stem}_{timestamp}.json"
    records = [_step_to_dict(s) for s in steps]
    out_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    return str(out_path)


def _step_to_dict(step) -> dict:
    """Convert a MicroStep (frozen dataclass) or dict to a plain dict."""
    if is_dataclass(step) and not isinstance(step, type):
        return {"type": step.__class__.__name__, **asdict(step)}
    if isinstance(step, dict):
        return dict(step)
    return {"type": type(step).__name__, "repr": repr(step)}


def _collect_final_states(ctx: SimulationContext) -> dict:
    """Build final_instance_states from the registry after execution."""
    out: dict[str, dict] = {}
    for class_name, bucket in ctx.registry._store.items():
        if not bucket:
            continue
        class_states: dict[str, str] = {}
        for key, inst in bucket.items():
            id_str = ",".join(f"{k}={v}" for k, v in sorted(dict(key).items()))
            state = inst.get("curr_state", "")
            class_states[id_str] = state
        out[class_name] = class_states
    return out


def _cleanup_generated_modules() -> None:
    """Remove mdf_generated_* modules from sys.modules (Pitfall 5 — Windows temp cleanup)."""
    for name in list(sys.modules):
        if name.startswith("mdf_generated_"):
            del sys.modules[name]


def simulate_domain(domain: str, scenario: str, mocks: str | None = None) -> dict:
    """MCP tool: compile-load-run a domain bundle against a scenario file.

    Args:
        domain: Domain name (e.g. "Elevator"). Bundle path is
                .design/bundles/<domain>.mdfbundle.
        scenario: Path to a .scenario.yaml file.
        mocks: Optional path to a .mocks.yaml file. If None, looks for
               <scenario_stem>.mocks.yaml alongside the scenario.

    Returns:
        D-06 result dict with total_steps, final_instance_states, errors, trace_file.
    """
    errors: list[dict] = []
    trace_file = ""
    steps: list = []
    final_states: dict = {}
    tmpdir: Path | None = None
    domain_safe = domain  # fallback for trace filename

    try:
        domain_safe = _sanitize(domain, "domain")  # T-5.3-10
        bundle_path = _model_root() / "bundles" / f"{domain_safe}.mdfbundle"
        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_path}")

        scenario_def = _load_scenario(scenario)
        bridge_mocks = _load_mocks(scenario, mocks)
        manifest, tmpdir = load_bundle(bundle_path)

        preflight_issues = check_multiplicity(scenario_def, manifest)
        if preflight_issues:
            for issue in preflight_issues:
                errors.append({
                    "type": "PreflightError",
                    "message": f"{issue.location}: {issue.message}",
                })
            trace_file = _write_trace(domain_safe, scenario, [])
            return {
                "total_steps": 0,
                "final_instance_states": {},
                "errors": errors,
                "trace_file": trace_file,
            }

        ctx = SimulationContext(manifest, bridge_mocks=bridge_mocks)
        for step in run_scenario(ctx, scenario_def, manifest):
            steps.append(step)
        final_states = _collect_final_states(ctx)

    except (BundleVersionError, BundleCorruptError) as e:
        errors.append({"type": type(e).__name__, "message": str(e)})
    except FileNotFoundError as e:
        errors.append({"type": "FileNotFoundError", "message": str(e)})
    except ValueError as e:
        errors.append({"type": "ValueError", "message": str(e)})
    except Exception as e:
        errors.append({"type": type(e).__name__, "message": str(e)})
    finally:
        _cleanup_generated_modules()
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    if not trace_file:
        safe_domain = domain_safe if _SAFE_NAME.match(domain_safe or "") else "unknown"
        trace_file = _write_trace(safe_domain, scenario, steps)

    return {
        "total_steps": len(steps),
        "final_instance_states": final_states,
        "errors": errors,
        "trace_file": trace_file,
    }


def simulate_class(class_name: str, scenario: str, mocks: str | None = None) -> dict:
    """MCP tool: isolated single-class simulation.

    Locates the bundle that contains class_name and delegates to simulate_domain.

    Args:
        class_name: Name of the class to simulate (e.g. "Door").
        scenario: Path to a .scenario.yaml file scoped to that class.
        mocks: Optional path to a .mocks.yaml file.

    Returns:
        D-06 result dict.
    """
    try:
        class_safe = _sanitize(class_name, "class_name")  # T-5.3-10
        bundle_path = _find_bundle_for_class(class_safe)
        if bundle_path is None:
            return {
                "total_steps": 0,
                "final_instance_states": {},
                "errors": [{"type": "ClassNotFound", "message": f"No bundle contains class {class_name!r}"}],
                "trace_file": "",
            }
        domain = bundle_path.stem  # <domain>.mdfbundle -> domain name
        return simulate_domain(domain, scenario, mocks=mocks)
    except Exception as e:
        return {
            "total_steps": 0,
            "final_instance_states": {},
            "errors": [{"type": type(e).__name__, "message": str(e)}],
            "trace_file": "",
        }


def _find_bundle_for_class(class_name: str) -> Path | None:
    """Scan .design/bundles/ for a bundle whose generated/ dir contains <class_name>.py."""
    bundles_dir = _model_root() / "bundles"
    if not bundles_dir.exists():
        return None
    for bundle in sorted(bundles_dir.glob("*.mdfbundle")):
        try:
            with zipfile.ZipFile(bundle) as zf:
                if f"generated/{class_name}.py" in zf.namelist():
                    return bundle
        except zipfile.BadZipFile:
            continue
    return None
