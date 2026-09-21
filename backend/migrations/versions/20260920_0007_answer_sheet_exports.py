"""Add answer-sheet layout config and immutable render/export audit records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0007"
down_revision: str | None = "20260920_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_LAYOUT = (
    "{\"metadata_lines\":[\"{{school_name}}\","
    "\"{{academic_year}} {{exam_name}}\","
    "\"{{level}} {{subject}} ({{document_type}})\"],"
    "\"mcq_columns\":2,\"mcq_borders\":true,"
    "\"mcq_question_width_mm\":14,\"mcq_answer_width_mm\":18,"
    "\"mcq_alignment\":\"center\",\"mcq_font_size_pt\":11,"
    "\"mcq_row_height_mm\":7,\"hierarchy_indent_mm\":7,"
    "\"show_parent_totals\":true,\"image_max_width_mm\":120,"
    "\"answer_table_borders\":true,\"answer_table_alignment\":\"left\","
    "\"answer_table_font_size_pt\":10,\"repeat_table_header\":true}"
)


def upgrade() -> None:
    op.add_column(
        "template_profiles",
        sa.Column(
            "answer_sheet_layout_json",
            postgresql.JSONB(),
            server_default=_DEFAULT_LAYOUT,
            nullable=False,
        ),
    )
    # NOT VALID safely aligns all new writes without making deployment depend
    # on historical rows that predate API validation.
    op.execute(
        "ALTER TABLE exam_imports ADD CONSTRAINT ck_exam_imports_import_type "
        "CHECK (import_type IN ('question_paper', 'answer_sheet')) NOT VALID"
    )
    op.create_table(
        "answer_sheet_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("exam_import_id", sa.Uuid(), nullable=False),
        sa.Column("template_profile_id", sa.Uuid(), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("reviewed_answer_sheet_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("template_config_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("metadata_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("format", sa.String(10), server_default="docx", nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("validation_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_answer_sheet_exports_workspace_id_workspaces",
        ),
        sa.ForeignKeyConstraint(
            ["exam_import_id"],
            ["exam_imports.id"],
            name="fk_answer_sheet_exports_exam_import_id_exam_imports",
        ),
        sa.ForeignKeyConstraint(
            ["template_profile_id"],
            ["template_profiles.id"],
            name="fk_answer_sheet_exports_template_profile_id_template_profiles",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_answer_sheet_exports"),
    )
    op.create_index(
        "ix_answer_sheet_exports_workspace_id", "answer_sheet_exports", ["workspace_id"]
    )
    op.create_index(
        "ix_answer_sheet_exports_exam_import_id", "answer_sheet_exports", ["exam_import_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_answer_sheet_exports_exam_import_id", table_name="answer_sheet_exports")
    op.drop_index("ix_answer_sheet_exports_workspace_id", table_name="answer_sheet_exports")
    op.drop_table("answer_sheet_exports")
    op.execute("ALTER TABLE exam_imports DROP CONSTRAINT ck_exam_imports_import_type")
    op.drop_column("template_profiles", "answer_sheet_layout_json")
