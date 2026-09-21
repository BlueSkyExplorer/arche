"""ExamImport API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.domain import OrmReadModel


class ExamImportSummary(OrmReadModel):
    id: UUID
    workspace_id: UUID
    source_filename: str
    source_type: str
    import_type: Literal["question_paper", "answer_sheet"]
    status: str
    extractor_name: str | None
    provider: str | None
    model: str | None
    fallback_occurred: bool
    needs_review: bool
    failure_message: str | None
    validation_json: dict[str, Any] | None
    warning_count: int = 0
    original_warning_count: int = 0
    current_warning_count: int = 0
    created_at: datetime
    updated_at: datetime


class ExamImportDetail(ExamImportSummary):
    model_config = ConfigDict(from_attributes=True)

    schema_version: str | None
    parser_meta: dict[str, Any]
    asset_manifest: dict[str, Any]
    blocks_json: list[dict[str, Any]]
    extracted_document_json: dict[str, Any] | None
    reviewed_document_json: dict[str, Any] | None
    answer_sheet_json: dict[str, Any] | None
    reviewed_answer_sheet_json: dict[str, Any] | None
    created_question_ids: list[str]
    reviewed_at: datetime | None
    completed_at: datetime | None
