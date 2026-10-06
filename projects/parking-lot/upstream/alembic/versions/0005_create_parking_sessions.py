"""create parking_sessions table

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-04

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parking_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column(
            "entry_time",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=10),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_parking_sessions_vehicle_id", "parking_sessions", ["vehicle_id"]
    )
    op.create_index(
        "ix_parking_sessions_operator_id", "parking_sessions", ["operator_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_parking_sessions_operator_id", table_name="parking_sessions")
    op.drop_index("ix_parking_sessions_vehicle_id", table_name="parking_sessions")
    op.drop_table("parking_sessions")
