# Project Research Summary

**Project:** Model-Driven Framework (MDF) v1.0
**Domain:** Developer tooling for xUML/Shlaer-Mellor embedded systems design — MCP server, YAML schema, Claude Code skills
**Researched:** 2026-03-05
**Confidence:** HIGH

## Executive Summary

MDF is a bespoke developer tool that bridges xUML/Shlaer-Mellor methodology to Claude Code via a three-layer architecture: MCP primitive tools (Python/FastMCP), agent-spawning skills (Markdown skill files), and a YAML-first model representation with deterministic Draw.io visualization. No existing Python library addresses this methodology; the YAML schema, Pydantic models, and pycca interpreter are all original work. The correct approach is schema-first: lock the YAML schema and canonical Draw.io bijection before implementing any MCP tool, because every tool, agent, and skill depends on that contract. Implementing tools before the schema is stable is the single most expensive mistake in this build.

The recommended stack is well-matched to the problem: FastMCP 3.1.0 for the MCP server, Pydantic v2 for schema definition and validation, lxml for deterministic Draw.io XML generation, NetworkX for graph reachability on state machines, and lark for the pycca action language parser. All packages are already installed or available for the Python 3.13 runtime on the dev machine. The primary technical risks are in the Draw.io integration (format instability on save/reload, bijection breaks from freeform edits) and in the session boundary design for Claude Code skills (context is stateless; all design rationale must be written to disk).

The Milestone 1 exit criterion is a verified behavioral model: YAML schema locked, all 8 MCP tools functional, all Phase 0 skills working end-to-end, and at least one domain model validated through the full `discuss-domain → discuss-class → discuss-state → review-model → verify-model` workflow. Phase 2 (configure-target, plan-roadmap, TRANSLATION.md) is explicitly out of scope for Milestone 1 and should not be started until the Phase 0 workflow is stable.

## Key Findings

### Recommended Stack

The stack is anchored by Python 3.13 + FastMCP 3.1.0 for the MCP server. FastMCP's `@mcp.tool()` decorator pattern makes tool registration straightforward; tools are stateless functions that read from and write to disk, with no in-memory state between calls. Pydantic v2 serves as the runtime schema — defining `DomainModel`, `ClassDef`, `Association`, `StateMachine`, `State`, `Transition`, and `DomainBridge` as Pydantic models gives both validation and serialization in one layer. The pycca action language embedded in YAML string blocks requires a dedicated lark parser rather than trying to evaluate or regex-match the strings.

One critical ecosystem gap: there is no usable Python library for Shlaer-Mellor tooling. Leon Starr's `modelint` tooling targets Micca (not pycca) and uses an incompatible model format. The pycca compiler is a C binary invoked via `subprocess`. This is expected and acceptable — building from scratch is the correct approach regardless.

**Core technologies:**
- Python 3.13: Runtime — current stable, asyncio improvements benefit MCP tool handlers
- FastMCP 3.1.0: MCP server framework — de facto Python MCP library; wraps low-level SDK with decorators and stdio transport
- Pydantic 2.12.5: Schema definition and validation — Rust core gives runtime speed; defines YAML schema as typed Python objects
- lxml 6.0.2: Draw.io XML generation — fastest XML library; required for namespace-aware attribute handling in canonical schema
- NetworkX 3.6.1: Graph reachability — `DiGraph` + `nx.descendants()` for unreachable state detection; BFS trap state detection
- lark 1.3.1: pycca parser — EBNF grammar; used by both simulation interpreter and static validation pre-parser
- ruamel.yaml 0.19.1: Write-back with comment preservation — use instead of PyYAML for write operations on human-edited files
- uv 0.10.8: Package management — already installed; `uv add`, `uv run`, `uv.lock` for the `mdf-server/` package

### Expected Features

The feature set divides cleanly into three layers: YAML schemas + templates (the contract), MCP tools (the primitives), and Phase 0 skills (the UX). All three must be present at Milestone 1; none of the three can be partially delivered without breaking the others.

