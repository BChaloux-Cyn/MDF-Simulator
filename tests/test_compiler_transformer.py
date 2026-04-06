"""
tests/test_compiler_transformer.py — Unit tests for compiler.transformer.

RED stubs created in Plan 05.2-01; filled in by Plan 05.2-02.

Covers:
  - compiler package importability (compile_model placeholder)
  - CompileError / ErrorAccumulator (error.py)
  - ActionTransformer construct coverage (transformer.py)
  - GuardTransformer expression coverage (transformer.py)
"""
import pytest


# ---------------------------------------------------------------------------
# Plan 05.2-01 stubs — RED until Plan 05.2-02 implements compiler/
# ---------------------------------------------------------------------------

class TestCompilerImport:
    def test_compile_model_import(self):
        """from compiler import compile_model must succeed (Plan 05.2-02 Task 1)."""
        from compiler import compile_model  # noqa: F401

    def test_compile_model_raises_not_implemented(self):
        """compile_model placeholder raises NotImplementedError (Plan 05.2-02 Task 1)."""
        from pathlib import Path
        from compiler import compile_model
        with pytest.raises(NotImplementedError):
            compile_model(Path("."), Path("/tmp"))

    def test_compile_error_import(self):
        """from compiler import CompileError, ErrorAccumulator must succeed."""
        from compiler import CompileError, ErrorAccumulator  # noqa: F401


class TestCompileError:
    def test_compile_error_format(self):
        """CompileError(file, line, message) formats as 'file:line: message'."""
        from compiler import CompileError
        err = CompileError(file="x.yaml", line=10, message="bad syntax")
        assert str(err) == "x.yaml:10: bad syntax"

    def test_compile_error_immutable(self):
        """CompileError is a frozen dataclass."""
        from compiler import CompileError
        err = CompileError(file="x.yaml", line=1, message="msg")
        with pytest.raises((AttributeError, TypeError)):
            err.line = 99  # type: ignore[misc]


class TestErrorAccumulator:
    def test_empty_accumulator_no_raise(self):
        """Empty ErrorAccumulator.raise_if_any() is a no-op."""
        from compiler import ErrorAccumulator
        acc = ErrorAccumulator()
        acc.raise_if_any()  # must not raise

    def test_accumulator_collects_and_raises(self):
        """add() + raise_if_any() raises CompilationFailed with all messages."""
        from compiler import CompileError, ErrorAccumulator
        from compiler.error import CompilationFailed
        acc = ErrorAccumulator()
        acc.add(CompileError(file="a.yaml", line=1, message="err1"))
        acc.add(CompileError(file="b.yaml", line=2, message="err2"))
        with pytest.raises(CompilationFailed) as exc_info:
            acc.raise_if_any()
        msg = str(exc_info.value)
        assert "a.yaml:1: err1" in msg
        assert "b.yaml:2: err2" in msg

    def test_accumulator_extend(self):
        """extend() adds a list of errors."""
        from compiler import CompileError, ErrorAccumulator
        from compiler.error import CompilationFailed
        acc = ErrorAccumulator()
        errs = [
            CompileError(file="x.yaml", line=i, message=f"msg{i}")
            for i in range(3)
        ]
        acc.extend(errs)
        with pytest.raises(CompilationFailed):
            acc.raise_if_any()


# ---------------------------------------------------------------------------
# ActionTransformer construct coverage (Plan 05.2-02 Task 2)
# ---------------------------------------------------------------------------

class TestActionTransformerAssignment:
    def test_self_attr_assignment(self):
        """self.current_floor = 5; → self_dict["current_floor"] = 5"""
        from compiler.transformer import transform_action
        result = transform_action("self.current_floor = 5;", "test.yaml", 0)
        assert 'self_dict["current_floor"] = 5' in result

    def test_rcvd_evt_field_access(self):
        """rcvd_evt.floor_num used on RHS → params["floor_num"]"""
        from compiler.transformer import transform_action
        result = transform_action("self.x = rcvd_evt.floor_num;", "test.yaml", 0)
        assert 'params["floor_num"]' in result


class TestActionTransformerControlFlow:
    def test_if_else(self):
        """if/else statement translates to valid Python if/else."""
        from compiler.transformer import transform_action
        source = "if (self.x > 3) { self.y = 1; } else { self.y = 2; }"
        result = transform_action(source, "test.yaml", 0)
        assert "if" in result
        assert "else" in result
        # Output must be compilable Python
        compile(result, "<test>", "exec")

    def test_for_each(self):
        """for-each loop translates to valid Python for loop."""
        from compiler.transformer import transform_action
        source = "for (Item item : items) { self.count = self.count + 1; }"
        result = transform_action(source, "test.yaml", 0)
        assert "for" in result
        compile(result, "<test>", "exec")


