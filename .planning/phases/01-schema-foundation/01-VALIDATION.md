---
phase: 1
slug: schema-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `mdf-server/pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 installs |
| **Quick run command** | `cd mdf-server && uv run pytest tests/ -x -q` |
| **Full suite command** | `cd mdf-server && uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd mdf-server && uv run pytest tests/ -x -q`
- **After every plan wave:** Run `cd mdf-server && uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04, SCHEMA-05, TMPL-01..04 | setup | `cd mdf-server && uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | SCHEMA-01, SCHEMA-02 | unit | `cd mdf-server && uv run pytest tests/test_yaml_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | SCHEMA-03 | unit | `cd mdf-server && uv run pytest tests/test_drawio_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 2 | SCHEMA-04 | integration | `cd mdf-server && uv run pytest tests/test_roundtrip.py -x -q` | ❌ W0 | ⬜ pending |
| 1-05-01 | 05 | 2 | SCHEMA-05, TMPL-01, TMPL-02, TMPL-03, TMPL-04 | smoke | `cd mdf-server && uv run pytest tests/test_templates.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `mdf-server/` package — does not exist; initialize with `uv init`
- [ ] `mdf-server/mdf_server/__init__.py` — package init
- [ ] `mdf-server/mdf_server/schema/__init__.py` — schema subpackage init
- [ ] `mdf-server/mdf_server/schema/yaml_schema.py` — Pydantic models (stub)
- [ ] `mdf-server/mdf_server/schema/drawio_schema.py` — bijection constants (stub)
- [ ] `mdf-server/tests/__init__.py` — test package init
- [ ] `mdf-server/tests/test_yaml_schema.py` — stubs for SCHEMA-01, SCHEMA-02
- [ ] `mdf-server/tests/test_drawio_schema.py` — stubs for SCHEMA-03
- [ ] `mdf-server/tests/test_roundtrip.py` — stubs for SCHEMA-04
- [ ] `mdf-server/tests/test_templates.py` — stubs for SCHEMA-05, TMPL-01..04
- [ ] Framework install: `cd mdf-server && uv init && uv add pydantic pyyaml "ruamel.yaml" lxml defusedxml && uv add --dev pytest ruff mypy`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Open generated XML in real Draw.io, save, verify diff is parse-safe | SCHEMA-04 | Requires interactive Draw.io browser app; no headless driver available | 1. Run `uv run python -m mdf_server.schema.drawio_schema` to generate sample XML. 2. Open file in Draw.io. 3. Save. 4. Run `uv run pytest tests/test_roundtrip.py::test_saved_roundtrip` on saved file. 5. Confirm structural equality. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
