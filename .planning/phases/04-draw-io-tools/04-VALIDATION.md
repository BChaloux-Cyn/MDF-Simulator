---
phase: 4
slug: draw-io-tools
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` testpaths = ["tests"] |
| **Quick run command** | `uv run pytest tests/test_drawio_tools.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_drawio_tools.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-??-01 | 01 | 0 | MCP-05 | unit | `uv run pytest tests/test_drawio_tools.py::test_render_class_diagram -x` | ❌ W0 | ⬜ pending |
| 4-??-02 | 01 | 0 | MCP-05 | unit | `uv run pytest tests/test_drawio_tools.py::test_render_idempotent -x` | ❌ W0 | ⬜ pending |
| 4-??-03 | 01 | 0 | MCP-05 | unit | `uv run pytest tests/test_drawio_tools.py::test_render_skip_unchanged -x` | ❌ W0 | ⬜ pending |
| 4-??-04 | 01 | 0 | MCP-05 | unit | `uv run pytest tests/test_drawio_tools.py::test_render_status_list -x` | ❌ W0 | ⬜ pending |
| 4-??-05 | 02 | 0 | MCP-06 | unit | `uv run pytest tests/test_drawio_tools.py::test_validate_drawio_valid -x` | ❌ W0 | ⬜ pending |
| 4-??-06 | 02 | 0 | MCP-06 | unit | `uv run pytest tests/test_drawio_tools.py::test_validate_drawio_invalid_style -x` | ❌ W0 | ⬜ pending |
| 4-??-07 | 03 | 0 | MCP-07 | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_adds_state -x` | ❌ W0 | ⬜ pending |
| 4-??-08 | 03 | 0 | MCP-07 | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_preserves_actions -x` | ❌ W0 | ⬜ pending |
| 4-??-09 | 03 | 0 | MCP-07 | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_runs_validate_model -x` | ❌ W0 | ⬜ pending |
| 4-??-10 | 03 | 0 | MCP-07 | unit | `uv run pytest tests/test_drawio_tools.py::test_sync_unrecognized_cell -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: Task IDs will be updated once PLAN.md files assign concrete task numbers.*

---

## Wave 0 Requirements

- [ ] `tests/test_drawio_tools.py` — stubs for MCP-05, MCP-06, MCP-07 (all 10 tests above)
- [ ] `igraph` added to `pyproject.toml` dependencies via `uv add igraph`

*All other infrastructure exists: pytest config in pyproject.toml, conftest.py present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Draw.io XML opens visually with all classes, associations, states, and transitions | MCP-05 | Requires visual inspection in Draw.io desktop app | Open generated `.drawio` file; verify all diagram elements render correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
