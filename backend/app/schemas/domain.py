from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.question import QuestionRead


class OrmReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AssetRead(OrmReadModel):
    id: UUID
    workspace_id: UUID
    kind: str
    storage_key: str
    original_filename: str
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
    settings_json: dict[str, Any]
    label: str | None = None
    question: QuestionRead | None = None


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


class PaperCreate(BaseModel):
    template_profile_id: UUID
    title: str
    subject: str
    level: str
    paper_date: date | None = None
    duration_minutes: int | None = None
    instructions_json: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "draft"


class PaperPatch(BaseModel):
    template_profile_id: UUID | None = None
    title: str | None = None
    subject: str | None = None
    level: str | None = None
    paper_date: date | None = None
    duration_minutes: int | None = None
    instructions_json: list[dict[str, Any]] | None = None
    status: str | None = None


class SectionCreate(BaseModel):
    title: str
    instructions_json: list[dict[str, Any]] = Field(default_factory=list)
    position: int = Field(ge=0)


class SectionPatch(BaseModel):
    title: str | None = None
    instructions_json: list[dict[str, Any]] | None = None
    position: int | None = Field(default=None, ge=0)


class PaperQuestionPut(BaseModel):
    question_id: UUID


class PaperSectionDetail(PaperSectionRead):
    questions: list[PaperQuestionRead]


class PaperDetail(PaperRead):
    sections: list[PaperSectionDetail]
    total_marks: Decimal
