from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PaperQuestion(Base):
    __tablename__ = "paper_questions"
    __table_args__ = (
        UniqueConstraint(
            "paper_section_id", "position", name="uq_paper_questions_section_position"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    paper_section_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_sections.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
