from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TemplateProfile(TimestampMixin, Base):
    __tablename__ = "template_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    school_name: Mapped[str] = mapped_column(String(255))
    logo_asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    page_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    typography_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    header_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    footer_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    numbering_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    section_style_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    question_style_config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    answer_sheet_layout_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    role_styles: Mapped[dict[str, Any]] = mapped_column("role_styles_json", JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
