# Terminate Pseudostate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `__terminal__` as a reserved transition destination keyword that renders as a UML terminate pseudostate (circle with X) in Draw.io diagrams.

**Architecture:** `__terminal__` is a virtual sink node, modeled like `__initial__` — it requires no `StateDef`, is injected into the layout graph when any transition targets it, and is emitted as a fixed 20×20 cell. Validation enforces that `__terminal__` has no outgoing transitions and `__initial__` has no incoming transitions.

**Tech Stack:** Python 3.11+, Pydantic v2, lxml, NetworkX, pytest. Virtual environment at `.venv/`. Run tests with `.venv\Scripts\python.exe -m pytest tests/ -v`.

## Global Constraints

- Working directory for all commands: project root (`mdf-simulator/`)
- Test runner: `.venv\Scripts\python.exe -m pytest tests/ -v`
- Do not modify `schema/drawio_canonical.py` or `schema/canonical_builder.py`
- Do not modify `schema/yaml_schema.py` beyond removing `StateDef.terminal`
- `INIT_SIZE` is defined in `tools/drawio.py` — import it in tests via `from tools.drawio import INIT_SIZE`
- `STYLE_STATE` and `STYLE_TERMINATE_PSEUDO` are in `schema/drawio_schema.py`
- All new test state-machine YAML files use `schema_version: "1.0.0"`

---

### Task 1: Add `STYLE_TERMINATE_PSEUDO` to `schema/drawio_schema.py`

**Files:**
- Modify: `schema/drawio_schema.py:11-35` (`__all__`), `:80-113` (constants + `BIJECTION_TABLE`)
- Test: `tests/test_drawio_schema.py`

**Interfaces:**
- Produces: `STYLE_TERMINATE_PSEUDO: str` — importable from `schema.drawio_schema`
- Produces: `BIJECTION_TABLE["terminate_pseudo"]` — maps to `STYLE_TERMINATE_PSEUDO`

- [ ] **Step 1: Write the failing tests**

In `tests/test_drawio_schema.py`, find `REQUIRED_ELEMENT_TYPES` (line 11) and add `"terminate_pseudo"`. Then add a new test at the bottom of the file:

```python
# Change existing set (line 11-14):
REQUIRED_ELEMENT_TYPES = {
    "class", "class_active", "attribute", "separator", "association", "assoc_label",
    "generalization", "state", "initial_pseudo", "transition", "bridge",
    "terminate_pseudo",
}

# Add new test at end of file:
def test_style_terminate_pseudo_nonempty():
    from schema.drawio_schema import STYLE_TERMINATE_PSEUDO
    assert STYLE_TERMINATE_PSEUDO
    assert "mxgraph.uml.terminate" in STYLE_TERMINATE_PSEUDO
    assert "ellipse" in STYLE_TERMINATE_PSEUDO
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\python.exe -m pytest tests/test_drawio_schema.py -v
```

Expected: `test_all_yaml_elements_have_style_constant` FAILS (key count mismatch), `test_style_terminate_pseudo_nonempty` FAILS (ImportError).

- [ ] **Step 3: Add the constant to `schema/drawio_schema.py`**

After `STYLE_INITIAL_PSEUDO` (line 84), add:

```python
STYLE_TERMINATE_PSEUDO = (
    "ellipse;whiteSpace=wrap;html=1;aspect=fixed;"
    "fillColor=#ffffff;strokeColor=#000000;"
    "shape=mxgraph.uml.terminate;"
)
```

In `__all__` (line 11), add `"STYLE_TERMINATE_PSEUDO"` after `"STYLE_INITIAL_PSEUDO"`.

In `BIJECTION_TABLE` (line 101), add after `"initial_pseudo"`:

```python
"terminate_pseudo": STYLE_TERMINATE_PSEUDO,
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\python.exe -m pytest tests/test_drawio_schema.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add schema/drawio_schema.py tests/test_drawio_schema.py
git commit -m "feat: add STYLE_TERMINATE_PSEUDO to drawio_schema"
```

---

