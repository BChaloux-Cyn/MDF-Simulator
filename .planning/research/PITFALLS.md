# Pitfalls Research

**Domain:** MCP server + YAML schema + Draw.io generation + state machine validation + Claude Code skills
**Researched:** 2026-03-05
**Confidence:** MEDIUM — web tools unavailable; based on training knowledge of FastMCP, Draw.io XML internals, PyYAML, and Claude Code skill patterns. Confidence is HIGH for pitfalls derived directly from the project's own design decisions (bijection constraint, pycca in YAML, session boundary design).

---

## Critical Pitfalls

### Pitfall 1: Draw.io XML Is Not a Stable, Documented Format

**What goes wrong:**
`render_to_drawio` produces XML that opens correctly in today's Draw.io but breaks silently in a future version, or produces XML that Draw.io opens but cannot save back without mutating the structure. The canonical schema you define today may have cells, IDs, or attributes that Draw.io's importer strips, rewrites, or duplicates on save.

**Why it happens:**
Draw.io's XML format is an implementation detail of a desktop/web app, not a published standard. The `mxCell` / `mxGraph` XML schema has no version contract. Attributes like `style`, `vertex`, `edge`, `parent`, and `source`/`target` are coupled to the renderer's internal graph model. When users save a file from Draw.io after viewing your generated XML, Draw.io may reformat, add, or remove attributes — and your `sync_from_drawio` parser then receives structurally different XML than what was generated.

**How to avoid:**
- Do not depend on attribute order, namespace prefixes, or style string content during parsing in `sync_from_drawio`.
- Parse by semantic meaning only: find cells with your canonical shape type, extract the text labels, extract source/target IDs from edge cells.
- During schema design (Phase 1), open generated XML in Draw.io, save it without changes, and diff the before/after XML. Identify all mutations Draw.io makes on save. Design your parser to tolerate all of them.
- Assign stable, semantically meaningful `id` attributes to every cell (e.g., `class-Motor`, `assoc-Controller-Motor-0`) rather than relying on Draw.io's auto-generated IDs, which change on re-import.

**Warning signs:**
- `sync_from_drawio` fails after the user does a save-as or export from Draw.io.
- Round-trip test passes when you control both ends but fails when a real Draw.io save is in the middle.
- Shape IDs in parsed XML do not match IDs in generated XML.

**Phase to address:**
Schema definition phase (Phase 1). The canonical schema must be tested against real Draw.io save-load cycles before the `sync_from_drawio` tool is written.

---

### Pitfall 2: The Bijection Breaks on the First Freeform Edit

**What goes wrong:**
A user opens a class diagram in Draw.io, adds a text annotation ("TODO: refine this later"), resizes a shape, or draws a connector that has no YAML equivalent. `sync_from_drawio` either fails entirely or silently drops the unrecognized element. If it silently drops it, the user has no idea their annotation was discarded. If it errors, the user is stuck — they cannot get back to YAML without deleting their edit.

**Why it happens:**
The bijection constraint assumes the Draw.io file contains only canonical elements. But Draw.io is a free-form diagramming tool — nothing prevents the user from adding arbitrary content. The parser has no graceful handling for out-of-schema elements.

**How to avoid:**
- Design `sync_from_drawio` to be tolerant, not strict: parse canonical elements, ignore unrecognized ones, and report them explicitly in the return value as warnings (not errors).
- Return a structured diff: "Parsed 3 classes, 2 associations. Ignored 1 unrecognized element (text box at position 400,200). These elements are not persisted to YAML."
- Never error on unknown elements — only error on elements that are recognizable but semantically invalid (e.g., an association connector with a missing or unknown target class).
- Document clearly for users: "Annotations, colors, and freeform shapes are visual only and will not sync back to the model."

**Warning signs:**
- User reports "my notes disappeared."
- `sync_from_drawio` throwing parsing exceptions on files that "look fine" in Draw.io.

**Phase to address:**
Phase 1 (schema) and Phase 2 (`sync_from_drawio` tool implementation). The parser's tolerance policy must be defined at schema time, not discovered during tool implementation.

---

### Pitfall 3: pycca Action Language in YAML String Blocks Is Invisible to Validation

**What goes wrong:**
Action language embedded in YAML string blocks is opaque to `validate_model`. A typo in a pycca statement, a reference to a nonexistent class attribute, or a call to an undefined method is invisible until `simulate_state_machine` actually executes that action — which may be much later in the workflow, or never if that state transition is never reached in a test.

