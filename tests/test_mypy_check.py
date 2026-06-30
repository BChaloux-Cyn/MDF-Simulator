# tests/test_mypy_check.py
import textwrap

import pytest
from pathlib import Path
from compiler.mypy_check import check_generated_files


_VALID_SOURCE = '''\
# from model.yaml:1
"""Generated module."""
from __future__ import annotations
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


class WidgetDict(TypedDict):
    __class_name__: str
    __instance_key__: str
    count: int


# from model.yaml:10
def action_Active_entry(
    ctx: "SimulationContext",
    self_dict: "WidgetDict",
    params: dict,
) -> None:
    x: int = 1
    self_dict["count"] = x
'''

_INVALID_SOURCE = '''\
# from model.yaml:1
"""Generated module."""
from __future__ import annotations
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.ctx import SimulationContext


class WidgetDict(TypedDict):
    __class_name__: str
    __instance_key__: str
    count: int


# from model.yaml:20
def action_Active_entry(
    ctx: "SimulationContext",
    self_dict: "WidgetDict",
    params: dict,
) -> None:
    self_dict["nonexistent_field"] = 1
'''


class TestCheckGeneratedFiles:
    def test_valid_source_returns_no_errors(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_VALID_SOURCE)
        errors = check_generated_files([path])
        assert errors == []

    def test_invalid_key_access_returns_error(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_INVALID_SOURCE)
        errors = check_generated_files([path])
        assert len(errors) >= 1
        assert any("nonexistent_field" in e.message for e in errors)

    def test_error_maps_to_mdf_source_file(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_INVALID_SOURCE)
        errors = check_generated_files([path])
        assert any(e.file == "model.yaml" for e in errors)

    def test_error_maps_to_mdf_source_line(self, tmp_path):
        path = str(tmp_path / "Widget.py")
        Path(path).write_text(_INVALID_SOURCE)
        errors = check_generated_files([path])
        # The # from comment before the function is "model.yaml:20"
        assert any(e.line == 20 for e in errors)

    def test_empty_paths_returns_no_errors(self):
        errors = check_generated_files([])
        assert errors == []


class TestCompileIntegration:
    def test_compile_model_raises_on_mypy_error(self, tmp_path):
        """compile_model raises CompilationFailed when generated code has type errors."""
        from compiler import compile_model, CompilationFailed

        domain_dir = tmp_path / "model" / "TestDomain"
        domain_dir.mkdir(parents=True)
        sd_dir = domain_dir / "state-diagrams"
        sd_dir.mkdir()

        (domain_dir / "class-diagram.yaml").write_text(textwrap.dedent("""\
            schema_version: "1.0.0"
            domain: TestDomain
            classes:
              - name: Widget
                stereotype: active
                attributes:
                  - name: count
                    type: Integer
        """))

        (sd_dir / "Widget.yaml").write_text(textwrap.dedent("""\
            schema_version: "1.0.0"
            domain: TestDomain
            class: Widget
            initial_state: Idle
            events: []
            states:
              - name: Idle
                entry_action: "self.nonexistent_field = 1;"
            transitions: []
        """))

        output_dir = tmp_path / "out"
        with pytest.raises(CompilationFailed):
            compile_model(tmp_path / "model", output_dir)
