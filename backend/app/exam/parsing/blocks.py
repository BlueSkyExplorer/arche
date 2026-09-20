"""Document Parsing contract: the provider-independent ``DocumentBlock``.

This layer only describes *what is in a document, where it is, and in what
order*. It deliberately performs no semantic interpretation: it never decides
that a block is "question 3(b)(ii)", never builds a sub-question tree, and never
interprets marks. That is the job of the semantic extractors (ticket 03/04),
which consume ``ParseResult``.

``DocumentBlock`` reuses ``BBox`` and ``AssetReference`` from the Exam IR so a
single geometry / asset-pointer vocabulary spans the whole pipeline.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from app.exam.ir import AssetReference, BBox, StrictIRModel


class BlockKind(StrEnum):
    TEXT = "text"
    HEADING = "heading"
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    CAPTION = "caption"
    HEADER = "header"
    FOOTER = "footer"


class SourceReference(StrictIRModel):
    """A stable pointer back into the source document."""

    file_name: str | None = None
    element_id: str | None = None
    page: int | None = Field(default=None, ge=1)


class DocumentBlock(StrictIRModel):
    """One content block in the source document, in reading order."""

    id: str = Field(min_length=1)  # stable, unique within a ParseResult
    page: int | None = Field(default=None, ge=1)
    kind: BlockKind
    text: str | None = None
    rows: list[list[str]] | None = None  # present for table blocks
    order: int = Field(ge=0)  # reading-order index across the whole document
    bbox: BBox | None = None  # absent when the parser cannot resolve geometry
    source: SourceReference = Field(default_factory=SourceReference)
    asset: AssetReference | None = None  # present for image blocks
    confidence: float | None = Field(default=None, ge=0, le=1)
    # parser-specific formatting/layout hints (font, bold, list level, …)
    meta: dict[str, Any] = Field(default_factory=dict)


class ParseResult(StrictIRModel):
    """Output of a ``DocumentParser``: ordered blocks + referenced raw assets."""

    blocks: list[DocumentBlock] = Field(default_factory=list)
    # local_id -> raw image bytes, to be persisted by the materializer (ticket 05)
    assets: dict[str, bytes] = Field(default_factory=dict)
    page_count: int | None = None
    source_name: str | None = None
    format: str | None = None
    warnings: list[str] = Field(default_factory=list)
    # true when the parse is lossy / uncertain (e.g. scanned PDF, OCR, .doc conv)
    needs_review: bool = False