**Why it happens:**
PyYAML loads pycca blocks as plain strings. The YAML schema validator sees a valid string. The semantic content is only evaluated when the pycca interpreter runs it. This is the classic "late binding" problem: errors are deferred to runtime.

**How to avoid:**
- Implement a pycca pre-parser as part of `validate_model`. It does not need to fully evaluate the action language — it needs to:
  1. Parse the pycca syntax (check for basic structural errors: unclosed blocks, malformed statements).
  2. Resolve identifiers against the class model: attribute names, method names, class names referenced in action bodies.
- Flag unresolvable references as validation issues, not simulation errors.
- For Phase 1, a minimal pycca lexer that catches syntax errors is sufficient. Full semantic resolution can be Phase 2.

**Warning signs:**
- `validate_model` returns no errors but `simulate_state_machine` raises a `NameError` or `AttributeError`.
- Action language edits never trigger validation failures — any string is accepted.

**Phase to address:**
Phase 2 (MCP tool implementation). The pycca pre-parser is a separate deliverable from the state machine graph validator. It should be scoped explicitly, not assumed to be part of YAML schema validation.

---

### Pitfall 4: Claude Code Skills Lose State on Every Session Boundary

**What goes wrong:**
A multi-session design workflow (`/mdf:discuss-domain`, `/mdf:discuss-class`, etc.) assumes accumulated conversational context. When the user runs `/mdf:discuss-class` in a new Claude Code session, the previous conversation about domain boundaries, naming decisions, and rationale is gone. Claude must reconstruct intent from disk artifacts alone. If the YAML files and behavior docs are incomplete or ambiguous, Claude makes decisions that contradict earlier sessions — producing model inconsistencies that are hard to trace.

**Why it happens:**
Claude Code sessions are stateless. The skill's CLAUDE.md or system prompt cannot embed a complete conversation history. Only what is written to disk persists. If a design decision was reached conversationally but never written as a comment or doc update, it is lost.

**How to avoid:**
- Every skill must write its decisions to disk before the session ends — not as a separate manual step, but as a mandatory final action of the skill itself.
- Behavior docs (`.design/behavior/<domain>/domain.md`, etc.) must capture rationale, not just structure. "Motor has three states: Idle, Running, Fault. Fault is terminal because hardware reset is required — this was a deliberate design decision." is valid and necessary.
- Each skill's first action is to call `list_domains()` and `read_model()` for relevant domains — reconstructing state from disk, not from memory.
- `/mdf:pause` must write a session-summary artifact capturing: what was decided, what is pending, what constraints were discovered.
- `/mdf:resume` must read that summary and confirm context before proceeding.

**Warning signs:**
- Claude asks a question in session 3 that was answered in session 1.
- Model inconsistencies that appear between one skill invocation and the next.
- Behavior docs that describe structure but not rationale.

**Phase to address:**
Phase 3 (skill implementation). The pause/resume protocol is a hard requirement, not a nice-to-have. Define the session-summary artifact schema before implementing any skill.

---

### Pitfall 5: MCP Tool Return Size Exceeds Claude's Context Budget

**What goes wrong:**
`read_model(domain)` is called for a large domain with dozens of classes and state machines. The returned YAML is thousands of lines. Combined with the ongoing conversation, MCP tool results accumulate in the context window and crowd out working space. Claude starts hallucinating or truncating its responses because the context is full.

**Why it happens:**
MCP tool results are injected into the conversation context. There is no streaming, no pagination, and no truncation — the full return value appears in context. A single domain YAML file for a non-trivial embedded system can be 500–2000 lines.

**How to avoid:**
- Design `read_model` to return one domain at a time — which is already planned — but also add a focused variant: `read_class(domain, class_name)` that returns only one class's definition including its state machine.
- `list_domains()` must return names only, never content.
- `validate_model` returns a list of issues, not the full model with annotations.
- `render_to_drawio` returns the XML but does not echo the input YAML.
- Apply the "progressive disclosure" principle from GUIDELINES.md aggressively: every tool should return the minimum information needed for the current step, with drill-down available on demand.

**Warning signs:**
- Skill becomes slow or inconsistent as the model grows.
- Claude stops calling validation tools mid-session as context fills.
- `read_model` return value is longer than the preceding conversation.

