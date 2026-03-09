---
phase: 02
slug: mcp-server-model-io
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2+ |
| **Config file** | `mdf-server/pyproject.toml` → `[tool.pytest.ini_options] testpaths = ["tests"]` |
| **Quick run command** | `cd mdf-server && uv run pytest tests/test_model_io.py -x` |
| **Full suite command** | `cd mdf-server && uv run pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd mdf-server && uv run pytest tests/test_model_io.py -x`
- **After every plan wave:** Run `cd mdf-server && uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 0 | MCP-00 | smoke | `cd mdf-server && uv run python -c "import mdf_server.server"` | ❌ W0 | ⬜ pending |
| TBD | 01 | 0 | MCP-00 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_imports -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-01 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_list_domains_empty -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-01 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_list_domains_with_domains -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-02 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_read_model_known -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-02 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_read_model_unknown -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-03 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_write_model_valid -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-03 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_write_model_bad_yaml -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | MCP-03 | unit | `cd mdf-server && uv run pytest tests/test_model_io.py::test_write_model_schema_invalid -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: Task IDs will be filled in after plans are written.*

---

## Wave 0 Requirements

- [ ] `mdf-server/tests/test_model_io.py` — stubs for MCP-00 through MCP-03 (9 test cases)
- [ ] `mdf-server/mdf_server/server.py` — FastMCP instance + tool registration stubs
- [ ] `mdf-server/mdf_server/tools/__init__.py` — package init
- [ ] `mdf-server/mdf_server/tools/model_io.py` — three tool implementations
- [ ] `mdf-server/mdf_server/tools/drawio.py` — stub (Phase 4)
- [ ] `mdf-server/mdf_server/tools/validation.py` — stub (Phase 3)
- [ ] `mdf-server/mdf_server/tools/simulation.py` — stub (Phase 5)
- [ ] `mdf-server/mdf_server/pycca/__init__.py` — stub (Phase 5)
- [ ] `mdf-server/pyproject.toml` update: add `fastmcp>=3.1.0,<4.0.0` to dependencies + `[project.scripts]` entry

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Claude connects to server via MCP protocol | MCP-00 | Requires live Claude Code session + MCP config | Add server to `~/.claude/settings.json` MCP config, restart Claude Code, verify `mdf/list_domains` appears in tool list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
