from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrmReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AssetRead(OrmReadModel):
    id: UUID
    workspace_id: UUID
    kind: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    created_at: datetime


class PaperRead(OrmReadModel):
    id: UUID
    workspace_id: UUID
    template_profile_id: UUID
    title: str
    subject: str
    level: str
    paper_date: date | None
    duration_minutes: int | None
    instructions_json: list[dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime


class PaperSectionRead(OrmReadModel):
    id: UUID
    workspace_id: UUID
    paper_id: UUID
    title: str
    instructions_json: list[dict[str, Any]]
    position: int


class PaperQuestionRead(OrmReadModel):
    id: UUID
    workspace_id: UUID
    paper_section_id: UUID
    question_id: UUID
    position: int
    marks_override: Decimal | None
    settings_json: dict[str, Any]


class ExportRead(OrmReadModel):
    id: UUID
    workspace_id: UUID
    paper_id: UUID
    template_version: int
    format: str
    status: str
    storage_key: str | None
    error_message: str | None
    created_at: datetime
