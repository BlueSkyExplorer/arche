"""Strict canonical ProseMirror/TipTap content schema.

Run ``python -m app.schemas.content`` to print the matching JSON Schema.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class EmptyAttrs(StrictModel):
    pass


class LinkAttrs(StrictModel):
    href: str = Field(min_length=1)
    title: str | None = None
    target: Literal["_blank", "_self"] | None = None


class BoldMark(StrictModel):
    type: Literal["bold"]


class ItalicMark(StrictModel):
    type: Literal["italic"]


class UnderlineMark(StrictModel):
    type: Literal["underline"]


class SubscriptMark(StrictModel):
    type: Literal["subscript"]


class SuperscriptMark(StrictModel):
    type: Literal["superscript"]


class LinkMark(StrictModel):
    type: Literal["link"]
    attrs: LinkAttrs


Mark = Annotated[
    BoldMark | ItalicMark | UnderlineMark | SubscriptMark | SuperscriptMark | LinkMark,
    Field(discriminator="type"),
]


class TextNode(StrictModel):
    type: Literal["text"]
    text: str
    marks: list[Mark] = Field(default_factory=list)


class HardBreakNode(StrictModel):
    type: Literal["hardBreak"]


class ImageAttrs(StrictModel):
    asset_id: UUID
    alt: str = ""
    title: str | None = None


class ImageNode(StrictModel):
    type: Literal["image"]
    attrs: ImageAttrs


InlineNode = Annotated[TextNode | HardBreakNode | ImageNode, Field(discriminator="type")]


class ParagraphNode(StrictModel):
    type: Literal["paragraph"]
    content: list[InlineNode] = Field(default_factory=list)


class HeadingAttrs(StrictModel):
    level: Literal[1, 2, 3]


class HeadingNode(StrictModel):
    type: Literal["heading"]
    attrs: HeadingAttrs
    content: list[InlineNode] = Field(default_factory=list)


class AnswerSpaceAttrs(StrictModel):
    lines: int | None = Field(default=None, ge=0)
    blank_height_mm: float | None = Field(default=None, alias="blankHeightMm", ge=0)

    @model_validator(mode="after")
    def exactly_one_dimension(self) -> AnswerSpaceAttrs:
        if (self.lines is None) == (self.blank_height_mm is None):
            raise ValueError("answerSpace requires exactly one of lines or blankHeightMm")
        return self


class AnswerSpaceNode(StrictModel):
    type: Literal["answerSpace"]
    attrs: AnswerSpaceAttrs


class ListItemNode(StrictModel):
    type: Literal["listItem"]
    content: list[BlockNode] = Field(min_length=1)


class BulletListNode(StrictModel):
    type: Literal["bulletList"]
    content: list[ListItemNode] = Field(min_length=1)


class OrderedListAttrs(StrictModel):
    start: int = Field(default=1, ge=1)


class OrderedListNode(StrictModel):
    type: Literal["orderedList"]
    attrs: OrderedListAttrs = Field(default_factory=OrderedListAttrs)
    content: list[ListItemNode] = Field(min_length=1)


class TableCellNode(StrictModel):
    type: Literal["tableCell"]
    content: list[BlockNode] = Field(min_length=1)


class TableRowNode(StrictModel):
    type: Literal["tableRow"]
    content: list[TableCellNode] = Field(min_length=1)


class TableNode(StrictModel):
    type: Literal["table"]
    content: list[TableRowNode] = Field(min_length=1)

    @model_validator(mode="after")
    def rectangular(self) -> TableNode:
        widths = {len(row.content) for row in self.content}
        if len(widths) != 1:
            raise ValueError("table rows must contain the same number of cells")
        return self


class SubQuestionAttrs(StrictModel):
    label: str = Field(min_length=1)


class SubQuestionNode(StrictModel):
    type: Literal["subQuestion"]
    attrs: SubQuestionAttrs
    content: list[BlockNode] = Field(min_length=1)


BlockNode = Annotated[
    ParagraphNode
    | HeadingNode
    | BulletListNode
    | OrderedListNode
    | TableNode
    | ImageNode
    | SubQuestionNode
    | AnswerSpaceNode,
    Field(discriminator="type"),
]


class DocNode(StrictModel):
    type: Literal["doc"] = "doc"
    content: list[BlockNode] = Field(default_factory=list)


DocNode.model_rebuild()
CONTENT_ADAPTER = TypeAdapter(DocNode)


def parse_content(value: object) -> DocNode:
    """Validate untrusted JSON and return typed nodes or raise ValidationError."""
    return CONTENT_ADAPTER.validate_python(value)


def content_json_schema() -> dict[str, object]:
    """Return the canonical schema used by frontend/editor integrations."""
    return CONTENT_ADAPTER.json_schema(by_alias=True)


if __name__ == "__main__":
    print(json.dumps(content_json_schema(), indent=2, ensure_ascii=False))
