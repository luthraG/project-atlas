"""add checkout fields to parking_sessions

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-05

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parking_sessions",
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "parking_sessions",
        sa.Column("amount_charged", sa.Integer(), nullable=True),
    )
    op.add_column(
        "parking_sessions",
        sa.Column("ticket_number", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parking_sessions", "ticket_number")
    op.drop_column("parking_sessions", "amount_charged")
    op.drop_column("parking_sessions", "exit_time")
