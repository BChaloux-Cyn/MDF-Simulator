---
phase: 3
slug: validation-tool
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_validation.py -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_validation.py -x -q`
- **After every plan wave:** Run `uv run pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-W0-deps | Wave 0 | 0 | MCP-04 | install | `uv run python -c "import networkx, lark"` | ❌ W0 | ⬜ pending |
| 03-W0-schema | Wave 0 | 0 | MCP-04 | unit | `uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 03-W0-stubs | Wave 0 | 0 | MCP-04 | unit | `uv run pytest tests/test_validation.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-01 | 01 | 1 | MCP-04 | unit | `uv run pytest tests/test_validation.py::test_referential_integrity -x -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | MCP-04 | unit | `uv run pytest tests/test_validation.py::test_missing_files -x -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | MCP-04 | unit | `uv run pytest tests/test_validation.py::test_reachability -x -q` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | MCP-04 | unit | `uv run pytest tests/test_validation.py::test_trap_states -x -q` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 1 | MCP-04 | unit | `uv run pytest tests/test_validation.py::test_guard_completeness -x -q` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 1 | MCP-04 | unit | `uv run pytest tests/test_validation.py::test_pycca_grammar -x -q` | ❌ W0 | ⬜ pending |
| 03-05-01 | 05 | 2 | MCP-04 | integration | `uv run pytest tests/test_validation.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_validation.py` — stubs for all MCP-04 test cases (referential integrity, missing files, reachability, trap states, guard completeness, pycca grammar)
- [ ] `pyproject.toml` — add `networkx>=3.4` and `lark>=1.1` dependencies (`uv add networkx lark`)
- [ ] `schema/yaml_schema.py` — add `initial_state: str` to `StateDiagramFile` and update all affected test fixtures
- [ ] `tools/validation.py` — stub module with three public functions that return `[]`
- [ ] `pycca/grammar.py` — stub module with placeholder `PYCCA_GRAMMAR`
- [ ] `pycca/__init__.py` — package init if not exists

*All test stubs should pass (returning empty lists = no issues) so pytest -x -q is green from Wave 0 start.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MCP tool registration discoverable via Claude Desktop | MCP-04 | Requires live MCP client | Start `uv run mdf-server`, connect Claude Desktop, verify `validate_model`/`validate_domain`/`validate_class` appear in tool list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
