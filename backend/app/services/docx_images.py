"""Extract images embedded in table cells, keyed by (table, row, col) position."""
from __future__ import annotations

from typing import Any

from docx.oxml.ns import qn


def extract_cell_images(doc: Any) -> dict[tuple[int, int, int], bytes]:
    found: dict[tuple[int, int, int], bytes] = {}
    seen: set[str] = set()
    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                for blip in cell._tc.findall(".//" + qn("a:blip")):
                    rid = blip.get(qn("r:embed"))
                    if not rid or rid in seen:
                        continue
                    seen.add(rid)
                    part = doc.part.related_parts.get(rid)
                    if part is not None:
                        found[(ti, ri, ci)] = part.blob
    return found
