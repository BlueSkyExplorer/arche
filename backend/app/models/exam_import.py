"""Durable exam-import workflow entity.

Holds the source reference, the parsed ``DocumentBlock[]`` evidence, the
*extracted* and *reviewed* ``ExamDocument`` (never overwritten in place), the
validation result, and the workflow status. JSON columns carry the documents;
``schema_version`` is the extractor's output schema version (from
``ExamDocument.meta``), kept so older rows can be re-migrated if the schema
evolves.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExamImportStatus(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    MATERIALIZING = "materializing"
    COMPLETED = "completed"
    FAILED = "failed"


# Legal state transitions (a dict maps current -> allowed next states).
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "uploaded": {"parsing", "failed"},
    "parsing": {"extracting", "failed"},
    "extracting": {"needs_review", "ready", "failed"},
    "needs_review": {"ready", "materializing", "failed"},
    "ready": {"materializing", "failed"},
    "materializing": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


def can_transition(current: str, next_state: str) -> bool:
    return next_state in ALLOWED_TRANSITIONS.get(current, set())


class ExamImport(TimestampMixin, Base):
    __tablename__ = "exam_imports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)

    source_filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(10))  # docx / pdf
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="uploaded")

    extractor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # parser metadata + source asset manifest (local_id -> storage_key/mime)
    parser_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    asset_manifest: Mapped[dict] = mapped_column(JSONB, default=dict)

    # DocumentBlock[] evidence (source page/bbox/text per block)
    blocks_json: Mapped[list] = mapped_column(JSONB, default=list)

    # extracted vs reviewed ExamDocument (JSON), kept separate
    extracted_document_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reviewed_document_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    validation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    needs_review: Mapped[bool] = mapped_column(default=True)
    fallback_occurred: Mapped[bool] = mapped_column(default=False)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_question_ids: Mapped[list] = mapped_column(JSONB, default=list)

    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
