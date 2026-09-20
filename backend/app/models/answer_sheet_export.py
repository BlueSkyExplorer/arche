from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AnswerSheetExport(Base):
    __tablename__ = "answer_sheet_exports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    exam_import_id: Mapped[UUID] = mapped_column(ForeignKey("exam_imports.id"), index=True)
    template_profile_id: Mapped[UUID] = mapped_column(ForeignKey("template_profiles.id"))
    template_version: Mapped[int] = mapped_column(Integer)
    reviewed_answer_sheet_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    template_config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    purpose: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(10), default="docx")
    status: Mapped[str] = mapped_column(String(30))
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
