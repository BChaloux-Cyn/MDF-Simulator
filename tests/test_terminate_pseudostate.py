"""Tests for __terminal__ pseudostate validation and rendering."""
import yaml
import pytest
from pathlib import Path
from schema.yaml_schema import StateDiagramFile
from tools import validation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sd(transitions_extra: list[dict]) -> StateDiagramFile:
    """Minimal state diagram with Active and Closing states, plus extra transitions."""
    data = {
        "schema_version": "1.0.0",
        "domain": "Terminal",
        "class": "Widget",
        "initial_state": "Active",
        "events": [
            {"name": "Shutdown"},
            {"name": "Done"},
            {"name": "Bad"},
        ],
        "states": [
            {"name": "Active"},
            {"name": "Closing"},
        ],
        "transitions": [
            {"from": "Active", "to": "Closing", "event": "Shutdown"},
        ] + transitions_extra,
    }
    return StateDiagramFile(**data)


def _issues(sd: StateDiagramFile) -> list[dict]:
    """Run full validation and return all issues."""
    import importlib, sys
    # Patch the model root so validate_domain can find our in-memory object
    # instead, call the internal checkers directly
    from tools.validation import (
        _check_referential_integrity_state_diagram,
        _check_reachability,
    )
    return (
        _check_referential_integrity_state_diagram(sd, "Terminal")
        + _check_reachability(sd, "Terminal")
    )


# ---------------------------------------------------------------------------
# Validation: pseudostate routing guards
# ---------------------------------------------------------------------------

def test_from_terminal_is_validation_error():
    sd = _make_sd([{"from": "__terminal__", "to": "Active", "event": "Bad"}])
    issues = _issues(sd)
    assert any("__terminal__" in i["issue"] and "source" in i["issue"] for i in issues), \
        f"Expected '__terminal__ as source' error, got: {issues}"


def test_to_initial_is_validation_error():
    sd = _make_sd([{"from": "Closing", "to": "__initial__", "event": "Bad"}])
    issues = _issues(sd)
    assert any("__initial__" in i["issue"] for i in issues), \
        f"Expected '__initial__ as target' error, got: {issues}"


def test_to_terminal_is_not_a_validation_error():
    sd = _make_sd([{"from": "Closing", "to": "__terminal__", "event": "Done"}])
    issues = _issues(sd)
    ref_issues = [i for i in issues if "__terminal__" in i.get("issue", "") and "unknown" in i.get("issue", "")]
    assert not ref_issues, f"__terminal__ should be a valid transition target, got: {ref_issues}"
