"""
MDF Simulator MCP Server.

Exposes model validation and I/O tools via the Model Context Protocol.
"""
from mcp.server.fastmcp import FastMCP

from tools.drawio import (
    render_to_drawio,
    render_to_drawio_class,
    render_to_drawio_state,
    sync_from_drawio,
    validate_drawio,
)
from tools.model_io import list_domains, read_model, write_model
from tools.validation import validate_class, validate_domain, validate_model

mcp = FastMCP("mdf-simulator")


# ---------------------------------------------------------------------------
# Model I/O tools (MCP-01 / MCP-02 / MCP-03)
# ---------------------------------------------------------------------------


@mcp.tool()
def list_domains_tool() -> list[str]:
    """List all domain names found in the model directory (.design/model/)."""
    return list_domains()


@mcp.tool()
def read_model_tool(domain: str) -> str | dict:
    """Return the raw YAML string from the class-diagram.yaml for the given domain."""
    return read_model(domain)


@mcp.tool()
def write_model_tool(domain: str, yaml_str: str) -> list[dict]:
    """Validate and save yaml_str to the class-diagram.yaml for the given domain."""
    return write_model(domain, yaml_str)


# ---------------------------------------------------------------------------
# Validation tools (MCP-04)
# ---------------------------------------------------------------------------


@mcp.tool()
def validate_model_tool(report_missing: bool = True) -> list[dict]:
    """
    Validate the entire model: DOMAINS.yaml + all domains + all active class state diagrams.

    Returns a list of issue dicts with fields: issue, location, value, fix, severity.
    Never raises — all errors are returned as structured data.
    """
    return validate_model(report_missing=report_missing)


@mcp.tool()
def validate_domain_tool(domain: str, report_missing: bool = True) -> list[dict]:
    """
    Validate one domain: class-diagram.yaml + state-diagrams/*.yaml.

    Returns a list of issue dicts with fields: issue, location, value, fix, severity.
    Never raises — all errors are returned as structured data.
    """
    return validate_domain(domain, report_missing=report_missing)


@mcp.tool()
def validate_class_tool(domain: str, class_name: str, report_missing: bool = True) -> list[dict]:
    """
    Validate one class from class-diagram.yaml and its state diagram if active.

    Returns a list of issue dicts with fields: issue, location, value, fix, severity.
    Never raises — all errors are returned as structured data.
    """
    return validate_class(domain, class_name, report_missing=report_missing)


# ---------------------------------------------------------------------------
# Draw.io tools (MCP-05 / MCP-06 / MCP-07)
# ---------------------------------------------------------------------------


@mcp.tool()
def render_to_drawio_tool(domain: str) -> list[dict]:
    """
    Generate all Draw.io diagrams for a domain from YAML.

    Writes class-diagram.drawio and one state diagram per active class.
    Skip-if-unchanged: if structure matches existing .drawio, preserves layout positions.
    Returns per-file list of {"file": path, "status": "written"|"skipped"} dicts,
    plus any error issue dicts.
    Never raises — all errors returned as structured data.
    """
    return render_to_drawio(domain)


@mcp.tool()
def render_to_drawio_class_tool(domain: str) -> list[dict]:
    """
    Generate class-diagram.drawio for a domain from class-diagram.yaml.

    Skip-if-unchanged: preserves engineer layout if YAML structure is unchanged.
    Returns [{"file": path, "status": "written"|"skipped"}] plus any error issues.
    Never raises.
    """
    return render_to_drawio_class(domain)


@mcp.tool()
def render_to_drawio_state_tool(domain: str, class_name: str) -> list[dict]:
    """
    Generate state-diagrams/<ClassName>.drawio for one active class.

    Skip-if-unchanged: preserves engineer layout if state machine structure is unchanged.
    Returns [{"file": path, "status": "written"|"skipped"}] plus any error issues.
    Never raises.
    """
    return render_to_drawio_state(domain, class_name)


@mcp.tool()
def validate_drawio_tool(domain: str, xml: str) -> list[dict]:
    """
    Validate Draw.io XML against the canonical MDF bijection schema.

    Returns empty list for valid canonical XML.
    Returns error issues for any mxCell with an unrecognized style string.
    Call this before sync_from_drawio to catch freeform edits.
    Never raises.
    """
    return validate_drawio(domain, xml)


@mcp.tool()
def sync_from_drawio_tool(domain: str, class_name: str, xml: str) -> list[dict]:
    """
    Sync Draw.io XML topology changes back to a class's state YAML model file.

    Merges structural changes (add/remove states, transitions) while preserving
    YAML-only fields (pycca action bodies, guards, entry_action).
    Automatically runs validate_class after sync; its issues appear in the returned list.
    Returns info-severity issues for each added/deleted element.
    Never raises.
    """
    return sync_from_drawio(domain, class_name, xml)
