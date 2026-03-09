"""
MDF Simulator MCP Server.

Exposes model validation and I/O tools via the Model Context Protocol.
"""
from mcp.server.fastmcp import FastMCP

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
