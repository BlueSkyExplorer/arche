"""IR for AI structure suggestions + deterministic converters to canonical types."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.content import DocNode
from app.schemas.question import QuestionIngestDraft


class AISubPart(BaseModel):
    label: str = Field(min_length=1)  # "(a)", "(i)", "a)"
    text: str = ""
    marks: Decimal = Field(default=Decimal("0"), ge=0)
    children: list[AISubPart] = Field(default_factory=list)


class AIQuestion(BaseModel):
    label: str = Field(min_length=1)  # "Q1." / "1." / "第1題"
    marks: Decimal = Field(default=Decimal("0"), ge=0)
    stem: str = ""
    subparts: list[AISubPart] = Field(default_factory=list)


def _para(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _subpart_node(sp: AISubPart) -> dict:
    node: dict = {"type": "subQuestion", "attrs": {"label": sp.label}, "content": []}
    if sp.text:
        node["content"].append(_para(sp.text))
    node["content"].extend(_subpart_node(c) for c in sp.children)
    if not node["content"]:
        node["content"].append(_para(""))
    return node


def ai_questions_to_drafts(questions: list[AIQuestion]) -> list[QuestionIngestDraft]:
    drafts: list[QuestionIngestDraft] = []
    for q in questions:
        blocks: list[dict] = [_para(q.stem)] if q.stem else []
        blocks.extend(_subpart_node(sp) for sp in q.subparts)
        if not blocks:
            blocks = [_para("")]
        content = DocNode.model_validate({"type": "doc", "content": blocks})
        drafts.append(
            QuestionIngestDraft(internal_title=q.label, marks=q.marks, content_json=content)
        )
    return drafts
