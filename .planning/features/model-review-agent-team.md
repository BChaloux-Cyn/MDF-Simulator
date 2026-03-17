# Feature: Model Review Agent Team

**Status:** Design-in-progress — not yet planned or implemented
**Last updated:** 2026-03-17

---

## Purpose

A Claude Code agent team that reviews an MDF domain model and produces a structured findings report. The team surfaces behavioral holes, ambiguities, and structural inconsistencies that static validation (`validate_model`) cannot catch — things like unreachable states, guard coverage gaps, cross-class event routing errors, and scenario dead-ends.

Ambiguous behavior is never assumed correct. When an agent cannot determine intent from the model alone, it escalates to the user, documents the question and answer, and continues.

---

## Deliverables

- `REVIEW.md` — structured findings report (one section per review domain, severity-rated)
- `DECISIONS.md` — log of ambiguity questions posed to the user and the answers given

Both files are written to the model root (`.design/model/<Domain>/`) or a designated output path.

---

## Adaptive Strategy

The orchestrator assesses the model before spawning teammates. Based on what it finds, it chooses one of two modes:

### Mode A — Targeted (well-documented model)

Conditions:
- All states, events, and transitions are present and non-trivial
- Prior reviews or issues exist that already surface known gaps
- `README.md` / `REQUIREMENTS.md` provide clear behavioral intent

The orchestrator reads existing artifacts, builds a targeted task list, and spawns specialized reviewers directly.

### Mode C — Wave (weak or unfamiliar model)

Conditions:
- Action bodies are sparse or missing
- No prior reviews or issues logged
- Documentation does not describe expected behavioral scenarios

**Wave 1:** Spawn 2–3 scout agents for broad coverage. Scouts read the class diagram and all state diagrams, identify surface-level issues, and report back to the orchestrator.

**Wave 2:** Orchestrator synthesizes scout findings into a prioritized task list. Spawns targeted deep-dive agents on flagged areas.

**Wave 3 (if needed):** Deep-dive agents may surface new gaps that require further investigation. Orchestrator decides whether to spawn another round.

---

## Reviewer Roles (Specialized Teammates)

Regardless of mode, the following review domains are assigned as tasks:

| Role | Scope |
|------|-------|
| **State Machine Reviewer** | Unreachable states, dead states (no exit), missing event handling, self-transition loops |
| **Guard Coverage Analyst** | Per-state/event: are guards mutually exclusive and exhaustive? Can an event arrive with no guard matching? |
| **Cross-Class Event Validator** | Every `generate E to X` — does event `E` exist in `X`'s state diagram? Does `X` exist in the class diagram? |
| **Relationship Traversal Checker** | Every `related by self->RN` — does `RN` exist in the class diagram? Is it reachable from `self`'s class? |
| **Scenario Walkthrough Agent** | Traces 1–2 key behavioral scenarios end-to-end (e.g. floor button pressed → dispatcher → elevator → door → completion). Flags dead-ends and missing responses. |

---

## Ambiguity Escalation Protocol

When a reviewer encounters behavior that cannot be determined to be correct or incorrect from the model alone:

1. The teammate sends a message to the lead with the question, context (file + location), and why it is ambiguous.
2. The lead surfaces the question to the user in plain language.
3. The user answers. The lead records the answer and relays it to the teammate.
4. The teammate documents the decision in `DECISIONS.md` under a consistent format:

```
## Decision: <short title>
**Location:** <file path / class / state or transition>
**Question:** <what was ambiguous>
**Answer:** <what the user decided>
**Implication:** <how this affects the model or review finding>
```

Reviewers must not assume ambiguous behavior is correct. If escalation is blocked (user unavailable), the item is flagged as `UNRESOLVED` in the report.

---

## Prompt Template (Orchestrator Lead)

The following prompt is used to launch the review team. Replace `{DOMAIN}` and `{MODEL_PATH}` before running.

```
You are the lead of a model review agent team for an MDF (Model-Driven Framework)
domain model. Your job is to coordinate a thorough behavioral review of the
{DOMAIN} domain and produce a structured findings report.

## Model Location
All model files are in: {MODEL_PATH}
- class-diagram.yaml — classes, attributes, associations
- state-diagrams/*.yaml — one file per active/entity class
- types.yaml — domain-defined types and enums
- README.md / REQUIREMENTS.md (if present) — behavioral intent

## Prior Context to Read First
Before spawning any teammates, read:
1. All files listed above
2. issues/ directory — known open issues
3. Any prior REVIEW.md or DECISIONS.md in the model path

## Step 1 — Assess the Model

Evaluate on two axes:
- Documentation completeness: are action bodies non-trivial and present for all states?
- Prior review coverage: do existing issues or reviews already identify gaps?

Based on your assessment, choose a mode and announce it with a one-paragraph rationale:

**Mode A (Targeted):** Model is well-documented. Spawn specialized reviewers directly
  with precise mandates based on what you found in the existing artifacts.

**Mode C (Wave):** Model is sparse or unfamiliar. Spawn scout agents first, wait for
  their reports, then spawn targeted deep-dive agents on flagged areas.

## Step 2 — Run the Review

Spawn teammates as needed based on your chosen mode. Assign tasks from this list
(not all may apply — use your judgment):
- State Machine Reviewer: unreachable/dead states, missing event handling
- Guard Coverage Analyst: mutually exclusive and exhaustive guards per state/event
- Cross-Class Event Validator: every `generate E to X` — verify E exists in X's diagram
- Relationship Traversal Checker: every `related by self->RN` — verify RN is valid
- Scenario Walkthrough Agent: trace 1-2 key end-to-end behavioral scenarios

## Step 3 — Ambiguity Escalation

When a teammate finds something ambiguous (cannot be determined correct or incorrect
from the model alone), they message you with:
- The question
- The location (file, class, state/transition)
- Why it is ambiguous

You then ask the user. Record the answer in DECISIONS.md using this format:

  ## Decision: <short title>
  **Location:** <file / class / state or transition>
  **Question:** <what was ambiguous>
  **Answer:** <what the user decided>
  **Implication:** <how this affects the model or review>

Do NOT assume ambiguous behavior is correct. Flag it as UNRESOLVED if the user
cannot be reached.

## Step 4 — Synthesize and Write Report

After all teammates finish, write REVIEW.md to {MODEL_PATH} with:
- One section per review domain
- Each finding rated: ERROR | WARNING | INFO
- Distinct section for UNRESOLVED ambiguities
- Summary table at the top

This report is human-reviewed before any findings are filed as issues.
```

---

## Future Work

- [ ] Parameterize the prompt template for multi-domain review
- [ ] Add a `review_model` MCP tool that constructs and launches this team programmatically
- [ ] Define a hook (`TeammateIdle`) to enforce that each reviewer has written at least one finding before going idle
- [ ] Integrate `DECISIONS.md` decisions back into model documentation or schema annotations