### Task 2: Remove `StateDef.terminal` from `schema/yaml_schema.py`

**Files:**
- Modify: `schema/yaml_schema.py:255-257`

**Interfaces:**
- Consumes: nothing
- Produces: `StateDef` no longer has a `terminal` field

- [ ] **Step 1: Verify no tests or fixtures use `terminal: true`**

```
.venv\Scripts\python.exe -m pytest tests/ -v -k "terminal"
```

Expected: no tests collected (the word "terminal" appears only in unrelated comments). Also verify:

```
grep -r "terminal" tests/ --include="*.yaml"
grep -r "\.terminal" schema/ tools/ tests/ --include="*.py"
```

Expected: no hits in YAML fixtures; only `StateDef.terminal` references in `schema/yaml_schema.py` and `tools/validation.py`.

- [ ] **Step 2: Remove the field from `StateDef`**

In `schema/yaml_schema.py`, remove lines 255–257:

```python
# Remove these three lines:
    terminal: bool = False
    """If True, this is a lifecycle-ending state. After the entry_action completes,
    the object instance deletes itself. Terminal states must have no outgoing transitions."""
```

`StateDef` becomes:

```python
class StateDef(BaseModel):
    name: str
    entry_action: str | None = None
```

- [ ] **Step 3: Run full test suite to catch any breakage**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all previously-passing tests still PASS. `tools/validation.py` still references `s.terminal` — this will produce an `AttributeError` at runtime (not at import time), so we must fix `validation.py` in Task 3 before running validation tests.

- [ ] **Step 4: Commit**

```
git add schema/yaml_schema.py
git commit -m "refactor: remove unused StateDef.terminal field"
```

---

### Task 3: Update `tools/validation.py` — referential integrity and reachability

**Files:**
- Modify: `tools/validation.py:436-507`
- Test: `tests/test_terminate_pseudostate.py` (validation tests only — file created here, extended in Task 6)

**Interfaces:**
- Consumes: `StateDef` no longer has `.terminal` (from Task 2)
- Produces: `_check_referential_integrity_state_diagram` rejects `from: __terminal__` and `to: __initial__`, accepts `to: __terminal__`
- Produces: `_check_reachability` no longer uses `s.terminal`; treats `__terminal__` as a virtual sink node

- [ ] **Step 1: Create `tests/test_terminate_pseudostate.py` with validation tests**

Create the file:

```python
"""Tests for __terminal__ pseudostate validation and rendering."""
import yaml
import pytest
from pathlib import Path
from schema.yaml_schema import StateDiagramFile
from tools import validation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sd(transitions_extra: list[dict]) -> StateDiagramFile:
    """Minimal state diagram with Active and Closing states, plus extra transitions."""
    data = {
        "schema_version": "1.0.0",
        "domain": "Terminal",
        "class": "Widget",
        "initial_state": "Active",
        "events": [
            {"name": "Shutdown"},
            {"name": "Done"},
            {"name": "Bad"},
        ],
        "states": [
            {"name": "Active"},
            {"name": "Closing"},
        ],
        "transitions": [
            {"from": "Active", "to": "Closing", "event": "Shutdown"},
        ] + transitions_extra,
    }
    return StateDiagramFile(**data)


def _issues(sd: StateDiagramFile) -> list[dict]:
    """Run full validation and return all issues."""
    import importlib, sys
    # Patch the model root so validate_domain can find our in-memory object
    # instead, call the internal checkers directly
    from tools.validation import (
        _check_referential_integrity_state_diagram,
        _check_reachability,
    )
    return (
        _check_referential_integrity_state_diagram(sd, "Terminal")
        + _check_reachability(sd, "Terminal")
    )


# ---------------------------------------------------------------------------
# Validation: pseudostate routing guards
# ---------------------------------------------------------------------------

def test_from_terminal_is_validation_error():
    sd = _make_sd([{"from": "__terminal__", "to": "Active", "event": "Bad"}])
    issues = _issues(sd)
    assert any("__terminal__" in i["issue"] and "source" in i["issue"] for i in issues), \
        f"Expected '__terminal__ as source' error, got: {issues}"


def test_to_initial_is_validation_error():
    sd = _make_sd([{"from": "Closing", "to": "__initial__", "event": "Bad"}])
    issues = _issues(sd)
    assert any("__initial__" in i["issue"] for i in issues), \
        f"Expected '__initial__ as target' error, got: {issues}"


def test_to_terminal_is_not_a_validation_error():
    sd = _make_sd([{"from": "Closing", "to": "__terminal__", "event": "Done"}])
    issues = _issues(sd)
    ref_issues = [i for i in issues if "__terminal__" in i.get("issue", "") and "unknown" in i.get("issue", "")]
    assert not ref_issues, f"__terminal__ should be a valid transition target, got: {ref_issues}"
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\python.exe -m pytest tests/test_terminate_pseudostate.py -v
```

