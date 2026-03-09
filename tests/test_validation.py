"""Tests for MCP validation tools: validate_model, validate_domain, validate_class."""
import importlib
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# YAML fixture strings
# ---------------------------------------------------------------------------

VALID_CLASS_DIAGRAM_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: active
    attributes:
      - name: valve_id
        type: UniqueID
associations: []
bridges: []
"""

VALID_STATE_DIAGRAM_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Open_valve
  - name: Close_valve
states:
  - name: Idle
  - name: Open
transitions:
  - from: Idle
    to: Open
    event: Open_valve
  - from: Open
    to: Idle
    event: Close_valve
"""

VALID_DOMAINS_YAML = """\
schema_version: "1.0.0"
domains:
  - name: Hydraulics
    type: application
    description: Hydraulic system domain
bridges: []
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_model_dir(tmp_path: Path) -> Path:
    """Create .design/model/Hydraulics/ directory structure."""
    model_dir = tmp_path / ".design" / "model" / "Hydraulics"
    model_dir.mkdir(parents=True)
    return model_dir


def _make_state_dir(model_dir: Path) -> Path:
    """Create state-diagrams/ subdirectory."""
    state_dir = model_dir / "state-diagrams"
    state_dir.mkdir(exist_ok=True)
    return state_dir


def _write_full_valid_model(tmp_path: Path) -> None:
    """Write a complete valid Hydraulics domain with DOMAINS.yaml."""
    # DOMAINS.yaml
    domains_path = tmp_path / ".design" / "model"
    domains_path.mkdir(parents=True, exist_ok=True)
    (domains_path / "DOMAINS.yaml").write_text(VALID_DOMAINS_YAML)
    # class-diagram.yaml
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    # state diagram
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(VALID_STATE_DIAGRAM_YAML)


# ---------------------------------------------------------------------------
# No-raise contract
# ---------------------------------------------------------------------------

def test_validate_model_returns_list(tmp_path, monkeypatch):
    """validate_model() always returns a list, never raises."""
    monkeypatch.chdir(tmp_path)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_model()
    assert isinstance(result, list)


def test_validate_domain_returns_list(tmp_path, monkeypatch):
    """validate_domain("X") always returns a list, never raises."""
    monkeypatch.chdir(tmp_path)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("NonExistent")
    assert isinstance(result, list)


def test_validate_class_returns_list(tmp_path, monkeypatch):
    """validate_class("X", "Y") always returns a list, never raises."""
    monkeypatch.chdir(tmp_path)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_class("NonExistent", "NoClass")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Missing-file checks
# ---------------------------------------------------------------------------

def test_missing_class_diagram_reported(tmp_path, monkeypatch):
    """Missing class-diagram.yaml with report_missing=True produces an issue."""
    monkeypatch.chdir(tmp_path)
    # Create domain directory but no class-diagram.yaml
    model_dir = tmp_path / ".design" / "model" / "Hydraulics"
    model_dir.mkdir(parents=True)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics", report_missing=True)
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "class-diagram.yaml" in issues_text


def test_report_missing_false_suppresses(tmp_path, monkeypatch):
    """report_missing=False suppresses missing-file issues."""
    monkeypatch.chdir(tmp_path)
    # Create domain directory but no class-diagram.yaml
    model_dir = tmp_path / ".design" / "model" / "Hydraulics"
    model_dir.mkdir(parents=True)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics", report_missing=False)
    assert isinstance(result, list)
    # With no file to check for structural errors, list should be empty
    assert result == []


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------

def test_bad_association_class(tmp_path, monkeypatch):
    """Association referencing a non-existent class name returns an issue."""
    monkeypatch.chdir(tmp_path)
    bad_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
associations:
  - name: R1
    point_1: Valve
    point_2: NonExistentClass
    1_mult_2: "1"
    2_mult_1: "1"
    1_phrase_2: has
    2_phrase_1: is for
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(bad_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "NonExistentClass" in issues_text or "association" in issues_text.lower()


def test_bad_transition_target(tmp_path, monkeypatch):
    """Transition.to referencing a non-existent state returns an issue."""
    monkeypatch.chdir(tmp_path)
    bad_state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Open_valve
states:
  - name: Idle
transitions:
  - from: Idle
    to: NonExistentState
    event: Open_valve
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(bad_state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "NonExistentState" in issues_text or "transition" in issues_text.lower()


def test_bad_transition_event(tmp_path, monkeypatch):
    """Transition.event referencing a non-existent event name returns an issue."""
    monkeypatch.chdir(tmp_path)
    bad_state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Open_valve
states:
  - name: Idle
  - name: Open
transitions:
  - from: Idle
    to: Open
    event: NonExistentEvent
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(bad_state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "NonExistentEvent" in issues_text or "event" in issues_text.lower()


def test_bad_attribute_type(tmp_path, monkeypatch):
    """Attribute with non-primitive type and no types.yaml returns an issue."""
    monkeypatch.chdir(tmp_path)
    bad_class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
    attributes:
      - name: pressure
        type: Pressure
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(bad_class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "Pressure" in issues_text or "type" in issues_text.lower()


def test_bad_initial_state(tmp_path, monkeypatch):
    """initial_state referencing a state name not in states list returns an issue."""
    monkeypatch.chdir(tmp_path)
    bad_state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: NonExistentState
events:
  - name: Open_valve
states:
  - name: Idle
transitions:
  - from: Idle
    to: Idle
    event: Open_valve
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(bad_state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "NonExistentState" in issues_text or "initial_state" in issues_text.lower()


def test_subtype_specializes_missing_r_number(tmp_path, monkeypatch):
    """specializes R-number not in associations returns an issue."""
    monkeypatch.chdir(tmp_path)
    bad_class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
  - name: BallValve
    stereotype: entity
    specializes: R99
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(bad_class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "R99" in issues_text or "specializes" in issues_text.lower()


def test_bad_bridge_operation(tmp_path, monkeypatch):
    """required_bridge operation not declared in DOMAINS.yaml returns an issue from validate_model()."""
    monkeypatch.chdir(tmp_path)
    domains_yaml = """\
