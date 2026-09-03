"""Initial domain schema.

Revision ID: 20260903_0001
Revises:
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_user_id", sa.String(320), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.UniqueConstraint("owner_user_id", name="uq_workspaces_owner_user_id"),
    )
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_assets_workspace_id_workspaces"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.UniqueConstraint("storage_key", name="uq_assets_storage_key"),
    )
    op.create_index("ix_assets_workspace_id", "assets", ["workspace_id"])
    op.create_table(
        "template_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("school_name", sa.String(255), nullable=False),
        sa.Column("logo_asset_id", sa.Uuid(), nullable=True),
        sa.Column("page_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("typography_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("header_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("footer_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("numbering_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("section_style_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("question_style_config_json", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["logo_asset_id"],
            ["assets.id"],
            name="fk_template_profiles_logo_asset_id_assets",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_template_profiles_workspace_id_workspaces",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_template_profiles"),
    )
    op.create_index("ix_template_profiles_workspace_id", "template_profiles", ["workspace_id"])
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("internal_title", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("level", sa.String(100), nullable=False),
        sa.Column("tags_json", postgresql.JSONB(), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("content_json", postgresql.JSONB(), nullable=False),
        sa.Column("marks", sa.Numeric(8, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_questions_workspace_id_workspaces"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
    )
    op.create_index("ix_questions_workspace_id", "questions", ["workspace_id"])
    op.create_table(
        "papers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("template_profile_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("level", sa.String(100), nullable=False),
        sa.Column("paper_date", sa.Date(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("instructions_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["template_profile_id"],
            ["template_profiles.id"],
            name="fk_papers_template_profile_id_template_profiles",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_papers_workspace_id_workspaces"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_papers"),
    )
    op.create_index("ix_papers_workspace_id", "papers", ["workspace_id"])
    op.create_table(
        "paper_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("instructions_json", postgresql.JSONB(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["papers.id"],
            name="fk_paper_sections_paper_id_papers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_paper_sections_workspace_id_workspaces",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paper_sections"),
        sa.UniqueConstraint("paper_id", "position", name="uq_paper_sections_paper_position"),
    )
    op.create_index("ix_paper_sections_paper_id", "paper_sections", ["paper_id"])
    op.create_index("ix_paper_sections_workspace_id", "paper_sections", ["workspace_id"])
    op.create_table(
        "paper_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("paper_section_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("marks_override", sa.Numeric(8, 2), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_section_id"],
            ["paper_sections.id"],
            name="fk_paper_questions_paper_section_id_paper_sections",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="fk_paper_questions_question_id_questions",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_paper_questions_workspace_id_workspaces",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paper_questions"),
        sa.UniqueConstraint(
            "paper_section_id", "position", name="uq_paper_questions_section_position"
        ),
    )
    op.create_index("ix_paper_questions_paper_section_id", "paper_questions", ["paper_section_id"])
    op.create_index("ix_paper_questions_question_id", "paper_questions", ["question_id"])
    op.create_index("ix_paper_questions_workspace_id", "paper_questions", ["workspace_id"])
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("paper_id", sa.Uuid(), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], name="fk_exports_paper_id_papers"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_exports_workspace_id_workspaces"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exports"),
    )
    op.create_index("ix_exports_paper_id", "exports", ["paper_id"])
    op.create_index("ix_exports_workspace_id", "exports", ["workspace_id"])


def downgrade() -> None:
    for table in [
        "exports",
        "paper_questions",
        "paper_sections",
        "papers",
        "questions",
        "template_profiles",
        "assets",
        "workspaces",
    ]:
        op.drop_table(table)