**Phase to address:**
Phase 2 (MCP tool implementation). Tool return scoping must be a first-class design consideration, not a post-hoc optimization.

---

### Pitfall 6: Graph Reachability Misses Compound Initial State and Self-Transitions

**What goes wrong:**
`validate_model`'s graph reachability check runs BFS/DFS from the declared `initial` state. It correctly marks reachable states. But it misses:
1. A state that is only reachable via a self-transition from another state (BFS visits it via the self-loop, so it appears reachable, but it cannot be entered from outside — it is only "re-entered").
2. An initial state that has no outgoing transitions — it is not a trap state in the tool's logic (it has no outgoing transitions but is the initial state, so it may be declared terminal intentionally).
3. States reachable only under guards that are always false (logically unreachable but structurally reachable).

**Why it happens:**
Structural graph reachability is necessary but not sufficient for behavioral completeness. Guards are conditions, not structure — a purely structural BFS cannot evaluate guard expressions.

**How to avoid:**
- Define precisely what the validator checks and what it does not: "structural reachability from initial state, ignoring guard conditions." Document this limitation.
- For trap state detection: a state is a trap if it has no outgoing transitions AND is not declared `terminal: true`. Apply this regardless of whether the state is the initial state — a terminal initial state is unusual and should produce a warning.
- For self-transitions: do not count self-transitions when determining trap state status (a state with only self-transitions cannot escape).
- Guard-condition reachability is not a v1 concern — flag it as a known limitation in validator output.

**Warning signs:**
- Validator reports no unreachable states, but simulation gets stuck in a state with no way out.
- Initial state with no outgoing transitions does not trigger a warning.

**Phase to address:**
Phase 2 (validator implementation). The exact semantics of each check must be specified before implementation, not discovered during testing.

---

### Pitfall 7: FastMCP Tool Descriptions Are the Selection Signal — Bad Descriptions Mean Wrong Tool Calls

**What goes wrong:**
Claude selects MCP tools based on the `description` field. Two tools with similar-sounding descriptions get confused. Claude calls `validate_drawio` when it should call `validate_model` (or vice versa), or calls `render_to_drawio` when the user only asked to validate. Each wrong tool call costs a round-trip and may mutate state unexpectedly if write tools are called when only read was intended.

**Why it happens:**
Tool descriptions are written at implementation time when the developer knows exactly which tool to use. But Claude must select tools from natural language context without that developer knowledge. Generic descriptions ("validate model", "render diagram") do not disambiguate.

**How to avoid:**
- Follow GUIDELINES.md's guidance: write descriptions as prompts with explicit when-to-use-this-vs-that guidance.
- For each tool that has a sibling: `validate_model` description should say "validates the YAML source model for structural consistency — NOT for Draw.io XML. Use validate_drawio for XML." `validate_drawio` should say the reverse.
- Include the precondition: "Call after write_model to confirm the saved state is valid" or "Call before sync_from_drawio to check the XML conforms to the canonical schema."
- Add a `list_tools()` meta-tool that returns a one-line description of each tool with its primary use case — helps Claude orient at the start of a session.

**Warning signs:**
- Claude calls the wrong tool and then has to recover.
- Skills need to explicitly tell Claude which tool to call (rather than letting the description do the work).
- Multiple tool calls for a single logical operation when one should have been sufficient.

**Phase to address:**
Phase 2 (MCP tool implementation). Tool descriptions are as important as tool implementations — they should be reviewed and tested as part of the tool's acceptance criteria.

---

### Pitfall 8: YAML Schema Drift Between Tool Versions and Model Files

**What goes wrong:**
The YAML model schema evolves during development. A `domain.yaml` file written against schema v1 uses `transitions[].guard` but the validator in schema v2 expects `transitions[].condition`. Old model files silently fail validation in ways that are hard to diagnose — the validator says "missing field `condition`" but the file has `guard` and the user has no idea why.

**Why it happens:**
YAML files have no embedded schema version. PyYAML loads any well-formed YAML without complaint. The schema is enforced only by the validator logic, which may have changed since the file was written.

**How to avoid:**
- Add a `schema_version` field to every domain YAML file. The validator checks this first and immediately rejects files with the wrong version with a clear error: "This model was written for schema v1. Current schema is v2. See migration guide."
- For v1, define the schema completely before writing any model files. Do not evolve the schema after model files exist without writing a migration script.
- Use `jsonschema` or `pydantic` to validate YAML structure — not manual key-checking in Python code. This makes the schema explicit and testable.

