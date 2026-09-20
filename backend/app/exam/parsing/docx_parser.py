"""DOCX → ``DocumentBlock[]`` parser.

Uses python-docx to walk the body in reading order (paragraphs and tables
interleaved), plus headers and footers. It performs layout detection only —
heading style, inline equation (OMML), inline image, caption, table — and never
interprets question structure or marks.

DOCX has no absolute page geometry without rendering, so every block's ``page``
and ``bbox`` are ``None`` (a documented "missing bbox" case); reading order is
preserved via the ``order`` index.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from docx import Document
from docx.oxml.ns import qn

from app.exam.ir import AssetReference
from app.exam.parsing.base import ParseError
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference

_HEADING_STYLE = re.compile(r"^Heading\s*(\d+)$", re.IGNORECASE)
_CAPTION_PREFIX = re.compile(
    r"^\s*(?:Figure|Fig\.|Table|Chart|圖|表|附圖)\b", re.IGNORECASE
)


def _paragraph_text(p_el: Any) -> str:
    return "".join(t.text or "" for t in p_el.iter(qn("w:t")))


def _paragraph_style_id(p_el: Any) -> str | None:
    p_pr = p_el.find(qn("w:pPr"))
    if p_pr is None:
        return None
    p_style = p_pr.find(qn("w:pStyle"))
    if p_style is None:
        return None
    val = p_style.get(qn("w:val"))
    return val if isinstance(val, str) else None


def _blips(element: Any) -> list[Any]:
    return list(element.findall(".//" + qn("a:blip")))


def _image_parts(element: Any, doc: Document) -> list[tuple[str, bytes, str]]:
    """Return (rid, blob, content_type) for each embedded image in ``element``."""
    found: list[tuple[str, bytes, str]] = []
    seen: set[str] = set()
    for blip in _blips(element):
        rid = blip.get(qn("r:embed"))
        if not rid or rid in seen:
            continue
        seen.add(rid)
        part = doc.part.related_parts.get(rid)
        if part is not None:
            found.append((str(rid), part.blob, str(part.content_type)))
    return found


def _table_rows(tbl_el: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in tbl_el.findall(qn("w:tr")):
        rows.append(
            [
                "".join(t.text or "" for t in tc.iter(qn("w:t")))
                for tc in tr.findall(qn("w:tc"))
            ]
        )
    return rows


class DocxParser:
    name = "docx"

    def supports(self, content_type: str | None, filename: str | None) -> bool:
        name = (filename or "").lower()
        return name.endswith(".docx") or content_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def parse(self, data: bytes, source_name: str | None = None) -> ParseResult:
        if not data or data[:4] != b"PK\x03\x04":
            raise ParseError("not a DOCX (missing ZIP magic)")
        try:
            doc = Document(BytesIO(data))
        except Exception as exc:  # noqa: BLE001 - malformed input surfaces as ParseError
            raise ParseError(f"malformed DOCX: {exc}") from exc

        blocks: list[DocumentBlock] = []
        assets: dict[str, bytes] = {}
        order = 0
        paragraph_index = 0
        table_index = 0
        image_index = 0

        def add_image(element: Any, doc_obj: Document) -> None:
            nonlocal order, image_index
            for rid, blob, content_type in _image_parts(element, doc_obj):
                local_id = f"img-{image_index}"
                image_index += 1
                assets[local_id] = blob
                blocks.append(
                    DocumentBlock(
                        id=f"b{order:04d}",
                        kind=BlockKind.IMAGE,
                        order=order,
                        source=SourceReference(
                            file_name=source_name, element_id=f"img-{rid}"
                        ),
                        asset=AssetReference(local_id=local_id, mime_type=content_type),
                    )
                )
                order += 1

        # Body in reading order (paragraphs and tables interleaved).
        for child in doc.element.body.iterchildren():
            if child.tag == qn("w:p"):
                paragraph_index += 1
                text = _paragraph_text(child)
                element_id = f"p{paragraph_index}"
                source = SourceReference(file_name=source_name, element_id=element_id)
                if child.find(qn("m:oMath")) is not None:
                    math_text = "".join(
                        t.text or "" for t in child.iter(qn("m:t"))
                    )
                    blocks.append(
                        DocumentBlock(
                            id=f"b{order:04d}",
                            kind=BlockKind.EQUATION,
                            text=math_text,
                            order=order,
                            source=source,
                            meta={"raw": "omml"},
                        )
                    )
                    order += 1
                    continue
                if _blips(child):
                    add_image(child, doc)
                    if text.strip():
                        blocks.append(
                            DocumentBlock(
                                id=f"b{order:04d}",
                                kind=BlockKind.TEXT,
                                text=text,
                                order=order,
                                source=source,
                            )
                        )
                        order += 1
                    continue
                style_id = _paragraph_style_id(child)
                heading = _HEADING_STYLE.match(style_id or "")
                if heading:
                    blocks.append(
                        DocumentBlock(
                            id=f"b{order:04d}",
                            kind=BlockKind.HEADING,
                            text=text,
                            order=order,
                            source=source,
                            meta={"level": int(heading.group(1))},
                        )
                    )
                    order += 1
                    continue
                if _CAPTION_PREFIX.match(text):
                    blocks.append(
                        DocumentBlock(
                            id=f"b{order:04d}",
                            kind=BlockKind.CAPTION,
                            text=text,
                            order=order,
                            source=source,
                        )
                    )
                    order += 1
                    continue
                if text.strip():
                    blocks.append(
                        DocumentBlock(
                            id=f"b{order:04d}",
                            kind=BlockKind.TEXT,
                            text=text,
                            order=order,
                            source=source,
                        )
                    )
                    order += 1
            elif child.tag == qn("w:tbl"):
                table_index += 1
                blocks.append(
                    DocumentBlock(
                        id=f"b{order:04d}",
                        kind=BlockKind.TABLE,
                        rows=_table_rows(child),
                        order=order,
                        source=SourceReference(
                            file_name=source_name, element_id=f"tbl{table_index}"
                        ),
                    )
                )
                order += 1
                add_image(child, doc)

        # Headers and footers as separate, order-continuing blocks.
        for section in doc.sections:
            header_index = 0
            for p in section.header.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                header_index += 1
                blocks.append(
                    DocumentBlock(
                        id=f"b{order:04d}",
                        kind=BlockKind.HEADER,
                        text=text,
                        order=order,
                        source=SourceReference(
                            file_name=source_name, element_id=f"hdr{header_index}"
                        ),
                    )
                )
                order += 1
            footer_index = 0
            for p in section.footer.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                footer_index += 1
                blocks.append(
                    DocumentBlock(
                        id=f"b{order:04d}",
                        kind=BlockKind.FOOTER,
                        text=text,
                        order=order,
                        source=SourceReference(
                            file_name=source_name, element_id=f"ftr{footer_index}"
                        ),
                    )
                )
                order += 1

        return ParseResult(
            blocks=blocks,
            assets=assets,
            page_count=None,
            source_name=source_name,
            format="docx",
            warnings=[],
            needs_review=False,
        )
