"""Tests for MCP model I/O tools: list_domains, read_model, write_model."""
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_CLASS_DIAGRAM_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
    attributes:
      - name: valve_id
        type: UniqueID
        identifier: true
associations: []
bridges: []
"""

INVALID_YAML_SYNTAX = "key: [unclosed"

SCHEMA_INVALID_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: not_a_valid_stereotype
associations: []
bridges: []
"""


# ---------------------------------------------------------------------------
# MCP-00: Import smoke tests
# ---------------------------------------------------------------------------

def test_imports():
    """Server and all tool modules are importable without error."""
    import tools.model_io  # smoke test
    import tools.model_io  # noqa: F401
    import tools.drawio  # noqa: F401
    import tools.validation  # noqa: F401
    import tools.simulation  # noqa: F401
    import pycca  # noqa: F401


# ---------------------------------------------------------------------------
# MCP-01: list_domains
# ---------------------------------------------------------------------------

def test_list_domains_empty(tmp_path, monkeypatch):
    """list_domains() returns [] when .design/model/ does not exist."""
    monkeypatch.chdir(tmp_path)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    assert model_io.list_domains() == []


def test_list_domains_with_domains(tmp_path, monkeypatch):
    """list_domains() returns domain names for directories containing class-diagram.yaml."""
    monkeypatch.chdir(tmp_path)
    domain_dir = tmp_path / ".design" / "model" / "Hydraulics"
    domain_dir.mkdir(parents=True)
    (domain_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.list_domains()
    assert result == ["Hydraulics"]


# ---------------------------------------------------------------------------
# MCP-02: read_model
# ---------------------------------------------------------------------------

def test_read_model_case_insensitive(tmp_path, monkeypatch):
    """read_model() finds domain directory case-insensitively (e.g. 'hydraulics' finds 'Hydraulics/')."""
    monkeypatch.chdir(tmp_path)
    domain_dir = tmp_path / ".design" / "model" / "Hydraulics"
    domain_dir.mkdir(parents=True)
    (domain_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.read_model("hydraulics")
    assert isinstance(result, str)
    assert "schema_version" in result


def test_read_model_known(tmp_path, monkeypatch):
    """read_model() returns YAML string for a known domain."""
    monkeypatch.chdir(tmp_path)
    domain_dir = tmp_path / ".design" / "model" / "Hydraulics"
    domain_dir.mkdir(parents=True)
    (domain_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.read_model("Hydraulics")
    assert isinstance(result, str)
    assert "schema_version" in result


def test_read_model_unknown(tmp_path, monkeypatch):
    """read_model() returns error dict with available list for unknown domain."""
    monkeypatch.chdir(tmp_path)
    domain_dir = tmp_path / ".design" / "model" / "Hydraulics"
    domain_dir.mkdir(parents=True)
    (domain_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.read_model("NonExistent")
    assert isinstance(result, dict)
    assert "error" in result
    assert "available" in result
    assert "Hydraulics" in result["available"]


# ---------------------------------------------------------------------------
# MCP-03: write_model
# ---------------------------------------------------------------------------

def test_write_model_valid(tmp_path, monkeypatch):
    """write_model() writes file and returns [] for valid YAML."""
    monkeypatch.chdir(tmp_path)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.write_model("Hydraulics", VALID_CLASS_DIAGRAM_YAML)
    assert result == []
    written = (tmp_path / ".design" / "model" / "Hydraulics" / "class-diagram.yaml")
    assert written.exists()
    assert "schema_version" in written.read_text()


def test_write_model_bad_yaml(tmp_path, monkeypatch):
    """write_model() returns parse error issue for invalid YAML syntax, no file written."""
    monkeypatch.chdir(tmp_path)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.write_model("Hydraulics", INVALID_YAML_SYNTAX)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "issue" in result[0]
    assert "YAML parse error" in result[0]["issue"]
    assert not (tmp_path / ".design" / "model" / "Hydraulics" / "class-diagram.yaml").exists()


def test_write_model_schema_invalid(tmp_path, monkeypatch):
    """write_model() returns Pydantic issue list for schema-invalid YAML, no file written."""
    monkeypatch.chdir(tmp_path)
    from tools import model_io
    import importlib
    importlib.reload(model_io)
    result = model_io.write_model("Hydraulics", SCHEMA_INVALID_YAML)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "issue" in result[0]
    assert "location" in result[0]
    assert not (tmp_path / ".design" / "model" / "Hydraulics" / "class-diagram.yaml").exists()