Expected: `test_from_terminal_is_validation_error` FAILS, `test_to_initial_is_validation_error` FAILS, `test_to_terminal_is_not_a_validation_error` FAILS.

- [ ] **Step 3: Update `_check_referential_integrity_state_diagram` in `tools/validation.py`**

Replace lines 434–449 (the transition loop body):

```python
# Transitions: to and event must exist
for i, t in enumerate(sd.transitions):
    if t.to not in state_names and t.to != "__terminal__":
        issues.append(_make_issue(
            issue=f"Transition from '{t.from_state}' has unknown target state '{t.to}'",
            location=f"{loc_sd}::transitions[{i}].to",
            value=t.to,
            fix=f"Add state '{t.to}' to states or fix the transition target",
        ))
    if t.from_state == "__terminal__":
        issues.append(_make_issue(
            issue=f"Transition uses '__terminal__' as a source state",
            location=f"{loc_sd}::transitions[{i}].from",
            value="__terminal__",
            fix="'__terminal__' is a sink pseudostate — it cannot have outgoing transitions",
        ))
    if t.to == "__initial__":
        issues.append(_make_issue(
            issue=f"Transition from '{t.from_state}' targets '__initial__'",
            location=f"{loc_sd}::transitions[{i}].to",
            value="__initial__",
            fix="'__initial__' is a source pseudostate — it cannot be the target of a transition",
        ))
    if t.event not in event_names:
        issues.append(_make_issue(
            issue=f"Transition from '{t.from_state}' references unknown event '{t.event}'",
            location=f"{loc_sd}::transitions[{i}].event",
            value=t.event,
            fix=f"Add event '{t.event}' to events or fix the transition event",
        ))
```

- [ ] **Step 4: Update `_check_reachability` in `tools/validation.py`**

Replace lines 465–507 (from `G = nx.DiGraph()` to end of function):

```python
G = nx.DiGraph()
G.add_nodes_from(state_names)
G.add_node("__terminal__")
for t in sd.transitions:
    # Only add edges for valid endpoints (referential integrity checked separately)
    src_valid = t.from_state in state_names
    tgt_valid = t.to in state_names or t.to == "__terminal__"
    if src_valid and tgt_valid:
        G.add_edge(t.from_state, t.to)

# Guard: initial_state must be in graph to run descendants()
if sd.initial_state not in G.nodes:
    return []  # Referential integrity already caught this

reachable = nx.descendants(G, sd.initial_state) | {sd.initial_state}
for state in state_names - reachable:
    issues.append(_make_issue(
        issue=f"State '{state}' is unreachable from initial state '{sd.initial_state}'",
        location=loc_sd,
        value=state,
        fix=f"Add a transition into '{state}' from a reachable state or remove it",
    ))

# Trap states: no outgoing edges (warning only)
for state in state_names:
    if G.out_degree(state) == 0:
        issues.append(_make_issue(
            issue=f"State '{state}' has no outgoing transitions",
            location=loc_sd,
            value=state,
            fix="Add outgoing transitions or add a transition 'to: __terminal__' if the state ends the object lifecycle",
            severity="warning",
        ))
```

- [ ] **Step 5: Run validation tests**