**Must have (table stakes — Milestone 1):**
- YAML model schema: classes with stereotypes/attributes/identifiers, associations with multiplicity/verb phrases, state machines with pycca action language, domain bridges
- Canonical Draw.io schema: 1:1 bijection with YAML — each YAML element maps to exactly one shape type
- `read_model`, `write_model`, `list_domains` — foundational CRUD primitives
- `validate_model` with graph reachability — structural correctness cannot be delegated to AI review
- `render_to_drawio` — deterministic, idempotent YAML → Draw.io XML
- `simulate_state_machine` — pycca interpreter; behavioral verification is the core value
- `validate_drawio`, `sync_from_drawio` — closes the visual review loop
- `/mdf:new-project`, `/mdf:discuss-domain`, `/mdf:discuss-class`, `/mdf:discuss-state` — three-stage design conversation
- `/mdf:review-model`, `/mdf:verify-model` — visual gate and behavioral verification
- `/mdf:pause`, `/mdf:resume` — session boundary handling; single-session-only workflow is a hard failure
- DOMAINS.md, behavior doc templates, folder structure bootstrapped by `/mdf:new-project`

**Should have (differentiators that make Milestone 1 genuinely useful):**
- Actionable validation error messages: `{issue, location, value, fix}` not pass/fail boolean
- Session summary artifact in `/mdf:pause` capturing decisions, open questions, rationale — not just a git checkpoint
- `validate_model` pycca pre-parser: catches undefined attribute references before simulation (can be scoped as Phase 2 if explicitly deferred)
- Stable, semantically meaningful cell IDs in Draw.io XML (e.g., `class-Motor`, `assoc-Controller-Motor-0`) — required for round-trip stability

**Defer to Phase 2 / v1.x:**
- `/mdf:configure-target` — execution domain generation for a specific target (blocked on Phase 0 stability)
- `/mdf:plan-roadmap` — GSD handoff (blocked on configure-target)
- TRANSLATION.md template — needed for configure-target

**Defer to v2+:**
- Multi-target support, Micca DSL output, model diff/merge tooling, Scrall action language

### Architecture Approach

The architecture is a strict three-layer stack: Skills (Markdown files in `.claude/skills/mdf/`) → Agents (spawned subagents) → MCP Tools (Python/FastMCP in `mdf-server/`). The discipline is "Tools are dumb; Skills are smart": tools do exactly one deterministic thing; all workflow logic, questioning sequences, and decision trees live in skills and agents. This separation means skill iteration (file edits) never requires tool redeployment (`pip install`).

The build order is a hard constraint enforced by dependency: YAML schema → `model_io.py` → `validate_model` → `drawio_schema.py` → `render_to_drawio` → `validate_drawio` + `sync_from_drawio` → pycca parser + simulation → skills. Skipping ahead in this sequence causes rework.

**Major components:**
1. `mdf-server/` (Python package) — all 8 MCP tools, YAML schema (Pydantic), Draw.io schema, graph validators, pycca parser + interpreter
2. `.claude/skills/mdf/` (Markdown skill files) — `/mdf:*` commands; UX + workflow sequencing; spawn agents; manage session resume
3. `templates/` — YAML and Markdown templates for artifacts agents produce (DOMAINS.md, CLASS_DIAGRAM, STATE_DIAGRAM, behavior docs)
4. `.design/` (runtime, not in repo) — created by `/mdf:new-project`; model YAML files, Draw.io files, behavior docs for the specific project being designed

### Critical Pitfalls

1. **Draw.io XML format instability** — Draw.io's XML (mxCell/mxGraph) has no version contract. When users save a generated file, Draw.io may mutate attributes, reorder elements, or change IDs. Prevention: test the full generate → open → save → diff cycle during schema design; design `sync_from_drawio` to parse by semantic meaning only (shape type + labels), not attribute order or style string content; use stable deterministic cell IDs, never Draw.io auto-generated IDs.

2. **Bijection broken by freeform edits** — Engineers will add annotations, text boxes, or custom connectors to Draw.io diagrams. `sync_from_drawio` must never error on unrecognized elements — it must parse canonical elements, report ignored elements as warnings, and silently discard them. Design the tolerance policy at schema time.

3. **pycca action language invisible to validation** — `validate_model` sees pycca blocks as plain strings. Errors (undefined attribute references, syntax errors) are deferred to simulation runtime. Prevention: implement a pycca pre-parser as part of `validate_model` that checks at minimum: syntax structure and resolution of identifiers against the class model. Can be Phase 2 scope but must be explicitly acknowledged as a gap if deferred.

4. **Skill session boundary / context loss** — Claude Code sessions are stateless. Design rationale discussed conversationally but not written to disk is permanently lost. Every skill must write decisions to disk as its final action. Behavior docs must capture rationale, not just structure. `/mdf:pause` must produce a session summary with decisions made, pending items, and constraints — not just a git commit.

5. **YAML schema drift between versions** — YAML files have no embedded version. If the schema evolves after model files exist, old files fail with cryptic errors. Prevention: add `schema_version` to every domain YAML file from day one; validator checks this first; write migration scripts for any schema changes after v1 release.

