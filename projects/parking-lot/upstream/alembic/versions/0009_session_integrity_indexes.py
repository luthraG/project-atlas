"""parking_sessions integrity + reporting indexes

- uq_open_session_per_vehicle: at most one OPEN session per vehicle
  (closes the concurrent check-in race).
- ix_sessions_open_entry: open-sessions listing ordered by entry_time.
- ix_sessions_status_exit: revenue reports (status + exit_time range).
- uq_sessions_ticket: ticket numbers are unique once assigned (NULL while
  open, hence partial).

Fails loudly if existing data violates the unique indexes (checked on the
live DB before shipping: no duplicates).

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPEN = sa.text("status = 'open'")
_HAS_TICKET = sa.text("ticket_number IS NOT NULL")


def upgrade() -> None:
    op.create_index(
        "uq_open_session_per_vehicle",
        "parking_sessions",
        ["vehicle_id"],
        unique=True,
        postgresql_where=_OPEN,
        sqlite_where=_OPEN,
    )
    op.create_index(
        "ix_sessions_open_entry",
        "parking_sessions",
        ["entry_time"],
        postgresql_where=_OPEN,
        sqlite_where=_OPEN,
    )
    op.create_index("ix_sessions_status_exit", "parking_sessions", ["status", "exit_time"])
    op.create_index(
        "uq_sessions_ticket",
        "parking_sessions",
        ["ticket_number"],
        unique=True,
        postgresql_where=_HAS_TICKET,
        sqlite_where=_HAS_TICKET,
    )


def downgrade() -> None:
    op.drop_index("uq_sessions_ticket", table_name="parking_sessions")
    op.drop_index("ix_sessions_status_exit", table_name="parking_sessions")
    op.drop_index("ix_sessions_open_entry", table_name="parking_sessions")
    op.drop_index("uq_open_session_per_vehicle", table_name="parking_sessions")
