from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Question(TimestampMixin, Base):
    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    internal_title: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(100))
    level: Mapped[str] = mapped_column(String(100))
    tags_json: Mapped[list[str]] = mapped_column(JSONB)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