## Implications for Roadmap

Based on the hard dependency chain in the architecture and the critical pitfalls that must be addressed at specific phases, the suggested milestone structure is:

### Phase 1: Schema Foundation
**Rationale:** Every other deliverable — MCP tools, agents, skills — depends on the YAML schema and canonical Draw.io schema being locked. This is not optional ordering; it is a hard architectural constraint. Starting tool implementation without a stable schema means rewriting tools when the schema stabilizes.
**Delivers:** Pydantic models for `DomainModel`, `ClassDef`, `Association`, `StateMachine`, `State`, `Transition`, `DomainBridge`; canonical Draw.io element definitions with bijection mapping; `schema_version` field; JSON schema publication artifact; DOMAINS.md and behavior doc templates
**Addresses:** YAML schema (table stakes), canonical Draw.io schema (differentiator), DOMAINS.md template, `schema_version` field (pitfall prevention)
**Avoids:** Pitfalls 1 (Draw.io format — test generate/save/diff cycle now), 8 (schema drift — version from the start)
**Research flag:** Standard patterns — Pydantic v2 model definition is well-documented; no research-phase needed. The pycca syntax subset needs to be precisely specified (from project design docs, not external research).

### Phase 2: MCP Primitive Tools
**Rationale:** With schema locked, tools can be implemented against a stable contract. The build order within this phase follows the schema dependency: `model_io` first, then `validate_model`, then Draw.io tools, then simulation. Each tool is independently testable.
**Delivers:** All 8 MCP tools: `list_domains`, `read_model`, `write_model`, `validate_model` (graph reachability + structural checks), `render_to_drawio`, `validate_drawio`, `sync_from_drawio`, `simulate_state_machine`; pytest suite for each tool; round-trip test (YAML → XML → sync → YAML → compare)
**Uses:** FastMCP 3.1.0, Pydantic v2, lxml, NetworkX, lark, ruamel.yaml, defusedxml
**Implements:** `mdf-server/` Python package structure (tools/, schema/, pycca/ modules)
**Avoids:** Pitfall 5 (context window — progressive disclosure; `read_model` returns domain only; validate returns issue list not full model), Pitfall 6 (graph reachability edge cases — define exactly what is checked), Pitfall 7 (tool descriptions as selection signal — cross-reference sibling tools in each description)
**Research flag:** Needs `/gsd:research-phase` before implementing `simulate_state_machine` — pycca grammar specification needs to be derived from project docs and verified against the pycca compiler's expected input format. All other tools follow standard patterns.

### Phase 3: Phase 0 Skills
**Rationale:** Skills depend on all MCP tools being available and stable. Skills are the UX layer — they evolve fastest and should be built last against a stable tool API. The session boundary design (pause/resume) must be the first skill implemented, because every other skill depends on the read-reconstruct pattern.
**Delivers:** All Phase 0 skills: `/mdf:new-project`, `/mdf:discuss-domain`, `/mdf:discuss-class`, `/mdf:discuss-state`, `/mdf:review-model`, `/mdf:verify-model`, `/mdf:pause`, `/mdf:resume`; agent prompt files for Domain Architect, Domain Verifier, Class Diagram Agent, State Diagram Agent, Simulation Test Generator; session summary artifact schema; folder structure templates
**Addresses:** All Phase 0 skills (table stakes), Domain-Verifier integration, session state reconstruction (differentiator)
**Avoids:** Pitfall 4 (session boundary — pause/resume protocol is a hard requirement; define session-summary artifact schema before implementing any skill), Pitfall 3 (pycca invisible to validation — surface pycca pre-parser gap explicitly in verify-model documentation)
**Research flag:** `/mdf:discuss-domain` agent prompt design may benefit from a research-phase on effective engineering question elicitation patterns for xUML domain analysis. All other skills follow standard patterns from the design docs.

### Phase 4: Integration Validation
**Rationale:** End-to-end workflow validation before declaring Milestone 1 complete. Run a real domain through the full chain; expose integration issues that unit tests miss.
**Delivers:** At least one complete domain model (real or synthetic) that passes the full `discuss-domain → discuss-class → discuss-state → review-model → verify-model` workflow; acceptance against the "looks done but isn't" checklist from PITFALLS.md; GUIDELINES.md updated with any workflow corrections
**Avoids:** All pitfalls — this phase exists to verify pitfall prevention strategies worked

### Phase Ordering Rationale