```
.venv\Scripts\python.exe -m pytest tests/test_terminate_pseudostate.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Run full test suite to check no regressions**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all previously-passing tests PASS.

- [ ] **Step 7: Commit**

```
git add tools/validation.py tests/test_terminate_pseudostate.py
git commit -m "feat: add __terminal__ pseudostate validation rules"
```

---

### Task 4: Create the test fixture YAML

**Files:**
- Create: `tests/fixtures/terminal-state-diagram.yaml`

**Interfaces:**
- Produces: a `StateDiagramFile`-parseable YAML with domain `Terminal`, class `Widget`, one `__terminal__` transition
- Consumed by: Task 5 and Task 6

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/terminal-state-diagram.yaml`:

```yaml
schema_version: "1.0.0"
domain: Terminal
class: Widget
initial_state: Active
events:
  - name: Shutdown
  - name: Done
states:
  - name: Active
  - name: Closing
    entry_action: "self.cleanup();"
transitions:
  - from: Active
    to: Closing
    event: Shutdown
  - from: Closing
    to: __terminal__
    event: Done
```

- [ ] **Step 2: Verify it parses correctly**

```
.venv\Scripts\python.exe -c "
import yaml
from pathlib import Path
from schema.yaml_schema import StateDiagramFile
sd = StateDiagramFile(**yaml.safe_load(Path('tests/fixtures/terminal-state-diagram.yaml').read_text()))
print('domain:', sd.domain)
print('states:', [s.name for s in sd.states])
print('transitions:', [(t.from_state, t.to, t.event) for t in sd.transitions])
"
```

Expected output:
```
domain: Terminal
states: ['Active', 'Closing']
transitions: [('Active', 'Closing', 'Shutdown'), ('Closing', '__terminal__', 'Done')]
```

- [ ] **Step 3: Commit**

```
git add tests/fixtures/terminal-state-diagram.yaml
git commit -m "test: add terminal-state-diagram fixture"
```

---

### Task 5: Implement terminate pseudostate rendering in `tools/drawio.py`

**Files:**
- Modify: `tools/drawio.py:30-48` (imports), `:1865-1968` (`_build_state_diagram_xml`), `:1174-1175` (`_drawio_to_canonical_state`)

**Interfaces:**
- Consumes: `STYLE_TERMINATE_PSEUDO` from Task 1; fixture from Task 4
- Produces: `_build_state_diagram_xml` emits a terminate pseudostate cell when any transition has `to == "__terminal__"`

- [ ] **Step 1: Add `STYLE_TERMINATE_PSEUDO` to imports**

In `tools/drawio.py` around line 30, the import from `schema.drawio_schema` currently reads:

```python
from schema.drawio_schema import (
    BIJECTION_TABLE,
    STYLE_ASSOC_LABEL,
    STYLE_ASSOCIATION,
    STYLE_ATTRIBUTE,
    STYLE_CLASS,
    STYLE_CLASS_ACTIVE,
    STYLE_GENERALIZATION,
    STYLE_INITIAL_PSEUDO,
    STYLE_SEPARATOR,
    STYLE_STATE,
    STYLE_TRANSITION,
    ...
)
```

Add `STYLE_TERMINATE_PSEUDO,` after `STYLE_STATE,`.

- [ ] **Step 2: Add terminal vertex detection and sizing in `_build_state_diagram_xml`**

After line 1865 (`n_vertices = 1 + len(state_names)`), insert:

```python
# Detect terminal pseudostate
has_terminal = any(t.to == "__terminal__" for t in sd.transitions)
```

After line 1884–1885 (node_widths/heights construction), insert:

```python
if has_terminal:
    terminal_vertex_idx = n_vertices
    n_vertices += 1
    state_name_to_idx["__terminal__"] = terminal_vertex_idx
    node_widths.append(INIT_SIZE)
    node_heights.append(INIT_SIZE)
```

The full block from `n_vertices` through the size lists should read:

