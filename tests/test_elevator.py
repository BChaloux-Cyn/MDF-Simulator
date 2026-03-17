"""
End-to-end tests for the elevator reference model.

Verifies that validate_model returns zero issues on the complete Elevator domain,
serving as a permanent regression guard for the elevator reference model.

Implemented in plan 04.1-06.
"""
import importlib

import pytest

from tools.validation import validate_model
from tools.model_io import read_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=False)
def elevator_root(monkeypatch):
    """Change CWD to examples/elevator so MODEL_ROOT resolves correctly."""
    monkeypatch.chdir("examples/elevator")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_elevator_model_clean(elevator_root):
    """validate_model('Elevator') returns zero issues on the reference model."""
    import tools.validation as validation
    importlib.reload(validation)
    issues = validation.validate_model("Elevator")
    if issues:
        for issue in issues:
            print(issue)
    assert issues == [], f"Expected 0 issues, got {len(issues)}: {issues}"


def test_elevator_schema_loads(elevator_root):
    """read_model('Elevator') returns a string (class-diagram YAML), no error dict."""
    import tools.model_io as model_io
    importlib.reload(model_io)
    result = model_io.read_model("Elevator")
    assert isinstance(result, str), f"read_model returned error: {result}"
    assert "schema_version" in result
    assert "Elevator" in result
