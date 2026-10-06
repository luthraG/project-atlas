"""create vehicles table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-20

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plate", sa.String(length=20), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=30), nullable=True),
        sa.Column("brand", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plate"),
    )
    op.create_index("ix_vehicles_category_id", "vehicles", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_vehicles_category_id", table_name="vehicles")
    op.drop_table("vehicles")
