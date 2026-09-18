"""Add question content snapshot to paper questions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260918_0003"
down_revision: str | None = "20260903_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_questions",
        sa.Column("content_snapshot_json", postgresql.JSONB(), nullable=True),
    )
    op.execute(
        "UPDATE paper_questions pq SET content_snapshot_json = q.content_json "
        "FROM questions q WHERE pq.question_id = q.id"
    )
    op.alter_column("paper_questions", "content_snapshot_json", nullable=False)


def downgrade() -> None:
    op.drop_column("paper_questions", "content_snapshot_json")
