# Design: Virtual and Abstract Methods

**Date:** 2026-06-29
**Status:** Approved

## Summary

Add a `virtual: bool` flag to the `Method` YAML schema. A virtual method with no `action` body
is abstract; one with a body is virtual. Abstract methods render in italics with a `{abstract}`
prefix; virtual methods render in italics with a `{virtual}` prefix. A class with any abstract
methods gets `, abstract` appended to its stereotype label in the diagram.

---

## YAML Schema

Add `virtual: bool = False` to `Method` in `schema/yaml_schema.py`.

```yaml
methods:
  - name: Execute
    virtual: true          # no action → abstract
    return: Integer

  - name: Validate
    virtual: true          # has action → virtual (overridable with default body)
    return: Boolean
    action: |
      return true;

  - name: Init
    return: void           # virtual omitted → concrete (default)
    action: |
      self.count = 0;
```

Rules:
- `virtual: true` + no `action` → **abstract** method
- `virtual: true` + `action` present → **virtual** method
- `virtual: false` (default) → **concrete** method; `action` is independent of this flag

No new validation rules are introduced. Whether a concrete subclass implements an abstract
method is not enforced — this is annotation only.

---

## Label Rendering

Changes to `_method_label()` in `schema/canonical_builder.py`.

| Condition | Rendered label |
|---|---|
| `virtual=False` | `- name(params): ret` (unchanged) |
| `virtual=True`, no body | `- <i>{abstract} name(params): ret</i>` |
| `virtual=True`, has body | `- <i>{virtual} name(params): ret</i>` |
| Class-scope + virtual | `- <u><i>{abstract} name(params): ret</i></u>` |

The `<i>` tag renders as italic in Draw.io cells with `html=1` (which all method/attribute
cells already use via `STYLE_ATTRIBUTE`). Nesting `<u><i>...</i></u>` is valid HTML and
renders correctly.

The `_method_label()` signature gains two new parameters:

```python
def _method_label(
    vis: str,
    scope: str,
    name: str,
    params: list,
    return_type: str | None,
    virtual: bool = False,
    action: str | None = None,
) -> str:
```

The call site in `yaml_to_canonical_class()` passes `m.virtual` and `m.action`.

---

## Class Stereotype Derivation

In `yaml_to_canonical_class()` in `schema/canonical_builder.py`, the stereotype stored in
`CanonicalClassEntry` is derived as follows:

```python
is_abstract_class = any(m.virtual and m.action is None for m in cls.methods)
stereotype = f"{cls.stereotype}, abstract" if is_abstract_class else cls.stereotype
```

This means `CanonicalClassEntry.stereotype` will be `"entity, abstract"` or `"active, abstract"`
when appropriate. The Draw.io cell value becomes `<<entity, abstract>>\nClassName`.

---

## Draw.io Style Selection Fix

In `tools/drawio.py`, the active-class style check currently uses:

```python
cls_style = STYLE_CLASS_ACTIVE if cls.stereotype == "active" else STYLE_CLASS
```

This must be changed to handle the `, abstract` suffix:

```python
cls_style = STYLE_CLASS_ACTIVE if cls.stereotype.startswith("active") else STYLE_CLASS
```

---

## Canonical Round-Trip

`_drawio_to_canonical_class()` in `tools/drawio.py` reads the stereotype back via:

```python
m = re.match(r"<<(.+?)>>", value)
if m:
    stereotype = m.group(1)
```

This will correctly read `entity, abstract` from `<<entity, abstract>>\nClassName`. The YAML
side also produces `entity, abstract` in the canonical, so the comparison is valid and
diagrams regenerate correctly when abstract status changes.

---

## Scope of Changes

| File | Change |
|---|---|
| `schema/yaml_schema.py` | Add `virtual: bool = False` to `Method` |
| `schema/canonical_builder.py` | Update `_method_label()` for italic/tag rendering; derive `, abstract` stereotype |
| `tools/drawio.py` | Fix `startswith("active")` style check |
| `tests/` | Tests for virtual/abstract label output and class stereotype derivation |

No changes to `schema/drawio_canonical.py`, `schema/drawio_schema.py`, or YAML files in
`examples/`. The `CanonicalMethod` model (used for state diagram impl boxes) is unaffected —
abstract methods already have `action=None` and are skipped by the existing `if m.action is None: continue` guard.
