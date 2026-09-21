from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school_name: str = Field(min_length=1, max_length=255)
    academic_year: str = Field(min_length=1, max_length=100)
    exam_name: str = Field(min_length=1, max_length=255)
    level: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=100)
    document_type: str = Field(min_length=1, max_length=100)


class AnswerSheetRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_profile_id: UUID
    metadata: DocumentMetadata


class AnswerSheetExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    exam_import_id: UUID
    template_profile_id: UUID
    template_version: int
    reviewed_answer_sheet_snapshot: dict[str, Any]
    template_config_snapshot: dict[str, Any]
    metadata_snapshot: dict[str, Any]
    purpose: Literal["preview", "export"]
    format: Literal["docx"]
    status: Literal["succeeded", "blocked", "failed"]
    error_message: str | None
    validation_json: dict[str, Any]
    created_at: datetime


class AnswerSheetPreviewResponse(BaseModel):
    record: AnswerSheetExportRead
    preview: dict[str, Any]
