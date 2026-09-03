from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.content import DocNode

QuestionContent = DocNode


class QuestionCreate(BaseModel):
    internal_title: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=100)
    level: str = Field(min_length=1, max_length=100)
    tags_json: list[str] = Field(default_factory=list)
    source_note: str | None = None
    content_json: DocNode
    marks: Decimal = Field(ge=0)
    status: str = Field(default="draft", pattern="^(draft|ready|archived)$")


class QuestionPatch(BaseModel):
    internal_title: str | None = Field(default=None, min_length=1, max_length=255)
    subject: str | None = Field(default=None, min_length=1, max_length=100)
    level: str | None = Field(default=None, min_length=1, max_length=100)
    tags_json: list[str] | None = None
    source_note: str | None = None
    content_json: DocNode | None = None
    marks: Decimal | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, pattern="^(draft|ready|archived)$")


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    internal_title: str
    subject: str
    level: str
    tags_json: list[str]
    source_note: str | None
    content_json: DocNode
    marks: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
