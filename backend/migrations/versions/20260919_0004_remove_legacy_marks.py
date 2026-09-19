"""Remove legacy question-level marks and paper-question marks override.

Leaf marks in the content tree (ticket 01/02) are now the single source of
scoring truth. Before dropping ``questions.marks``, lift it into the root
``marks`` leaf for standalone questions (no sub-questions, no existing leaf
marks) so they keep their total through the contract removal. Multipart
questions already carry per-part leaf marks in their sub-question attributes.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260919_0004"
down_revision: str | None = "20260918_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE questions SET content_json = "
        "content_json || jsonb_build_object('marks', marks::text) "
        "WHERE marks > 0 "
        "AND NOT (content_json ? 'marks') "
        "AND NOT EXISTS ("
        "    SELECT 1 FROM jsonb_array_elements(COALESCE(content_json->'content', '[]'::jsonb)) el "
        "    WHERE el->>'type' = 'subQuestion'"
        ")"
    )
    op.drop_column("questions", "marks")
    op.drop_column("paper_questions", "marks_override")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column("questions", sa.Column("marks", sa.Numeric(8, 2), nullable=True))
    op.add_column("paper_questions", sa.Column("marks_override", sa.Numeric(8, 2), nullable=True))