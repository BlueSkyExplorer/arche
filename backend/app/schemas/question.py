from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.content import DocNode

QuestionContent = DocNode


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
