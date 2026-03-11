# Requirements: MDF Simulator (mdf-sim)

**Defined:** 2026-03-05
**Updated:** 2026-03-09 — Migrated from model-based-project-framework monorepo
**Core Value:** Engineers can verify the full structural design before typing `execute-phase` — no guessing, no mid-execution surprises.

> **Note:** MCP tool requirements (MCP-00..MCP-09) are tracked here. Agent, skill, and workflow requirements are in `mdf-server`.

## v0.1 Requirements

### Schema Foundation

- [x] **SCHEMA-01**: YAML model schema defined — classes (stereotypes, identifiers, attributes, methods), associations (verb phrase, multiplicity), state machines (states, transitions, guards, pycca actions), domain bridges (from/to, operation, params, direction)
- [x] **SCHEMA-02**: `schema_version` field required in all model files from day one
- [x] **SCHEMA-03**: Canonical Draw.io schema defined — 1:1 bijection with YAML; canonical shape-type-per-element table locked; no freeform shapes without YAML equivalent
- [x] **SCHEMA-04**: Draw.io round-trip test passes — generate XML, open in real Draw.io, save, sync back; structural equality confirmed before any tool is built
- [x] **SCHEMA-05**: Behavior doc format defined — domain-level, class-level, and state-machine-level templates

### Templates

- [x] **TMPL-01**: `DOMAINS.md` template — domain map with realized domains and bridge index
- [x] **TMPL-02**: `CLASS_DIAGRAM.yaml` template — class diagram YAML scaffold
- [x] **TMPL-03**: `STATE_DIAGRAM.yaml` template — state diagram YAML scaffold
- [x] **TMPL-04**: Behavior doc templates — `behavior-domain.md`, `behavior-class.md`, `behavior-state.md`

### MCP Tools

- [x] **MCP-00**: Library package scaffolded — `mdf-simulator/` with `pyproject.toml`, module structure (`tools/`, `schema/`, `pycca/`)
- [x] **MCP-01**: `list_domains()` — returns all domain names in `.design/model/`
- [x] **MCP-02**: `read_model(domain)` — returns YAML for one domain; error if not found lists available domains
- [x] **MCP-03**: `write_model(domain, yaml)` — saves, validates against schema, returns issue list; idempotent
- [x] **MCP-04**: `validate_model(domain)` — returns list of issues: referential integrity, graph reachability (BFS/DFS unreachable states, trap states), pycca syntax pre-check; never pass/fail
- [x] **MCP-05**: `render_to_drawio(domain)` — generates Draw.io XML from YAML per canonical schema; deterministic and idempotent
- [x] **MCP-06**: `validate_drawio(domain, xml)` — validates Draw.io XML against canonical schema before sync; returns issue list
- [x] **MCP-07**: `sync_from_drawio(domain, xml)` — structured schema-aware parse back to YAML; runs `validate_model` automatically; returns issue list
- [ ] **MCP-08**: Simulation engine — `simulate_domain(domain, scenario)` and `simulate_class(class, events)`; domain-scoped object instance registry, three-queue event scheduler (priority/standard/delay), run-to-completion semantics, pycca interpreter, micro-step stream output, YAML mock registry for bridge calls
- [ ] **MCP-10**: CLI test harness — `mdf-sim-test` entry point; YAML test script format (instance setup, event sequence, per-step and final-state assertions); non-zero exit on assertion failure
- [ ] **MCP-11**: GUI debugger — `mdf-sim-gui` entry point (Dear PyGui); domain/class canvas from `.drawio` file; action-line breakpoints, property watchpoints, domain event breakpoints; Step/Continue/Reset controls; sync and async instance creation; live Log/Instances/Queues panels; optional `--scenario` file at launch
- [ ] **MCP-09**: Test suite — `test_engine` (detailed unit coverage), `test_model_io`, `test_drawio_roundtrip`, `test_validation`, `test_simulation`

## Out of Scope

| Feature | Reason |
|---------|--------|
| Agent and skill implementations | Belong to `mdf-server` |
| FastMCP server registration | `mdf-server` scope |
| GSD workflow integration | `mdf-server` scope |
| Micca as compilation target | pycca chosen; Micca deferred |
| Multi-user collaboration | Single engineer context for now |
| Scrall action language | Less mature tooling for C targets; evaluate after pycca path proven |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCHEMA-01 | Phase 1 | Complete |
| SCHEMA-02 | Phase 1 | Complete |
| SCHEMA-03 | Phase 1 | Complete |
| SCHEMA-04 | Phase 1 | Complete |
| SCHEMA-05 | Phase 1 | Complete |
| TMPL-01 | Phase 1 | Complete |
| TMPL-02 | Phase 1 | Complete |
| TMPL-03 | Phase 1 | Complete |
| TMPL-04 | Phase 1 | Complete |
| MCP-00 | Phase 2 | Complete |
| MCP-01 | Phase 2 | Complete |
| MCP-02 | Phase 2 | Complete |
| MCP-03 | Phase 2 | Complete |
| MCP-04 | Phase 3 | Complete |
| MCP-05 | Phase 4 | Complete |
| MCP-06 | Phase 4 | Complete |
| MCP-07 | Phase 4 | Complete |
| MCP-08 | Phase 5 | Pending |
| MCP-10 | Phase 6 | Pending |
| MCP-11 | Phase 7 | Pending |
| MCP-09 | Phase 8 | Pending |

**Coverage:**
- v0.1 requirements: 21 total (SCHEMA-01..05, TMPL-01..04, MCP-00..11)
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-05*
*Last updated: 2026-03-09 — Phase 5 scope expanded; MCP-08 updated for domain-scope engine; MCP-10 (CLI) and MCP-11 (GUI) added; MCP-09 (test suite) moved to Phase 8*
