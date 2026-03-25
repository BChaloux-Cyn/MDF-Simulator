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
        identifier: 1
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


# ---------------------------------------------------------------------------
# Guard completeness
# ---------------------------------------------------------------------------

ENUM_TYPES_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
types:
  - name: ValveMode
    base: enum
    values: [Manual, Auto, Locked]
"""

INTEGER_TYPES_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
types:
  - name: Pressure
    base: Integer
    range: [0, 200]
"""

STRING_TYPES_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
types:
  - name: Label
    base: String
"""

GUARD_CLASS_DIAGRAM_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: active
    attributes:
      - name: valve_id
        type: UniqueID
        identifier: 1
associations: []
bridges: []
"""


def _write_guard_model(
    tmp_path: Path,
    state_yaml: str,
    types_yaml: str | None = None,
) -> None:
    """Write class-diagram + state diagram + optional types.yaml to tmp_path."""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(GUARD_CLASS_DIAGRAM_YAML)
    state_dir = _make_state_dir(model_dir)
    (state_dir / "Valve.yaml").write_text(state_yaml)
    if types_yaml is not None:
        (model_dir / "types.yaml").write_text(types_yaml)


def test_guard_string_type_error(tmp_path, monkeypatch):
    """Guard on a String-typed event parameter returns severity='error'."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Mode_changed
    params:
      - name: label
        type: String
states:
  - name: Idle
  - name: Active
transitions:
  - from: Idle
    to: Active
    event: Mode_changed
    guard: "label == open"
"""
    _write_guard_model(tmp_path, state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    guard_issues = [i for i in result if "string" in i["issue"].lower() or "String" in i["issue"]]
    assert len(guard_issues) >= 1, f"Expected string guard error, got: {result}"
    assert guard_issues[0]["severity"] == "error"


def test_guard_enum_missing_value(tmp_path, monkeypatch):
    """Enum guard covering 2 of 3 values returns severity='error' naming the missing value."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Mode_changed
    params:
      - name: mode
        type: ValveMode
states:
  - name: Idle
  - name: Manual
  - name: Auto
transitions:
  - from: Idle
    to: Manual
    event: Mode_changed
    guard: "mode == Manual"
  - from: Idle
    to: Auto
    event: Mode_changed
    guard: "mode == Auto"
"""
    _write_guard_model(tmp_path, state_yaml, ENUM_TYPES_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    guard_issues = [i for i in result if "Locked" in i["issue"] or "missing" in i["issue"].lower() or "enum" in i["issue"].lower()]
    assert len(guard_issues) >= 1, f"Expected missing enum value error, got: {result}"
    assert guard_issues[0]["severity"] == "error"
    assert "Locked" in guard_issues[0]["issue"]


def test_guard_enum_complete(tmp_path, monkeypatch):
    """Enum guard covering all 3 values produces no guard completeness issue."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Mode_changed
    params:
      - name: mode
        type: ValveMode
states:
  - name: Idle
  - name: Manual
  - name: Auto
  - name: Locked
transitions:
  - from: Idle
    to: Manual
    event: Mode_changed
    guard: "mode == Manual"
  - from: Idle
    to: Auto
    event: Mode_changed
    guard: "mode == Auto"
  - from: Idle
    to: Locked
    event: Mode_changed
    guard: "mode == Locked"
"""
    _write_guard_model(tmp_path, state_yaml, ENUM_TYPES_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    # No guard completeness issues expected (trap-state warnings may appear for terminal states)
    guard_issues = [
        i for i in result
        if "enum" in i["issue"].lower() or "missing" in i["issue"].lower() or "guard" in i["issue"].lower()
    ]
    assert guard_issues == [], f"Expected no guard completeness issues, got: {guard_issues}"


def test_guard_multiple_unguarded_same_event(tmp_path, monkeypatch):
    """Two unguarded transitions from the same state on the same event returns severity='error'."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Open_valve
states:
  - name: Idle
  - name: Open
  - name: OpenFast
transitions:
  - from: Idle
    to: Open
    event: Open_valve
  - from: Idle
    to: OpenFast
    event: Open_valve
"""
    _write_guard_model(tmp_path, state_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    ambiguous = [i for i in result if "ambiguous" in i["issue"].lower() or "unguarded" in i["issue"].lower()]
    assert len(ambiguous) >= 1, f"Expected ambiguous transition error, got: {result}"
    assert ambiguous[0]["severity"] == "error"


def test_guard_interval_gap(tmp_path, monkeypatch):
    """Integer guard 'x < 5' and 'x > 5' returns a severity='warning' about the gap at x == 5."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Pressure_changed
    params:
      - name: pressure
        type: Pressure
states:
  - name: Idle
  - name: Low
  - name: High
transitions:
  - from: Idle
    to: Low
    event: Pressure_changed
    guard: "pressure < 5"
  - from: Idle
    to: High
    event: Pressure_changed
    guard: "pressure > 5"
"""
    _write_guard_model(tmp_path, state_yaml, INTEGER_TYPES_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    gap_issues = [i for i in result if "gap" in i["issue"].lower() or "coverage" in i["issue"].lower()]
    assert len(gap_issues) >= 1, f"Expected interval gap warning, got: {result}"
    assert gap_issues[0]["severity"] == "warning"


def test_guard_interval_full_coverage(tmp_path, monkeypatch):
    """Integer guard 'x < 5' and 'x >= 5' produces no gap issue."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Pressure_changed
    params:
      - name: pressure
        type: Pressure
states:
  - name: Idle
  - name: Low
  - name: High
transitions:
  - from: Idle
    to: Low
    event: Pressure_changed
    guard: "pressure < 5"
  - from: Idle
    to: High
    event: Pressure_changed
    guard: "pressure >= 5"
"""
    _write_guard_model(tmp_path, state_yaml, INTEGER_TYPES_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    gap_issues = [i for i in result if "gap" in i["issue"].lower() or "coverage" in i["issue"].lower()]
    assert gap_issues == [], f"Expected no gap issues for full coverage, got: {gap_issues}"


# ---------------------------------------------------------------------------
# Subtype partition checks (ELV-002, ELV-004)
# ---------------------------------------------------------------------------

PARTITION_SUPERTYPE_CLASS_YAML = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Shape
    stereotype: entity
    partitions:
      - name: R1
        subtypes:
          - Circle
  - name: Circle
    stereotype: entity
    specializes: R1
  - name: Square
    stereotype: entity
    specializes: R1
associations:
  - name: R1
    point_1: Shape
    point_2: Circle
    1_mult_2: "1"
    2_mult_1: "1"
    1_phrase_2: is specialized as
    2_phrase_1: specializes
bridges: []
"""

PARTITION_SUPERTYPE_CLASS_YAML_FIXED = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Shape
    stereotype: entity
    partitions:
      - name: R1
        subtypes:
          - Circle
          - Square
  - name: Circle
    stereotype: entity
    specializes: R1
  - name: Square
    stereotype: entity
    specializes: R1
associations:
  - name: R1
    point_1: Shape
    point_2: Circle
    1_mult_2: "1"
    2_mult_1: "1"
    1_phrase_2: is specialized as
    2_phrase_1: specializes
bridges: []
"""


def test_subtype_not_in_supertype_partition(tmp_path, monkeypatch):
    """Subtype with specializes: RN not listed in supertype partitions returns an error."""
    monkeypatch.chdir(tmp_path)
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(PARTITION_SUPERTYPE_CLASS_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    partition_issues = [
        i for i in result
        if "partition" in i["issue"].lower() or "Square" in i["issue"]
    ]
    assert len(partition_issues) >= 1, f"Expected partition issue for Square, got: {result}"
    assert partition_issues[0]["severity"] == "error"


def test_subtype_listed_in_supertype_partition_no_error(tmp_path, monkeypatch):
    """All subtypes listed in supertype partitions produces no partition issue."""
    monkeypatch.chdir(tmp_path)
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(PARTITION_SUPERTYPE_CLASS_YAML_FIXED)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    partition_issues = [
        i for i in result
        if "partition" in i["issue"].lower()
    ]
    assert partition_issues == [], f"Expected no partition issues, got: {partition_issues}"


def test_elevator_model_no_partition_errors(monkeypatch):
    """Elevator example model has no subtype partition errors after ELV-002/ELV-004 fixes."""
    elevator_path = Path(__file__).parent.parent / "examples" / "elevator"
    monkeypatch.chdir(elevator_path)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_model()
    partition_issues = [
        i for i in result
        if "partition" in i["issue"].lower()
    ]
    assert partition_issues == [], f"Elevator model has partition errors: {partition_issues}"


def test_guard_complex_expression_warning(tmp_path, monkeypatch):
    """Guard containing 'and'/'or' returns severity='warning' (cannot determine completeness)."""
    monkeypatch.chdir(tmp_path)
    state_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
class: Valve
initial_state: Idle
events:
  - name: Pressure_changed
    params:
      - name: pressure
        type: Pressure
      - name: flow
        type: Integer
states:
  - name: Idle
  - name: Active
transitions:
  - from: Idle
    to: Active
    event: Pressure_changed
    guard: "pressure > 10 and flow > 5"
"""
    _write_guard_model(tmp_path, state_yaml, INTEGER_TYPES_YAML)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    complex_issues = [
        i for i in result
        if "complex" in i["issue"].lower() or "cannot" in i["issue"].lower() or "completeness" in i["issue"].lower()
    ]
    assert len(complex_issues) >= 1, f"Expected complex guard warning, got: {result}"
    assert complex_issues[0]["severity"] == "warning"


# ---------------------------------------------------------------------------
# Identifier checks
# ---------------------------------------------------------------------------

def test_missing_identifier_1_error(tmp_path, monkeypatch):
    """Class with no identifier 1 attribute produces an error."""
    monkeypatch.chdir(tmp_path)
    bad_class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
    attributes:
      - name: status
        type: Boolean
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(bad_class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    id_issues = [i for i in result if "no identifier 1" in i["issue"].lower()]
    assert len(id_issues) >= 1, f"Expected missing identifier 1 error, got: {result}"
    assert id_issues[0]["severity"] == "error"


def test_uniqueid_non_identifier_warning(tmp_path, monkeypatch):
    """UniqueID attribute without identifier set produces a warning."""
    monkeypatch.chdir(tmp_path)
    bad_class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Valve
    stereotype: entity
    attributes:
      - name: valve_id
        type: UniqueID
        identifier: 1
      - name: r1_timer_id
        type: UniqueID
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(bad_class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    relvar_warnings = [
        i for i in result
        if "relvar" in i["issue"].lower() or "not an identifier" in i["issue"].lower()
    ]
    assert len(relvar_warnings) >= 1, f"Expected UniqueID non-identifier warning, got: {result}"
    assert relvar_warnings[0]["severity"] == "warning"


def test_subtype_inherits_identifier_no_error(tmp_path, monkeypatch):
    """Subtype without own identifier 1 is OK (inherited from supertype)."""
    monkeypatch.chdir(tmp_path)
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Shape
    stereotype: entity
    partitions:
      - name: R1
        subtypes:
          - Circle
    attributes:
      - name: shape_id
        type: UniqueID
        identifier: 1
  - name: Circle
    stereotype: entity
    specializes: R1
    attributes:
      - name: radius
        type: Real
associations:
  - name: R1
    point_1: Shape
    point_2: Circle
    1_mult_2: "1"
    2_mult_1: "1"
    1_phrase_2: is specialized as
    2_phrase_1: specializes
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    id_issues = [i for i in result if "no identifier 1" in i["issue"].lower()]
    assert id_issues == [], f"Subtype should not need own identifier, got: {id_issues}"


def test_compound_identifier_valid(tmp_path, monkeypatch):
    """Two attributes both with identifier [1] is a valid compound key."""
    monkeypatch.chdir(tmp_path)
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: FloorButton
    stereotype: entity
    attributes:
      - name: floor_num
        type: Integer
        identifier: 1
      - name: direction
        type: Integer
        identifier: 1
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    id_issues = [i for i in result if "no identifier 1" in i["issue"].lower()]
    assert id_issues == [], f"Compound identifier should be valid, got: {id_issues}"


# ---------------------------------------------------------------------------
# Type validation: built-in types, generics, class names
# ---------------------------------------------------------------------------


def test_builtin_types_accepted(tmp_path, monkeypatch):
    """Timestamp and Duration are valid attribute types without declaring them in types.yaml."""
    monkeypatch.chdir(tmp_path)
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Sensor
    stereotype: entity
    attributes:
      - name: sensor_id
        type: UniqueID
        identifier: 1
      - name: last_read
        type: Timestamp
      - name: interval
        type: Duration
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    type_issues = [i for i in result if "unknown type" in i["issue"].lower()]
    assert type_issues == [], f"Timestamp/Duration should be valid, got: {type_issues}"


def test_generic_type_with_valid_class(tmp_path, monkeypatch):
    """Set<ClassName> is valid when ClassName exists in the domain."""
    monkeypatch.chdir(tmp_path)
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Pump
    stereotype: active
    attributes:
      - name: pump_id
        type: UniqueID
        identifier: 1
    methods:
      - name: get_valves
        visibility: public
        scope: instance
        return: Set<Valve>
  - name: Valve
    stereotype: entity
    attributes:
      - name: valve_id
        type: UniqueID
        identifier: 1
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    type_issues = [i for i in result if "unknown type" in i["issue"].lower()]
    assert type_issues == [], f"Set<Valve> should be valid, got: {type_issues}"


def test_generic_type_with_invalid_class(tmp_path, monkeypatch):
    """Set<NonexistentClass> is an error."""
    monkeypatch.chdir(tmp_path)
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Pump
    stereotype: active
    attributes:
      - name: pump_id
        type: UniqueID
        identifier: 1
    methods:
      - name: get_stuff
        visibility: public
        scope: instance
        return: Set<NonexistentClass>
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    type_issues = [i for i in result if "is unknown" in i["issue"].lower() and "NonexistentClass" in i["issue"]]
    assert len(type_issues) >= 1, f"Set<NonexistentClass> should be invalid, got: {result}"


def test_nested_generic_optional_of_class(tmp_path, monkeypatch):
    """Optional<ClassName> is valid when ClassName exists."""
    monkeypatch.chdir(tmp_path)
    class_yaml = """\
schema_version: "1.0.0"
domain: Hydraulics
classes:
  - name: Pump
    stereotype: active
    attributes:
      - name: pump_id
        type: UniqueID
        identifier: 1
    methods:
      - name: find_valve
        visibility: public
        scope: instance
        return: Optional<Pump>
associations: []
bridges: []
"""
    model_dir = _make_model_dir(tmp_path)
    (model_dir / "class-diagram.yaml").write_text(class_yaml)
    from tools import validation
    importlib.reload(validation)
    result = validation.validate_domain("Hydraulics")
    type_issues = [i for i in result if "unknown type" in i["issue"].lower()]
    assert type_issues == [], f"Optional<Pump> should be valid, got: {type_issues}"
