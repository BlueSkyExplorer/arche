"""Content-free, source-derived OOXML layout blueprints for answer sheets.

Blueprints deliberately contain only formatting elements.  Teacher answer text
never enters this structure; the reviewed AnsSheet remains the content source.
"""
# ruff: noqa: E501
from __future__ import annotations

import re
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W_NS}


def _xml(element: Any | None) -> str | None:
    return etree.tostring(element, encoding="unicode") if element is not None else None


def _ppr(paragraph: Any) -> str | None:
    return _xml(paragraph._p.pPr)


def _rpr(paragraph: Any) -> str | None:
    run = next(iter(paragraph.runs), None)
    return _xml(run._r.rPr) if run is not None else None


def _paragraph(
    paragraph: Any,
    *,
    marks_same_line: bool = False,
    answer_same_line: bool = False,
) -> dict[str, Any]:
    return {
        "pPr": _ppr(paragraph),
        "rPr": _rpr(paragraph),
        "marks_same_line": marks_same_line,
        "answer_same_line": answer_same_line,
    }


def _is_mcq(table: Any) -> bool:
    return bool(table.rows) and "題號" in "".join(c.text for c in table.rows[0].cells) and "答案" in "".join(c.text for c in table.rows[0].cells)


def _table(table: Any) -> dict[str, Any]:
    tbl = table._tbl
    rows: list[dict[str, Any]] = []
    for row in table.rows[:2]:
        rows.append({"trPr": _xml(row._tr.trPr), "cells": [{"tcPr": _xml(cell._tc.tcPr), "pPr": _ppr(cell.paragraphs[0]), "rPr": _rpr(cell.paragraphs[0])} for cell in row.cells]})
    return {"tblPr": _xml(tbl.tblPr), "tblGrid": _xml(tbl.tblGrid), "rows": rows}


_CHAIN_LABEL = re.compile(r"^\(?[A-Za-z0-9]{1,4}\)?$")


def _label_chain(paragraph: Any) -> dict[str, Any] | None:
    """A same-line label chain: ``sub\\tsubsub\\tanswer\\tmarks`` on one line.

    Returns a content-free chain descriptor when the paragraph's text matches
    the chain shape (>=2 tab-separated leading labels and >=1 more tab field);
    labels are kept so the renderer can reuse the shape, answer text is not.
    """
    text = paragraph.text or ""
    if text.count("\t") < 2:
        return None
    fields = text.split("\t")
    labels = [f.strip() for f in fields if f.strip()]
    if len(labels) < 3:
        return None
    label_fields = labels[:-2] if "分" in labels[-1] or "marks" in labels[-1].lower() else labels[:-1]
    if len(label_fields) < 2 or not all(_CHAIN_LABEL.match(f) for f in label_fields):
        return None
    depth = len(label_fields)
    chain: dict[str, Any] = {"depth": depth, "pPr": _ppr(paragraph), "rPr": _rpr(paragraph), "labels": label_fields}
    for idx, label in enumerate(label_fields):
        key = "sub" if idx == 0 else ("subsub" if idx == 1 else f"label{idx}")
        chain[key] = label
    return chain


