"""Create vehicles and devices.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("vin", sa.String(length=17), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("make", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=60), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("license_plate", sa.String(length=20), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "DEACTIVATED", name="vehiclestatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_owner_id", "vehicles", ["owner_id"])
    op.create_index("ix_vehicles_vin", "vehicles", ["vin"], unique=True)

    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("hardware_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("firmware_version", sa.String(length=50), nullable=True),
        sa.Column(
            "state",
            sa.Enum(
                "PENDING",
                "ONLINE",
                "WARNING",
                "DELAYED",
                "OFFLINE",
                "DISABLED",
                "RETIRED",
                name="devicestate",
            ),
            nullable=False,
        ),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_hardware_id", "devices", ["hardware_id"], unique=True)
    op.create_index("ix_devices_owner_id", "devices", ["owner_id"])
    op.create_index("ix_devices_vehicle_id", "devices", ["vehicle_id"])


def downgrade() -> None:
    op.drop_index("ix_devices_vehicle_id", table_name="devices")
    op.drop_index("ix_devices_owner_id", table_name="devices")
    op.drop_index("ix_devices_hardware_id", table_name="devices")
    op.drop_table("devices")
    op.drop_index("ix_vehicles_vin", table_name="vehicles")
    op.drop_index("ix_vehicles_owner_id", table_name="vehicles")
    op.drop_table("vehicles")