schema_version: "1.0.0"
domains:
  - name: Hydraulics
    type: application
    description: Hydraulic system domain
bridges:
  - from: Hydraulics
    to: Pneumatics
    operations:
      - name: Open
      - name: Close
"""
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
associations: []
bridges:
  - to_domain: Pneumatics
    direction: required
    operations:
      - Open
      - Close
      - Flush
"""
    model_root = tmp_path / ".design" / "model"
    model_root.mkdir(parents=True)
    (model_root / "DOMAINS.yaml").write_text(domains_yaml)
    model_dir = model_root / "Hydraulics"
    model_dir.mkdir()
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_model()
    assert isinstance(result, list)
    assert len(result) >= 1
    issues_text = " ".join(i["issue"] for i in result)
    assert "Flush" in issues_text or "undeclared" in issues_text.lower() or "operation" in issues_text.lower()


# ---------------------------------------------------------------------------
# Graph reachability
# ---------------------------------------------------------------------------

def test_unreachable_state_detected(tmp_path, monkeypatch):
    """State with no incoming path from initial_state is reported as severity='error'."""
    monkeypatch.chdir(tmp_path)
    bad_state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Open_valve
states:
  - name: Idle
  - name: Open
  - name: Orphan
transitions:
  - from: Idle
    to: Open
    event: Open_valve
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(bad_state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    unreachable = [i for i in result if "Orphan" in str(i.get("value", "")) or "Orphan" in i.get("issue", "")]
    assert len(unreachable) >= 1
    assert unreachable[0]["severity"] == "error"


def test_trap_state_warning(tmp_path, monkeypatch):
    """State with no outgoing transitions is reported as severity='warning'."""
    monkeypatch.chdir(tmp_path)
    trap_state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Open_valve
states:
  - name: Idle
  - name: Terminal
transitions:
  - from: Idle
    to: Terminal
    event: Open_valve
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(trap_state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    trap = [i for i in result if "Terminal" in str(i.get("value", "")) or "Terminal" in i.get("issue", "")]
    assert len(trap) >= 1
    assert trap[0]["severity"] == "warning"


def test_reachable_state_no_issue(tmp_path, monkeypatch):
    """Fully-connected state machine with no unreachable/trap states produces no reachability issues."""
    monkeypatch.chdir(tmp_path)
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(VALID_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(VALID_STATE_DIAGRAM_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    assert isinstance(result, list)
    assert result == []