def source_layout_blueprint(doc: Any) -> dict[str, Any]:
    """Extract stable semantic-role formatting without retaining source content."""
    roles: dict[str, dict[str, Any]] = {}
    metadata: list[dict[str, Any]] = []
    label_chains: list[dict[str, Any]] = []
    root = sub = subsub = answer = section = marks = image = None
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if not text:
            continue
        if section is None and ("甲部" in text or "乙部" in text or text.lower().startswith("section")):
            section = p
        if text.startswith("Q") and len(text) > 1 and text[1].isdigit() and root is None:
            root = p
        elif text.startswith("(") and ")" in text:
            if sub is None:
                sub = p
            elif subsub is None:
                subsub = p
        elif section is None:
            metadata.append(_paragraph(p))
        elif answer is None:
            answer = p
        if "\t" in p.text and ("分" in text or "marks" in text.lower()):
            marks = p
            chain = _label_chain(p)
            if chain is not None:
                label_chains.append(chain)
        if image is None and "graphic" in p._p.xml:
            image = p
    if metadata:
        roles["metadata"] = metadata[0]
    role_sources = (
        ("section_heading", section),
        ("root_question", root),
        ("sub_question", sub),
        ("sub_sub_question", subsub),
        ("answer_paragraph", answer),
        ("marks", marks or root or sub),
        ("image_paragraph", image or answer),
    )
    for name, paragraph in role_sources:
        if paragraph is not None:
            same_line = name in {"root_question", "sub_question", "sub_sub_question", "marks"}
            marks_same_line = same_line and "\t" in paragraph.text
            answer_same_line = marks_same_line and (
                "分" in paragraph.text or "marks" in paragraph.text.lower()
            )
            roles[name] = _paragraph(
                paragraph,
                marks_same_line=marks_same_line,
                answer_same_line=answer_same_line,
            )
    footer = (
        doc.sections[0].footer.paragraphs[0]
        if doc.sections and doc.sections[0].footer.paragraphs
        else None
    )
    header = (
        doc.sections[0].header.paragraphs[0]
        if doc.sections and doc.sections[0].header.paragraphs
        else None
    )
    if header is not None:
        roles["header"] = _paragraph(header)
    if footer is not None:
        roles["footer"] = _paragraph(footer)
    tables = list(doc.tables)
    mcq = next((t for t in tables if _is_mcq(t)), None)
    answer_table = next((t for t in tables if t is not mcq), None)
    parent_totals = {"0": bool(root and "分" in root.text), "1": bool(sub and "分" in sub.text), "2": bool(subsub and "分" in subsub.text)}
    return {"schema_version": 1, "section_sectPr": _xml(doc.sections[0]._sectPr) if doc.sections else None, "paragraph_roles": roles, "metadata_paragraphs": metadata, "label_chains": label_chains, "tables": {**({"mcq": _table(mcq)} if mcq else {}), **({"answer_table": _table(answer_table)} if answer_table else {})}, "parent_totals_by_depth": parent_totals}


def clone_xml(xml: str | None) -> Any | None:
    return etree.fromstring(xml.encode()) if xml else None


def apply_run_blueprint(run: Any, blueprint: dict[str, Any]) -> None:
    """Copy source run properties onto a newly injected semantic run."""
    rpr = clone_xml(blueprint.get("rPr"))
    if rpr is not None:
        old = run._r.rPr
        if old is not None:
            run._r.remove(old)
        run._r.insert(0, rpr)


def apply_paragraph_blueprint(paragraph: Any, blueprint: dict[str, Any]) -> None:
    """Replace pPr/rPr only; text/runs remain newly generated semantic content."""
    ppr = clone_xml(blueprint.get("pPr"))
    if ppr is not None:
        old = paragraph._p.pPr
        if old is not None:
            paragraph._p.remove(old)
        paragraph._p.insert(0, ppr)
    if paragraph.runs:
        apply_run_blueprint(paragraph.runs[0], blueprint)


def table_cell_blueprint(
    blueprint: dict[str, Any], row_index: int, column_index: int
) -> dict[str, Any] | None:
    """Return the nearest source cell primitive for a generated table cell."""
    rows = blueprint.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[min(row_index, len(rows) - 1)]
    if not isinstance(row, dict):
        return None
    cells = row.get("cells")
    if not isinstance(cells, list) or not cells:
        return None
    cell = cells[min(column_index, len(cells) - 1)]
    return cell if isinstance(cell, dict) else None


def apply_table_blueprint(table: Any, blueprint: dict[str, Any]) -> None:
    tbl = table._tbl
    for attr in ("tblPr", "tblGrid"):
        cloned = clone_xml(blueprint.get(attr))
        if cloned is not None:
            old = getattr(tbl, attr)
            if old is not None:
                tbl.remove(old)
            tbl.insert(0 if attr == "tblPr" else 1, cloned)
    for ri, row in enumerate(table.rows):
        source = (blueprint.get("rows") or [])[min(ri, len(blueprint.get("rows") or [1]) - 1)] if blueprint.get("rows") else None
        if not source:
            continue
        trpr = clone_xml(source.get("trPr"))
        if trpr is not None:
            old = row._tr.trPr
            if old is not None:
                row._tr.remove(old)
            row._tr.insert(0, trpr)
        for ci, cell in enumerate(row.cells):
            cells = source.get("cells", [])
            if not cells:
                continue
            cell_source = cells[min(ci, len(cells) - 1)]
            tcpr = clone_xml(cell_source.get("tcPr"))
            if tcpr is not None:
                old = cell._tc.tcPr
                if old is not None:
                    cell._tc.remove(old)
                cell._tc.insert(0, tcpr)
            if cell.paragraphs:
                apply_paragraph_blueprint(cell.paragraphs[0], cell_source)
