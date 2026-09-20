"""Add answer-sheet import columns to exam_imports (additive)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260920_0006"
down_revision: str | None = "20260920_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exam_imports",
        sa.Column(
            "import_type",
            sa.String(30),
            server_default="question_paper",
            nullable=False,
        ),
    )
    op.add_column(
        "exam_imports", sa.Column("answer_sheet_json", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "exam_imports",
        sa.Column("reviewed_answer_sheet_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exam_imports", "reviewed_answer_sheet_json")
    op.drop_column("exam_imports", "answer_sheet_json")
    op.drop_column("exam_imports", "import_type")
