"""Render and quality tests for the Elevator class diagram.

Generates three progressive outputs to tests/output/ for visual inspection:
  step1-boxes-grid.drawio       — boxes only, simple grid placement, no edges
  step2-boxes-sugiyama.drawio   — boxes only, Sugiyama layout, no edges
  step3-full.drawio             — Sugiyama layout + association edges (production output)
"""
import math
import os
import shutil
import yaml
from pathlib import Path

import pytest
from lxml import etree

from schema.yaml_schema import ClassDiagramFile
from tools.drawio import CLASS_W, _build_class_diagram_xml

FIXTURE_YAML = Path(__file__).parent / "fixtures" / "elevator-class-diagram.yaml"
OUTPUT_DIR = Path(__file__).parent / "output"
DOMAIN = "Elevator"


def _load_cd() -> ClassDiagramFile:
    return ClassDiagramFile(**yaml.safe_load(FIXTURE_YAML.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def all_variants() -> dict[str, bytes]:
    """Generate all diagram variants in memory; write only the production file to disk."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Remove stale step files from previous diagnostic sessions
    for stale in OUTPUT_DIR.glob("elevator-step*.drawio"):
        stale.unlink()

    cd = _load_cd()

    variants = {
        "step1-boxes-grid":         _build_class_diagram_xml(DOMAIN, cd, use_layout=False,                          include_edges=False),
        "step2-boxes-sugiyama":     _build_class_diagram_xml(DOMAIN, cd, use_layout=True, layout="sugiyama",        include_edges=False),
        "step3-full-sugiyama":      _build_class_diagram_xml(DOMAIN, cd, use_layout=True, layout="sugiyama",        include_edges=True),
        "step4-boxes-kamada-kawai": _build_class_diagram_xml(DOMAIN, cd, use_layout=True, layout="kamada_kawai",    include_edges=False),
        "step5-full-kamada-kawai":  _build_class_diagram_xml(DOMAIN, cd, use_layout=True, layout="kamada_kawai",    include_edges=True),
    }

    # Only write the production output for visual inspection
    (OUTPUT_DIR / "elevator-class-diagram.drawio").write_bytes(variants["step5-full-kamada-kawai"])

    return variants


def _cells_by_id(xml_bytes: bytes) -> dict:
    root = etree.fromstring(xml_bytes)
    return {el.get("id"): el for el in root.iter("mxCell") if ":" in (el.get("id") or "")}


# ---------------------------------------------------------------------------
# Structural completeness (tested against the full diagram)
# ---------------------------------------------------------------------------

def test_all_classes_present(all_variants):
    cd = _load_cd()
    class_names = {cls.name for cls in cd.classes}
    cells = _cells_by_id(all_variants["step3-full-sugiyama"])
    class_cells = {
        cid.split(":")[-1]
        for cid in cells
        if cid.count(":") == 2 and ":class:" in cid
    }
    missing = class_names - class_cells
    assert not missing, f"Classes missing from diagram: {missing}"


def test_all_associations_present(all_variants):
    cd = _load_cd()
    assoc_names = {a.name for a in cd.associations}
    cells = _cells_by_id(all_variants["step3-full-sugiyama"])
    # Regular association cells end at the R-name; generalization cells have an extra
    # ":<subtype>" suffix (e.g. "elevator:assoc:R5:ElevatorCall"). Accept both forms.
    assoc_cells = set()
    for cid in cells:
        if ":assoc:" not in cid or ":assoc_mult:" in cid:
            continue
        parts = cid.split(":assoc:")[-1].split(":")
        assoc_cells.add(parts[0])   # always the R-name
    missing = assoc_names - assoc_cells
    assert not missing, f"Associations missing from diagram: {missing}"


# ---------------------------------------------------------------------------
# Layout quality (checked on each variant independently)
# ---------------------------------------------------------------------------

def test_no_overlapping_classes(all_variants):
    """No two class boxes share the same (x, y) in any variant."""
    for name, xml_bytes in all_variants.items():
        cells = _cells_by_id(xml_bytes)
        positions = []
        for cid, el in cells.items():
            if ":class:" in cid and cid.count(":") == 2:
                geo = el.find("mxGeometry")
                if geo is not None:
                    positions.append((int(geo.get("x", 0)), int(geo.get("y", 0)), cid))
        coords = [(x, y) for x, y, _ in positions]
        assert len(coords) == len(set(coords)), (
            f"{name}: duplicate positions: "
            f"{[p for p in positions if coords.count((p[0], p[1])) > 1]}"
        )


def test_no_box_overlaps(all_variants):
    """No two class boxes overlap (with a minimum gap between edges)."""
    from tools.drawio import CLASS_W
    GAP = 20  # minimum required gap between any two box edges

    for name, xml_bytes in all_variants.items():
        cells = _cells_by_id(xml_bytes)
        boxes = []
        for cid, el in cells.items():
            if ":class:" in cid and cid.count(":") == 2:
                geo = el.find("mxGeometry")
                x = int(geo.get("x", 0))
                y = int(geo.get("y", 0))
                h = int(geo.get("height", 0))
                boxes.append((x, y, CLASS_W, h, cid))

        for i, (x1, y1, w1, h1, id1) in enumerate(boxes):
            for x2, y2, w2, h2, id2 in boxes[i + 1:]:
                # Separation along each axis (positive = gap, negative = overlap)
                h_sep = (x2 - (x1 + w1)) if x2 >= x1 else (x1 - (x2 + w2))
                v_sep = (y2 - (y1 + h1)) if y2 >= y1 else (y1 - (y2 + h2))
                # Boxes are non-overlapping if they are separated on at least one axis
                assert h_sep >= GAP or v_sep >= GAP, (
                    f"{name}: {id1} and {id2} overlap or are too close "
                    f"(h_sep={h_sep}px, v_sep={v_sep}px, need {GAP}px on at least one axis)"
                )


def test_anchor_order_matches_target_positions(all_variants):
    """Exit anchors along a side must be ordered to match target positions.

    For edges leaving a box on the bottom/top, the leftmost exit anchor should
    go to the leftmost target (and so on).  Mismatches cause unnecessary crossings
    like the R10/R11 and R4/R14 issues on Elevator.
    """
    import re
    port_re = re.compile(r'exit([XY])=([0-9.]+)')

    xml_bytes = all_variants["step5-full-kamada-kawai"]
    root = etree.fromstring(xml_bytes)

    # Build {cell_id: (cx, cy)} centre positions
    centres: dict[str, tuple[float, float]] = {}
    for el in root.iter("mxCell"):
        cid = el.get("id", "")
        if ":class:" in cid and cid.count(":") == 2:
            geo = el.find("mxGeometry")
            x = float(geo.get("x", 0))
            y = float(geo.get("y", 0))
            w = float(geo.get("width", 0))
            h = float(geo.get("height", 0))
            centres[cid] = (x + w / 2, y + h / 2)

    # Group edges by (source_id, exit_side)
    from collections import defaultdict
    side_edges: dict[tuple, list] = defaultdict(list)
    for el in root.iter("mxCell"):
        if el.get("edge") != "1":
            continue
        src = el.get("source")
        tgt = el.get("target")
        if not src or not tgt or src == tgt:
            continue
        if ":class:" not in src or ":class:" not in tgt:
            continue
        style = el.get("style", "")
        ports = {m.group(1): float(m.group(2)) for m in port_re.finditer(style)}
        if "X" not in ports or "Y" not in ports:
            continue
        ex, ey = ports["X"], ports["Y"]
        if ey == 1.0:
            side = "bottom"
        elif ey == 0.0:
            side = "top"
        elif ex == 0.0:
            side = "left"
        else:
            side = "right"
        side_edges[(src, side)].append((ex, ey, tgt, el.get("id")))

    for (src, side), group in side_edges.items():
        if len(group) < 2:
            continue
        # Spread dimension: x for top/bottom, y for left/right
        if side in ("top", "bottom"):
            anchor_pos = [ex for ex, ey, tgt, _ in group]
            target_pos = [centres[tgt][0] for ex, ey, tgt, _ in group]
        else:
            anchor_pos = [ey for ex, ey, tgt, _ in group]
            target_pos = [centres[tgt][1] for ex, ey, tgt, _ in group]

        # Anchor order should match target order (both ascending or both descending)
        anchor_rank = sorted(range(len(anchor_pos)), key=lambda i: anchor_pos[i])
        target_rank = sorted(range(len(target_pos)), key=lambda i: target_pos[i])
        assert anchor_rank == target_rank, (
            f"Anchor order on {src} {side} side does not match target positions.\n"
            f"  edges: {[(g[3], g[2]) for g in group]}\n"
            f"  anchor positions: {anchor_pos}\n"
            f"  target positions: {target_pos}"
        )


def test_classes_within_canvas(all_variants):
    """All class boxes stay within the declared canvas in every variant."""
    for name, xml_bytes in all_variants.items():
        root = etree.fromstring(xml_bytes)
        model = root.find(".//mxGraphModel")
        canvas_w = int(model.get("pageWidth", 9999))
        canvas_h = int(model.get("pageHeight", 9999))

        cells = _cells_by_id(xml_bytes)
        for cid, el in cells.items():
            if ":class:" in cid and cid.count(":") == 2:
                geo = el.find("mxGeometry")
                x = int(geo.get("x", 0))
                y = int(geo.get("y", 0))
                h = int(geo.get("height", 0))
                assert x + CLASS_W <= canvas_w, f"{name}: {cid} extends past right edge"
                assert y + h <= canvas_h, f"{name}: {cid} extends past bottom edge"


# ---------------------------------------------------------------------------
# Visual quality: UML compliance and style correctness
# ---------------------------------------------------------------------------

def test_generalization_edges_have_hollow_triangle(all_variants):
    """R5 and R6 generalization edges must use hollow-triangle (block, endFill=0) arrowhead."""
    xml_bytes = all_variants["step5-full-kamada-kawai"]
    root = etree.fromstring(xml_bytes)

    gen_edges = [
        el for el in root.iter("mxCell")
        if el.get("edge") == "1"
        and "endArrow=block" in (el.get("style") or "")
        and "endFill=0" in (el.get("style") or "")
    ]
    assert gen_edges, "No generalization edges with hollow-triangle arrowhead found"

    # Collect groups by target (supertype)
    from collections import defaultdict
    by_target: dict[str, list] = defaultdict(list)
    for el in gen_edges:
        by_target[el.get("target")].append(el)

    # Expect two supertype groups: Call (R5) and CallButton (R6)
    from schema.drawio_schema import class_id as _cid
    domain = DOMAIN
    assert _cid(domain, "Call") in by_target, "R5: no generalization edges targeting Call"
    assert _cid(domain, "CallButton") in by_target, "R6: no generalization edges targeting CallButton"

    # Each group must have ≥2 edges (one per subtype)
    assert len(by_target[_cid(domain, "Call")]) >= 2, "R5: expected ≥2 subtype edges"
    assert len(by_target[_cid(domain, "CallButton")]) >= 2, "R6: expected ≥2 subtype edges"

    # All edges within a group share the same entry port on the supertype
    for target_id, group in by_target.items():
        import re
        entry_re = re.compile(r'entryX=[0-9.]+;entryY=[0-9.]+')
        entry_ports = {entry_re.search(el.get("style", "")).group() for el in group if entry_re.search(el.get("style", ""))}
        assert len(entry_ports) == 1, (
            f"Generalization edges to {target_id} use inconsistent entry ports: {entry_ports}"
        )


def test_active_classes_have_distinct_fill_color(all_variants):
    """Active classes must use green fill (#d5e8d4), entity classes blue fill (#dae8fc)."""
    xml_bytes = all_variants["step5-full-kamada-kawai"]
    root = etree.fromstring(xml_bytes)

    for el in root.iter("mxCell"):
        cid = el.get("id", "")
        if ":class:" not in cid or cid.count(":") != 2:
            continue
        value = el.get("value", "")
        style = el.get("style", "")
        if "<<active>>" in value:
            assert "fillColor=#d5e8d4" in style, (
                f"Active class {cid} should have green fill (#d5e8d4), got style: {style}"
            )
        else:
            assert "fillColor=#dae8fc" in style, (
                f"Entity class {cid} should have blue fill (#dae8fc), got style: {style}"
            )


def test_assoc_labels_have_transparent_background(all_variants):
    """Association multiplicity label cells must have transparent fill (fillColor=none)."""
    xml_bytes = all_variants["step5-full-kamada-kawai"]
    root = etree.fromstring(xml_bytes)

    label_cells = [
        el for el in root.iter("mxCell")
        if ":assoc_mult:" in (el.get("id") or "")
    ]
    assert label_cells, "No assoc_mult label cells found"

    for el in label_cells:
        style = el.get("style", "")
        assert "fillColor=none" in style, (
            f"Label cell {el.get('id')} should have fillColor=none, got: {style}"
        )