- Schema must precede tools: all tools import from `schema/`; tools written against an undefined schema need rewriting
- Tools must precede skills: skills call tools by name via MCP protocol; skills written before tools exist cannot be tested
- Session boundary (pause/resume) must be designed before other skills: the read-reconstruct pattern is the foundation of every skill's session initialization block
- Draw.io round-trip test (generate → open → save → diff) must happen in Phase 1 (schema design), not Phase 2 (tool implementation) — this is pitfall 1's prevention strategy and it must inform the canonical schema before the parser is written

### Research Flags

Phases needing `/gsd:research-phase` during planning:
- **Phase 2, `simulate_state_machine`:** pycca grammar specification and lark grammar implementation — pycca is a real compiler's input language and the grammar must be derived from the actual compiler behavior; training knowledge is MEDIUM confidence here
- **Phase 3, `/mdf:discuss-domain` agent prompt:** xUML domain questioning methodology — effective elicitation patterns for Shlaer-Mellor domain analysis are methodology-specific; design docs provide guidance but agent prompt quality matters

Phases with standard patterns (skip research-phase):
- **Phase 1, YAML schema:** Pydantic v2 model definition is thoroughly documented; schema structure is fully specified in project design docs
- **Phase 2, `validate_model` graph reachability:** NetworkX DiGraph + BFS is standard; pitfall 6 specifies exactly what edge cases to handle
- **Phase 2, `render_to_drawio`:** lxml XML generation is standard; canonical schema mapping is defined at Phase 1
- **Phase 3, skill session handling:** Session reconstruct pattern is fully specified in ARCHITECTURE.md Pattern 2

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Package versions verified from PyPI; FastMCP 3.x API should be verified against gofastmcp.com before implementation (training cutoff August 2025; FastMCP 3.x released after cutoff) |
| Features | HIGH | Derived directly from project design documents; not inferred from external domain research |
| Architecture | HIGH | Architecture is locked in design documents; component boundaries and data flows are explicitly specified |
| Pitfalls | MEDIUM | Pitfalls 2, 4, 5, 8 are HIGH confidence (derived from project design constraints); Pitfalls 1, 3, 6, 7 are MEDIUM (training knowledge of Draw.io format, FastMCP behavior, graph algorithm edge cases) |

**Overall confidence:** HIGH — this project's research is primarily drawn from its own detailed design documents, not external sources. The main uncertainty area is FastMCP 3.x API specifics.

### Gaps to Address

- **FastMCP 3.x API verification:** Training cutoff predates FastMCP 3.x stable release. Before implementing any MCP tool, verify the `@mcp.tool()` decorator API and tool description field name against gofastmcp.com documentation. Risk is LOW — even if API details differ, the conceptual approach is sound.
- **pycca grammar scope:** The exact subset of pycca syntax to support in the lark grammar is not fully specified in design docs. The pycca compiler (C binary) is the reference implementation. Before implementing the parser, derive the supported grammar from the compiler's expected input format. A `/gsd:research-phase` on this is recommended.
- **Draw.io XML save behavior:** The generate → save → diff test must be run against the current Draw.io version during schema design (Phase 1). The exact mutations Draw.io makes on save cannot be known until tested — this is the foundation of the `sync_from_drawio` parser's tolerance policy.
- **modelint ecosystem current state:** Leon Starr's tooling was assessed from training knowledge; current state may differ. Low risk — even if modelint has evolved, the schema mismatch means building from scratch is correct regardless.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — requirements, key decisions, constraints
- `docs/plans/2026-03-05-mdf-development-workflow.md` — Phase 0–2 workflow design, agent responsibilities, skill list
- `docs/plans/2026-03-04-model-based-project-framework-design.md` — MCP tool design, YAML schema examples, approach rationale
- `docs/plans/milestone2-flow.md` — Phase 3+ agent analysis, GSD integration contract
- `.planning/GUIDELINES.md` — MCP tool design principles, skill design principles, YAML conventions, canonical Draw.io schema requirement
- PyPI index queries — version numbers for all libraries

### Secondary (MEDIUM confidence)
- Training knowledge — FastMCP 3.x API (verify against gofastmcp.com before use), Draw.io mxGraph XML format, NetworkX graph algorithms, lark EBNF grammar patterns, Claude Code session model behavior
- Training knowledge — pycca action language syntax (verify against pycca compiler reference before grammar implementation)

### Tertiary (LOW confidence)
- Training knowledge — Leon Starr's modelint ecosystem current state (irrelevant to build decisions; building from scratch is correct regardless)

---
*Research completed: 2026-03-05*
*Ready for roadmap: yes*
