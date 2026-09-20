"""Provider-independent Exam Intermediate Representation (IR).

The IR is the single interchange contract between the document-parsing layer
(DocumentBlock[]), the semantic-extraction layer (rule-based or LLM), the
deterministic validation/reconciliation engine, and the materializer that
writes Arche's canonical content tree.

Design invariants (mirrors ADR-0002 / ADR-0003):

- **Semantic vs layout are separate.** A `QuestionNode` holds the *meaning*
  (label, marks, content); a `LayoutReference` on each `ContentBlock` and node
  holds the *source formatting* (font, size, bbox, page), so neither is lost and
  neither pollutes the other.
- **Leaf-only marks.** Only a leaf `QuestionNode` carries an authoritative
  `marks`; a node with `children` is always the computed sum of its descendants.
  The schema rejects a non-leaf node that also carries `marks`.
- **Arbitrary depth.** `QuestionNode.children` is recursive, so `3 -> b -> ii`
  is represented naturally without a fixed level count.
- **Declared values are evidence only.** `declared_marks` on a node, a section
  `declared_subtotal`, and the document `declared_total` are what the source
  *stated*; they never participate in computation.
- **Unknown marks are `None`, never `0`.** A leaf with no detected mark keeps
  `marks=None`; validation turns that into `needs_review`.
- **Everything carries source evidence.** Nodes and blocks reference
  `SourceEvidence` (page, block id, bbox, source text, confidence) so the review
  UI can trace any value back to its origin.

Nothing here imports an LLM vendor. Providers adapt *into* this contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictIRModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBox(StrictIRModel):
    """A bounding box in the source page, normalised to 0..1 fractions."""

    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self) -> BBox:
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("bbox must satisfy x1 >= x0 and y1 >= y0")
        return self


class SourceEvidence(StrictIRModel):
    """Where a value came from: page, block id, bbox, verbatim source text."""

    page: int | None = Field(default=None, ge=1)
    block_id: str | None = None
    bbox: BBox | None = None
    source_text: str = ""
    confidence: float = Field(default=1.0, ge=0, le=1)


class LayoutReference(StrictIRModel):
    """Source formatting of a block, kept separate from semantic content."""

    font: str | None = None
    size_pt: float | None = Field(default=None, gt=0)
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    alignment: Literal["left", "center", "right", "justify"] | None = None
    indent_mm: float | None = Field(default=None, ge=0)
    list_level: int | None = Field(default=None, ge=0)


class AssetReference(StrictIRModel):
    """A pointer to an extracted image/attachment, keyed by a stable local id.

    The materializer later persists each referenced asset and rewrites
    ``local_id`` to the persisted ``asset_id`` (ADR-0003 content-addressed).
    """

    local_id: str = Field(min_length=1)
    mime_type: str | None = None
    page: int | None = Field(default=None, ge=1)
    bbox: BBox | None = None
    source_text: str = ""


class ContentBlock(StrictIRModel):
    """One block of question content: text, an image, a table, an equation, etc."""

    kind: Literal["paragraph", "heading", "image", "table", "equation", "answer_space", "list"]
    text: str | None = None
    heading_level: int | None = Field(default=None, ge=1, le=6)
    asset: AssetReference | None = None
    rows: list[list[str]] | None = None  # rectangular table body
    source: SourceEvidence = Field(default_factory=SourceEvidence)
    layout: LayoutReference = Field(default_factory=LayoutReference)

    @model_validator(mode="after")
    def kind_specific_fields(self) -> ContentBlock:
        if self.kind == "image" and self.asset is None:
            raise ValueError("an image ContentBlock requires an asset reference")
        if self.kind == "table" and self.rows is None:
            raise ValueError("a table ContentBlock requires rows")
        if self.kind != "image" and self.asset is not None:
            raise ValueError("only image blocks carry an asset reference")
        return self


class DeclaredMarkEvidence(StrictIRModel):
    """A mark the source stated, with provenance (never scoring truth)."""

    value: Decimal = Field(ge=0)
    raw_text: str = ""
    source: SourceEvidence = Field(default_factory=SourceEvidence)


class QuestionNode(StrictIRModel):
    """A question or sub-question at arbitrary depth.

    Leaf nodes carry authoritative ``marks``; parents aggregate descendants.
    ``children`` is recursive — there is no fixed depth limit.
    """

    label: str | None = None
    marks: Decimal | None = Field(default=None, ge=0)
    declared_marks: list[DeclaredMarkEvidence] = Field(default_factory=list)
    content: list[ContentBlock] = Field(default_factory=list)
    children: list[QuestionNode] = Field(default_factory=list)
    source: SourceEvidence = Field(default_factory=SourceEvidence)
    confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def leaf_or_parent(self) -> QuestionNode:
        if self.marks is not None and self.children:
            raise ValueError(
                "a QuestionNode with children cannot carry an authoritative mark"
            )
        return self


class Section(StrictIRModel):
    """A section of the paper: an optional title, subtotal evidence, questions."""

    title: str | None = None
    declared_subtotal: Decimal | None = Field(default=None, ge=0)
    questions: list[QuestionNode] = Field(default_factory=list)
    source: SourceEvidence = Field(default_factory=SourceEvidence)


class ExamDocument(StrictIRModel):
    """The whole extracted paper: metadata, sections, and referenced assets."""

    school_name: str | None = None
    title: str | None = None
    subject: str | None = None
    level: str | None = None
    declared_total: Decimal | None = Field(default=None, ge=0)
    sections: list[Section] = Field(default_factory=list)
    assets: list[AssetReference] = Field(default_factory=list)
    source: SourceEvidence = Field(default_factory=SourceEvidence)
    # provider / parser metadata (e.g. which extractor, model, source file name)
    meta: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(StrictIRModel):
    """A deterministic discrepancy a human must review or acknowledge."""

    code: str = Field(min_length=1)
    severity: Literal["info", "warning", "blocking"] = "warning"
    message: str = ""
    location: str = ""
    source: SourceEvidence = Field(default_factory=SourceEvidence)


class ExtractionConfidence(StrictIRModel):
    """Aggregate confidence over the whole extraction."""

    overall: float = Field(default=1.0, ge=0, le=1)
    min_node: float = Field(default=1.0, ge=0, le=1)
    low_confidence_nodes: list[str] = Field(default_factory=list)


class ValidationReport(StrictIRModel):
    """Deterministic validation output: issues + review flag + computed total."""

    issues: list[ValidationIssue] = Field(default_factory=list)
    needs_review: bool = False
    computed_total: Decimal = Decimal("0")
    confidence: ExtractionConfidence = Field(default_factory=ExtractionConfidence)
