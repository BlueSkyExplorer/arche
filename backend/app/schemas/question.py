from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionContent(BaseModel):
    type: Literal["doc"] = "doc"
    content: list[dict[str, Any]] = Field(default_factory=list)


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    internal_title: str
    subject: str
    level: str
    tags_json: list[str]
    source_note: str | None
    content_json: dict[str, Any]
    marks: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