**Warning signs:**
- Validation errors mention fields that "definitely exist" in the file.
- Different domains validate successfully under some tool versions but not others.
- The validator's error messages reference field names not in the YAML.

**Phase to address:**
Phase 1 (schema design). The schema must be versioned and formally specified before any model files are created.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Parse Draw.io XML with string search / regex instead of an XML parser | Faster to implement | Breaks on attribute reordering, namespace changes, encoding edge cases. Unmaintainable. | Never |
| Skip pycca pre-parser, validate only YAML structure | Faster Phase 2 delivery | pycca errors only surface during simulation, which may be much later in the workflow | Only if pycca pre-parser is explicitly scoped as Phase 3 and documented as a known gap |
| Use Draw.io auto-generated cell IDs instead of canonical IDs | No ID management code needed | sync_from_drawio cannot match cells between generate and re-import because IDs change | Never |
| Single large `validate_model` function | Faster to write | Untestable, hard to extend, errors are mixed across validation types | Never — separate graph reachability, referential integrity, and pycca checks |
| Store session context in Claude's working memory across turns | Simpler skill implementation | Lost at next session boundary — breaks multi-session workflow entirely | Never — always write to disk |
| Accept any string for action language fields without parsing | No parser to build | Late errors in simulation with no traceability to model location | Acceptable in Phase 1 if explicitly noted; must be resolved before Phase 2 simulation work |
| Read entire model (all domains) for every operation | Simpler context management | Context window exhaustion; Claude behavior degrades on large models | Never — one domain at a time is an architectural constraint |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| YAML → Draw.io XML | Generating XML with Python string formatting / f-strings | Use `xml.etree.ElementTree` or `lxml` to build the XML tree programmatically; avoids encoding bugs and malformed XML |
| Draw.io XML → YAML | Parsing XML with regex or BeautifulSoup string search | Use ElementTree with namespace-aware XPath; match on `tag` and `attrib`, not string content |
| FastMCP tool → Claude | Tool return value contains Python dict/object | FastMCP auto-serializes to JSON — verify the serialized form is what Claude actually reads; nested objects may lose type information |
| pycca string blocks → Python | Using `eval()` or `exec()` to interpret pycca | pycca is NOT Python — implement a dedicated interpreter or use a parser combinator library. Never exec user-provided strings. |
| YAML string blocks with multiline pycca | Using YAML literal block scalar (`|`) without understanding chomping | `|` preserves newlines; `|-` strips trailing newline. Using the wrong one can add/remove newlines that affect pycca parsing |
| Claude Code skill → MCP server | MCP server not running when skill is invoked | FastMCP in stdio mode starts fresh per invocation — no persistent state in the server process itself. All state must be on disk. |
| `/mdf:pause` → `/mdf:resume` | Assuming Claude reconstructs intent from model YAML alone | Model YAML captures structure, not conversational context. The session summary artifact must capture in-progress decisions, open questions, and rationale. |
| validate_model → skill workflow | Skill continues after validation errors without surfacing them to user | Always surface validation results before proceeding to next stage. Validation errors are not optional. |

---

## Performance Traps

This project does not have scale concerns in the traditional sense (not serving 10k users). Performance traps are context-budget traps.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Reading all domains into context for every operation | Skill becomes slow; Claude's responses become shorter and less accurate | list_domains() then read only the domain being worked on | Models with more than ~3 domains |
| validate_model returning full YAML with annotations instead of issue list | Context fills with model + validation output; no room for response | Validation returns structured issue list only — never the full model | First validation of a non-trivial domain |
| render_to_drawio + validate_drawio in the same turn for every edit | Two large payloads (YAML in + XML out + XML in + validation result) fill context | Only render when explicitly asked; validate is a separate explicit step | Every model edit cycle |
| Session summary artifact for pause/resume containing full model content | Resume loads a huge artifact that fills context before the conversation starts | Session summary contains pointers (domain names, class names, open questions) — not model content | After 2+ sessions with a large model |

---

## "Looks Done But Isn't" Checklist

