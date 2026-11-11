"""registered IoT devices and lifecycle state

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10
"""

import sqlalchemy as sa

from alembic import op
from app.db.postgres import UTCDateTime

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("hardware_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("last_heartbeat_at", UTCDateTime(), nullable=True),
        sa.Column("retired_at", UTCDateTime(), nullable=True),
        sa.Column("removed_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_devices_vehicle_id", "devices", ["vehicle_id"])
    op.create_index("ix_devices_owner_id", "devices", ["owner_id"])
    op.create_index("ix_devices_hardware_id", "devices", ["hardware_id"], unique=True)


def downgrade() -> None:
    op.drop_table("devices")
