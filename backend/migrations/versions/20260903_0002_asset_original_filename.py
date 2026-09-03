"""Add sanitized original asset filename."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_0002"
down_revision: str | None = "20260903_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("original_filename", sa.String(255), nullable=True))
    op.execute("UPDATE assets SET original_filename = 'upload' WHERE original_filename IS NULL")
    op.alter_column("assets", "original_filename", nullable=False)
    op.add_column(
        "template_profiles",
        sa.Column("role_styles_json", postgresql.JSONB(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("template_profiles", "role_styles_json")
    op.drop_column("assets", "original_filename")