```python
n_vertices = 1 + len(state_names)  # 0=initial_pseudo, 1..N=states

# Detect terminal pseudostate
has_terminal = any(t.to == "__terminal__" for t in sd.transitions)

# Build edges
state_name_to_idx = {name: 1 + i for i, name in enumerate(state_names)}
edges: list[tuple[int, int]] = []
# Initial -> initial_state edge
edges.append((0, initial_state_vertex_idx))
# Transition edges — track which transitions map to which edge index
trans_edge_idx: list[int | None] = []
for trans in sd.transitions:
    src = state_name_to_idx.get(trans.from_state)
    tgt = state_name_to_idx.get(trans.to)
    if src is not None and tgt is not None:
        trans_edge_idx.append(len(edges))
        edges.append((src, tgt))
    else:
        trans_edge_idx.append(None)

# Per-node dimensions: vertex 0 = initial pseudostate, vertices 1..N = states
node_widths:  list[int] = [INIT_SIZE] + [_state_width(st.name, st.entry_action) for st in sd.states]
node_heights: list[int] = [INIT_SIZE] + [_state_height(st.entry_action)          for st in sd.states]

if has_terminal:
    terminal_vertex_idx = n_vertices
    n_vertices += 1
    state_name_to_idx["__terminal__"] = terminal_vertex_idx
    node_widths.append(INIT_SIZE)
    node_heights.append(INIT_SIZE)
```

**Important:** `has_terminal` must be set *before* the `state_name_to_idx` / edge-building block so `state_name_to_idx["__terminal__"]` is populated when the edge loop runs and `tgt` is resolved.

The corrected ordering is:

```python
n_vertices = 1 + len(state_names)

has_terminal = any(t.to == "__terminal__" for t in sd.transitions)

# Per-node dimensions (built before we know n_vertices final value, extended below)
node_widths:  list[int] = [INIT_SIZE] + [_state_width(st.name, st.entry_action) for st in sd.states]
node_heights: list[int] = [INIT_SIZE] + [_state_height(st.entry_action)          for st in sd.states]

state_name_to_idx = {name: 1 + i for i, name in enumerate(state_names)}

if has_terminal:
    terminal_vertex_idx = n_vertices
    n_vertices += 1
    state_name_to_idx["__terminal__"] = terminal_vertex_idx
    node_widths.append(INIT_SIZE)
    node_heights.append(INIT_SIZE)

edges: list[tuple[int, int]] = []
edges.append((0, initial_state_vertex_idx))
trans_edge_idx: list[int | None] = []
for trans in sd.transitions:
    src = state_name_to_idx.get(trans.from_state)
    tgt = state_name_to_idx.get(trans.to)
    if src is not None and tgt is not None:
        trans_edge_idx.append(len(edges))
        edges.append((src, tgt))
    else:
        trans_edge_idx.append(None)
```

- [ ] **Step 3: Emit the terminate pseudostate cell**

After the state-nodes loop (after line 1968, which ends `)`), insert:

```python
    # Terminate pseudostate (if any transition targets __terminal__)
    if has_terminal:
        term_cid = f"{domain.lower()}:state:{class_name}:__terminal__"
        xt = int(positions[terminal_vertex_idx][0])
        yt = int(positions[terminal_vertex_idx][1])
        term_cell = etree.SubElement(
            root_el, "mxCell",
            id=term_cid, value="",
            style=STYLE_TERMINATE_PSEUDO, vertex="1", parent="1",
        )
        etree.SubElement(
            term_cell, "mxGeometry",
            x=str(xt), y=str(yt), width=str(INIT_SIZE), height=str(INIT_SIZE),
            attrib={"as": "geometry"},
        )
```

- [ ] **Step 4: Update `_drawio_to_canonical_state` to skip `__terminal__`**

At line 1174, the existing skip reads:

```python
        if state_name == "__initial__":
            continue
```

Change to:

```python
        if state_name in ("__initial__", "__terminal__"):
            continue
```

- [ ] **Step 5: Run the full test suite**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all existing tests PASS (no regressions). The new rendering tests in Task 6 will be written next.

- [ ] **Step 6: Commit**

