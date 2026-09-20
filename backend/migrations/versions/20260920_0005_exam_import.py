"""Create the exam_imports workflow table (additive)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0005"
down_revision: str | None = "20260919_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exam_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(10), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(30), server_default="uploaded", nullable=False),
        sa.Column("extractor_name", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("schema_version", sa.String(20), nullable=True),
        sa.Column("parser_meta", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("asset_manifest", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("blocks_json", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("extracted_document_json", postgresql.JSONB(), nullable=True),
        sa.Column("reviewed_document_json", postgresql.JSONB(), nullable=True),
        sa.Column("validation_json", postgresql.JSONB(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "fallback_occurred", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_question_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_exam_imports"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_exam_imports_workspace_id_workspaces"
        ),
    )
    op.create_index("ix_exam_imports_workspace_id", "exam_imports", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_imports_workspace_id", table_name="exam_imports")
    op.drop_table("exam_imports")