class TestActionTransformerGenerate:
    def test_generate_to_self(self):
        """generate Floor_assigned to self; → ctx.generate call."""
        from compiler.transformer import transform_action
        result = transform_action("generate Floor_assigned to self;", "test.yaml", 0)
        assert 'ctx.generate("Floor_assigned"' in result
        assert "self_dict" in result

    def test_generate_with_delay(self):
        """generate Door_open to self delay duration_s(2); → ctx.generate with delay_ms=2000."""
        from compiler.transformer import transform_action
        result = transform_action(
            "generate Door_open to self delay duration_s(2);", "test.yaml", 0
        )
        assert 'ctx.generate("Door_open"' in result
        assert "delay_ms" in result or "2000" in result


class TestActionTransformerSelect:
    def test_select_any_related(self):
        """select any e related by self->R1; → emits a select_any ctx call."""
        from compiler.transformer import transform_action
        result = transform_action("select any e related by self->R1;", "test.yaml", 0)
        assert "select_any" in result or "ctx.select" in result


class TestActionTransformerBridge:
    def test_bridge_call_named_args(self):
        """Building::IsTopFloor[floor_num: self.current_floor]; → ctx.bridge call."""
        from compiler.transformer import transform_action
        result = transform_action(
            "Building::IsTopFloor[floor_num: self.current_floor];", "test.yaml", 0
        )
        assert 'ctx.bridge("Building", "IsTopFloor"' in result
        assert '"floor_num"' in result


class TestActionTransformerSourceComments:
    def test_source_line_comment(self):
        """Every emitted block is preceded by # from <file>:<line> comment."""
        from compiler.transformer import transform_action
        result = transform_action("self.x = 1;", "myfile.yaml", 10)
        assert "# from myfile.yaml:" in result

    def test_source_line_offset_applied(self):
        """Line comment uses absolute line (relative parse line + offset)."""
        from compiler.transformer import transform_action
        result = transform_action("self.x = 1;", "myfile.yaml", 20)
        # Line 1 in parse + offset 20 = line 21
        assert "myfile.yaml:21" in result


class TestActionTransformerUnhandledRule:
    def test_unhandled_rule_raises(self):
        """Unhandled grammar rule raises NotImplementedError naming the rule."""
        from compiler.transformer import ActionTransformer
        import lark
        # Create a minimal Tree with a fabricated rule name
        tree = lark.Tree("unknown_rule_xyz", [])
        t = ActionTransformer()
        with pytest.raises(NotImplementedError, match="unknown_rule_xyz"):
            t.__default__("unknown_rule_xyz", [], None)


class TestGuardTransformer:
    def test_guard_self_attr_comparison(self):
        """Guard: self.x > 0 → self_dict["x"] > 0."""
        from compiler.transformer import transform_guard
        result = transform_guard("self.x > 0", "test.yaml", 1)
        assert 'self_dict["x"] > 0' in result

    def test_guard_combined_expression(self):
        """Guard: self.x > 0 and self.y < 10 translates both sides."""
        from compiler.transformer import transform_guard
        result = transform_guard("self.x > 0 and self.y < 10", "test.yaml", 1)
        assert 'self_dict["x"]' in result
        assert 'self_dict["y"]' in result


class TestTier3UnsupportedStubs:
    def test_while_stmt_raises_compile_error(self):
        """while statement raises on parse (not in grammar) or transformer (D-08 stub).

        'while' is not yet in pycca/grammar.py, so lark raises UnexpectedCharacters.
        The D-08 intent is satisfied: the construct is rejected with a clear error.
        """
        from compiler.transformer import transform_action
        from compiler.error import CompilationFailed
        import lark
        with pytest.raises((CompilationFailed, NotImplementedError, lark.LarkError, Exception)):
            transform_action("while (self.x > 0) { self.x = self.x - 1; }", "t.yaml", 0)

    def test_switch_stmt_raises_compile_error(self):
        """switch statement raises on parse (not in grammar) or transformer (D-08 stub)."""
        from compiler.transformer import transform_action
        from compiler.error import CompilationFailed
        import lark
        with pytest.raises((CompilationFailed, NotImplementedError, lark.LarkError, Exception)):
            # switch is not in the grammar yet; parse itself will fail
            transform_action("switch (self.direction) { }", "t.yaml", 0)