```
git add tools/drawio.py
git commit -m "feat: render __terminal__ as terminate pseudostate in Draw.io"
```

---

### Task 6: Write rendering tests for the terminate pseudostate

**Files:**
- Modify: `tests/test_terminate_pseudostate.py` (extend file from Task 3)

**Interfaces:**
- Consumes: `STYLE_TERMINATE_PSEUDO`, `STYLE_STATE`, `INIT_SIZE` from `schema.drawio_schema` / `tools.drawio`; fixture from Task 4; `_build_state_diagram_xml` from Task 5

- [ ] **Step 1: Add rendering tests to `tests/test_terminate_pseudostate.py`**

Append to the existing file:

```python
# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------

from lxml import etree as lxml_etree
from schema.drawio_schema import STYLE_TERMINATE_PSEUDO, STYLE_STATE
from tools.drawio import INIT_SIZE, _build_state_diagram_xml

FIXTURE_YAML = Path(__file__).parent / "fixtures" / "terminal-state-diagram.yaml"
DOMAIN = "Terminal"
CLASS_NAME = "Widget"
TERM_CELL_ID = "terminal:state:Widget:__terminal__"


def _load_sd_fixture() -> StateDiagramFile:
    return StateDiagramFile(**yaml.safe_load(FIXTURE_YAML.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def terminal_diagram_xml() -> bytes:
    sd = _load_sd_fixture()
    return _build_state_diagram_xml(DOMAIN, sd)


def _cells_by_id(xml_bytes: bytes) -> dict:
    root = lxml_etree.fromstring(xml_bytes)
    return {el.get("id"): el for el in root.iter("mxCell") if el.get("id")}


def test_terminate_pseudostate_cell_present(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    assert TERM_CELL_ID in cells, f"Expected cell '{TERM_CELL_ID}' not found"


def test_terminate_pseudostate_uses_correct_style(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    cell = cells[TERM_CELL_ID]
    assert cell.get("style") == STYLE_TERMINATE_PSEUDO, (
        f"Expected STYLE_TERMINATE_PSEUDO, got: {cell.get('style')!r}"
    )


def test_terminate_pseudostate_is_20x20(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    geo = cells[TERM_CELL_ID].find("mxGeometry")
    assert geo is not None
    assert int(geo.get("width")) == INIT_SIZE, f"Expected width={INIT_SIZE}"
    assert int(geo.get("height")) == INIT_SIZE, f"Expected height={INIT_SIZE}"


def test_terminate_pseudostate_has_empty_value(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    assert cells[TERM_CELL_ID].get("value") == ""


def test_regular_states_still_use_state_style(terminal_diagram_xml):
    cells = _cells_by_id(terminal_diagram_xml)
    for state_name in ("Active", "Closing"):
        cid = f"{DOMAIN.lower()}:state:{CLASS_NAME}:{state_name}"
        cell = cells.get(cid)
        assert cell is not None, f"State cell '{cid}' missing"
        assert cell.get("style") == STYLE_STATE, (
            f"{state_name} should use STYLE_STATE, got {cell.get('style')!r}"
        )


def test_transition_to_terminal_targets_pseudostate_cell(terminal_diagram_xml):
    root = lxml_etree.fromstring(terminal_diagram_xml)
    # Find the Closing --Done--> __terminal__ transition edge
    done_edges = [
        el for el in root.iter("mxCell")
        if el.get("edge") == "1"
        and ":trans:Widget:Closing:Done:" in (el.get("id") or "")
    ]
    assert done_edges, "No edge found for Closing --Done--> __terminal__"
    for edge in done_edges:
        assert edge.get("target") == TERM_CELL_ID, (
            f"Edge target should be '{TERM_CELL_ID}', got {edge.get('target')!r}"
        )


def test_no_terminal_transitions_no_terminal_cell():
    data = {
        "schema_version": "1.0.0",
        "domain": "Terminal",
        "class": "Widget",
        "initial_state": "Active",
        "events": [{"name": "Shutdown"}],
        "states": [{"name": "Active"}, {"name": "Closing"}],
        "transitions": [{"from": "Active", "to": "Closing", "event": "Shutdown"}],
    }
    sd = StateDiagramFile(**data)
    xml = _build_state_diagram_xml("Terminal", sd)
    cells = _cells_by_id(xml)
    assert TERM_CELL_ID not in cells, "No __terminal__ cell expected when no transitions target it"
```

