"""Persist immutable template source DOCX references and content-free OOXML blueprints."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0008"
down_revision: str | None = "20260920_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "template_profiles",
        sa.Column("source_docx_storage_key", sa.String(1024), nullable=True),
    )
    op.add_column(
        "template_profiles",
        sa.Column("source_docx_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "template_profiles",
        sa.Column(
            "ooxml_layout_blueprint_json",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("template_profiles", "ooxml_layout_blueprint_json")
    op.drop_column("template_profiles", "source_docx_sha256")
    op.drop_column("template_profiles", "source_docx_storage_key")