- [ ] **YAML schema:** Has a `schema_version` field and the validator checks it before all other validation
- [ ] **Draw.io generation:** Generated XML has been opened in Draw.io, saved, and the save result has been diffed against the generated XML — parser handles all differences
- [ ] **Bijection:** A round-trip test exists: YAML → XML → sync_from_drawio → YAML → compare. Passes without user intervention.
- [ ] **Graph reachability:** Validator catches both unreachable states (no path from initial) AND trap states (no path out, not declared terminal)
- [ ] **Trap state detection:** Self-transitions do not prevent a state from being classified as a trap
- [ ] **pycca validation:** validate_model catches at minimum a reference to an undefined class attribute in an action body
- [ ] **Session boundary:** `/mdf:resume` can reconstruct current work from disk alone, in a fresh Claude Code session, with no prior context
- [ ] **Tool descriptions:** Each tool that has a sibling with similar purpose explicitly names the sibling and says when NOT to use this one
- [ ] **Return size:** `read_model(domain)` for the largest expected domain YAML file fits comfortably in context alongside a full conversation (~2000 tokens or less)
- [ ] **Idempotency:** `render_to_drawio` called twice on the same model produces identical XML (not different cell IDs each time)

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Draw.io format breaks on version upgrade | HIGH | Re-derive canonical schema against new version; rewrite sync_from_drawio parser; test all existing model files |
| Bijection broken by freeform user edits | LOW | Document which elements are non-canonical; user deletes them; re-sync |
| pycca syntax error discovered late in simulation | MEDIUM | Locate action block in YAML (validate_model now reports line/field); fix in YAML; re-validate; re-simulate |
| Session context lost — model has inconsistencies | MEDIUM | Run validate_model on all domains to find structural errors; review behavior docs for rationale; re-run affected skill from last clean state |
| MCP tool returns too much context — session degraded | LOW | Start new session; use more focused tool calls (read_class not read_model) |
| YAML schema drift — old model file fails validation | MEDIUM | Write migration script from v(N-1) to v(N); run on all model files; re-validate |
| Wrong tool called due to ambiguous description | LOW | Update tool description; re-run the failed operation |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Draw.io XML format instability | Phase 1: Schema design | Round-trip test through real Draw.io save; diff XML before/after |
| Bijection broken by freeform edits | Phase 1: Schema + Phase 2: sync_from_drawio tolerance policy | sync_from_drawio returns warnings for unrecognized elements instead of erroring |
| pycca action language invisible to validation | Phase 2: MCP tools — pycca pre-parser | validate_model catches undefined attribute reference in action body |
| Skill session boundary / context loss | Phase 3: Skill implementation — pause/resume protocol | resume-from-cold-session test: fresh session, no prior context, /mdf:resume reconstructs correctly |
| Context window exhaustion from large tool returns | Phase 2: MCP tool design | read_model on largest test domain fits in context with conversation history |
| Graph reachability edge cases | Phase 2: Validator implementation | Validator test suite covers: unreachable state, trap state, trap via self-loop only, terminal initial state |
| Wrong MCP tool called | Phase 2: Tool descriptions | Skill acceptance test includes cases where sibling tools exist — Claude calls the correct one |
| YAML schema drift | Phase 1: Schema versioning | Validator rejects file with wrong schema_version with actionable message |

---

## Sources

- Project design docs: `.planning/PROJECT.md`, `docs/plans/2026-03-04-model-based-project-framework-design.md`, `docs/plans/2026-03-05-mdf-development-workflow.md`
- Project guidelines: `.planning/GUIDELINES.md` (MCP tool design principles, session boundary design, canonical Draw.io schema constraint, graph reachability requirement)
- Training knowledge: FastMCP Python library behavior (stdio transport, tool description as selection signal, JSON serialization of return values)
- Training knowledge: Draw.io XML mxGraph format (mxCell structure, attribute instability, ID generation behavior, style string format)
- Training knowledge: PyYAML behavior (string block chomping, type coercion, no schema enforcement by default)
- Training knowledge: Claude Code session model (stateless, context window limits, MCP tool result injection into context)

**Confidence notes:**
- HIGH confidence: Pitfalls 2, 4, 5, 8 — derived directly from the project's own design constraints (bijection requirement, session boundary design, one-domain-at-a-time constraint, no schema versioning yet)
- MEDIUM confidence: Pitfalls 1, 3, 6, 7 — based on training knowledge of the relevant technologies; web verification was unavailable
- All pitfalls are specific to this system's component combination — not generic software development advice

---
*Pitfalls research for: MDF v1.0 — MCP server + YAML schema + Draw.io + skills*
*Researched: 2026-03-05*
