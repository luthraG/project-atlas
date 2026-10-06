"""create evidence_photos table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_photos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=False),
        sa.Column(
            "taken_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["parking_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_photos_session_id", "evidence_photos", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_photos_session_id", table_name="evidence_photos")
    op.drop_table("evidence_photos")
