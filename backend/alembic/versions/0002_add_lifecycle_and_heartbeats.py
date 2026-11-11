"""Add lifecycle timestamps and heartbeat history.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vehicles", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "devices", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "devices", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "device_heartbeats",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column(
            "health",
            sa.Enum("HEALTHY", "WARNING", name="devicehealth"),
            nullable=False,
        ),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_heartbeats_device_id",
        "device_heartbeats",
        ["device_id"],
    )
    op.create_index("ix_device_heartbeats_owner_id", "device_heartbeats", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_device_heartbeats_owner_id", table_name="device_heartbeats")
    op.drop_index("ix_device_heartbeats_device_id", table_name="device_heartbeats")
    op.drop_table("device_heartbeats")
    op.drop_column("devices", "removed_at")
    op.drop_column("devices", "retired_at")
    op.drop_column("vehicles", "removed_at")
