"""
model_io — MDF model I/O tools: list_domains, read_model, write_model.
"""
from pathlib import Path

import yaml
from pydantic import ValidationError

from schema.yaml_schema import ClassDiagramFile

MODEL_ROOT = Path(".design/model")


def _resolve_domain_path(domain: str) -> Path | None:
    """Return the Path for domain directory (case-insensitive), or None if not found."""
    if not MODEL_ROOT.exists():
        return None
    target = domain.lower()
    for d in MODEL_ROOT.iterdir():
        if d.is_dir() and d.name.lower() == target:
            return d
    return None


def _pydantic_errors_to_issues(e: ValidationError) -> list[dict]:
    """Convert a Pydantic ValidationError into the MDF issue-list format."""
    issues = []
    for err in e.errors():
        loc_parts = [str(p) for p in err["loc"]]
        location = ".".join(loc_parts) if loc_parts else "<root>"
        issues.append({
            "issue": err["msg"],
            "location": location,
            "value": err.get("input"),
        })
    return issues


def list_domains() -> list[str]:
    """
    Returns all domain names found in .design/model/.
    A domain is any subdirectory containing class-diagram.yaml.
    Returns [] if .design/model/ does not exist or is empty.
    Call this before read_model() to discover available domains.
    """
    if not MODEL_ROOT.exists():
        return []
    result = []
    for d in MODEL_ROOT.iterdir():
        if d.is_dir() and (d / "class-diagram.yaml").exists():
            result.append(d.name)
    return result


def read_model(domain: str) -> str | dict:
    """
    Returns the raw YAML string from .design/model/<domain>/class-diagram.yaml.
    Domain lookup is case-insensitive.
    On success: returns the YAML file content as a string.
    On domain not found: returns {"error": "Domain 'X' not found", "available": [...]}
    Call list_domains() first to discover available domain names.
    """
    domain_path = _resolve_domain_path(domain)
    if domain_path is None:
        return {"error": f"Domain '{domain}' not found", "available": list_domains()}
    yaml_file = domain_path / "class-diagram.yaml"
    if not yaml_file.exists():
        return {"error": f"Domain '{domain}' not found", "available": list_domains()}
    return yaml_file.read_text()


def write_model(domain: str, yaml_str: str) -> list[dict]:
    """
    Saves yaml_str to .design/model/<domain>/class-diagram.yaml after validation.
    Validates YAML syntax and Pydantic schema before writing. Never writes on error.
    Auto-creates .design/model/<domain>/ if it does not exist.
    Returns [] on success.
    Returns [{"issue": str, "location": str, "value": any}] on any error.
    Never raises exceptions — all errors are returned as structured data.
    """
    # Step 1: YAML parse
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        return [{
            "issue": f"YAML parse error: {getattr(exc, 'problem', str(exc))}",
            "location": f"line {mark.line + 1}" if mark else "unknown",
            "value": yaml_str[:200],
        }]

    # Step 2: Pydantic schema validation
    try:
        ClassDiagramFile.model_validate(data)
    except ValidationError as exc:
        return _pydantic_errors_to_issues(exc)

    # Step 3: Write only if both steps passed
    domain_dir = MODEL_ROOT / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "class-diagram.yaml").write_text(yaml_str)
    return []
