"""vehicles.created_by audit column (operator that auto-registered it)

Nullable: pre-existing rows and admin-created vehicles have no value.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch mode keeps this runnable on SQLite (no ALTER ... ADD CONSTRAINT).
    with op.batch_alter_table("vehicles") as batch:
        batch.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_vehicles_created_by_users", "users", ["created_by"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("vehicles") as batch:
        batch.drop_constraint("fk_vehicles_created_by_users", type_="foreignkey")
        batch.drop_column("created_by")