- [ ] **Step 2: Run all tests in the file**

```
.venv\Scripts\python.exe -m pytest tests/test_terminate_pseudostate.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 3: Run full test suite**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```
git add tests/test_terminate_pseudostate.py
git commit -m "test: terminate pseudostate rendering and validation tests"
```

---

### Task 7: Add "State Machine Pseudostates" section to `docs/design/SYNTAX.md`

**Files:**
- Modify: `docs/design/SYNTAX.md` — insert new section between `## 11. Reserved Words` and `## 12. Differences from Standard OAL` (currently around line 1024)

**Interfaces:**
- Consumes: nothing
- Produces: documentation of `__initial__` and `__terminal__` semantics

- [ ] **Step 1: Insert the new section**

In `docs/design/SYNTAX.md`, find the `---` separator between sections 11 and 12 (around line 1024) and insert the following block **before** `## 12. Differences from Standard OAL`:

```markdown
---

## 11.5. State Machine Pseudostates

State diagrams use two reserved pseudostate keywords. Neither is a real
state — they require no entry in the `states:` list.

### `__initial__`

The implicit source of the first transition. The `initial_state:` field in
the state-diagram YAML names the first real state; the Draw.io renderer
automatically emits the filled-circle initial pseudostate and routes a
transition from it to that state.

- Cannot be the **target** of any transition.
- Never appears in the `states:` list.

### `__terminal__`

A reserved transition destination that ends the object instance lifecycle.

```yaml
transitions:
  - from: Closing
    to: __terminal__
    event: Done
```

- **Effect:** The runtime immediately deletes the object instance. No
  action body executes on entry.
- **Entry action:** Not supported and not rendered. Any cleanup (attribute
  zeroing, relationship unlinking, cross-domain notifications) must be
  performed in a preceding normal state with an entry action.
- **Outgoing transitions:** None. `__terminal__` is a sink. A transition
  `from: __terminal__` is a validation error.
- **Incoming transitions:** Any number of transitions from any state may
  target `__terminal__`. All route to a single UML terminate pseudostate
  cell (circle with X) in the Draw.io diagram.
- Never appears in the `states:` list.
```

- [ ] **Step 2: Commit**

```
git add docs/design/SYNTAX.md
git commit -m "docs: add State Machine Pseudostates section to SYNTAX.md"
```

---

## Self-Review

### Spec Coverage

| Spec Section | Task |
|---|---|
| Remove `StateDef.terminal` | Task 2 |
| Add `STYLE_TERMINATE_PSEUDO` + bijection | Task 1 |
| Allow `to: __terminal__` in validation | Task 3 |
| Forbid `from: __terminal__` | Task 3 |
| Forbid `to: __initial__` | Task 3 |
| Remove `StateDef.terminal`-based reachability logic | Task 3 |
| Update trap-state fix message | Task 3 |
| Import `STYLE_TERMINATE_PSEUDO` in drawio.py | Task 5 |
| Add terminal vertex to layout graph | Task 5 |
| Emit terminate pseudostate cell | Task 5 |
| Skip `__terminal__` in canonical parser | Task 5 |
| Add fixture | Task 4 |
| 9 tests (7 rendering + 2 validation) | Tasks 3 + 6 |
| SYNTAX.md documentation | Task 7 |

All spec sections covered.

### Ordering Dependency Note

The critical ordering constraint in Task 5 Step 2: `has_terminal` detection and `state_name_to_idx["__terminal__"]` injection must happen **before** the edge-building loop, so transitions with `to == "__terminal__"` resolve `tgt` correctly and get added to `edges`. The plan shows the corrected ordering explicitly in Step 2.
