"""IoT devices, heartbeat history, vehicle soft delete, RESTRICT foreign keys

Additive and non-destructive: existing rows are kept. Every existing vehicle gets one backfilled
"legacy" device (hardware_id LEGACY-<vehicle_code>) carrying the controls from its device_status row.
vehicle_code / vehicle_type already exist on vehicles (0001), so nothing is added for them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op
from app.db.postgres import UTCDateTime

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_RESTRICTED = (("alerts", "vehicle_id"), ("audio_records", "vehicle_id"))
_STATUS_FOR_VEHICLE = {"connected": "ACTIVE", "maintenance": "WARNING", "disconnected": "DELAYED"}


def _swap_fk(table: str, column: str, ondelete: str) -> None:
    """Replace the vehicles FK on `table` with one using `ondelete` (PostgreSQL only)."""
    for fk in sa.inspect(op.get_bind()).get_foreign_keys(table):
        if fk["constrained_columns"] == [column] and fk["referred_table"] == "vehicles":
            op.drop_constraint(fk["name"], table, type_="foreignkey")
    op.create_foreign_key(f"{table}_{column}_fkey", table, "vehicles", [column], ["id"], ondelete=ondelete)


def upgrade() -> None:
    op.add_column("vehicles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("vehicles", sa.Column("deleted_at", UTCDateTime(), nullable=True))
    op.create_index("ix_vehicles_is_active", "vehicles", ["is_active"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hardware_id", sa.String(64), nullable=False),
        sa.Column("device_name", sa.String(80), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=False, server_default="other"),
        sa.Column("manufacturer", sa.String(80), nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("firmware_version", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", UTCDateTime(), nullable=True),
        sa.Column("registered_at", UTCDateTime(), nullable=False),
        sa.Column("removed_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("monitoring_mode", sa.String(20), nullable=False, server_default="continuous"),
        sa.Column("audio_capture_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("recording", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("online_since", UTCDateTime(), nullable=True),
        sa.Column("battery_level", sa.Integer(), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("api_key_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_devices_vehicle_id", "devices", ["vehicle_id"])
    op.create_index("ix_devices_hardware_id", "devices", ["hardware_id"], unique=True)
    op.create_index("ix_devices_status", "devices", ["status"])
    op.create_index("ix_devices_last_seen_at", "devices", ["last_seen_at"])
    op.create_index("ix_devices_vehicle_status", "devices", ["vehicle_id", "status"])

    op.create_table(
        "device_heartbeats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("received_at", UTCDateTime(), nullable=False),
        sa.Column("heartbeat_status", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("battery_level", sa.Integer(), nullable=True),
        sa.Column("signal_strength", sa.Float(), nullable=True),
        sa.Column("firmware_version", sa.String(40), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_device_heartbeats_device_id", "device_heartbeats", ["device_id"])
    op.create_index("ix_device_heartbeats_received_at", "device_heartbeats", ["received_at"])
    op.create_index("ix_device_heartbeats_heartbeat_status", "device_heartbeats", ["heartbeat_status"])
    op.create_index("ix_heartbeats_device_received", "device_heartbeats", ["device_id", "received_at"])

    _backfill_legacy_devices()

    if op.get_bind().dialect.name == "postgresql":
        for table, column in _RESTRICTED:
            _swap_fk(table, column, "RESTRICT")


def _backfill_legacy_devices() -> None:
    """One device per existing vehicle, carrying its current controls. Idempotent; deletes nothing."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT v.id, v.vehicle_code, v.status, v.last_seen_at, v.created_at, s.monitoring_mode, "
            "s.audio_capture_enabled, s.recording, s.online_since, s.battery_level "
            "FROM vehicles v LEFT JOIN device_status s ON s.vehicle_id = v.id"
        )
    ).mappings()
    now = datetime.now(UTC)
    devices = sa.table(
        "devices",
        *(
            sa.column(name)
            for name in (
                "id vehicle_id hardware_id device_name device_type status is_active last_seen_at registered_at "
                "created_at updated_at monitoring_mode audio_capture_enabled recording online_since battery_level"
            ).split()
        ),
    )
    for row in rows:
        exists = bind.execute(
            sa.text("SELECT 1 FROM devices WHERE hardware_id = :h"), {"h": f"LEGACY-{row['vehicle_code']}"}
        ).first()
        if exists:
            continue
        bind.execute(
            devices.insert().values(
                id=uuid.uuid4(),
                vehicle_id=row["id"],
                hardware_id=f"LEGACY-{row['vehicle_code']}"[:64],
                device_name="Primary audio unit",
                device_type="microphone",
                status=_STATUS_FOR_VEHICLE.get(row["status"], "PENDING"),
                is_active=True,
                last_seen_at=row["last_seen_at"],
                registered_at=row["created_at"] or now,
                created_at=now,
                updated_at=now,
                monitoring_mode=row["monitoring_mode"] or "continuous",
                audio_capture_enabled=True if row["audio_capture_enabled"] is None else row["audio_capture_enabled"],
                recording=bool(row["recording"]),
                online_since=row["online_since"],
                battery_level=row["battery_level"],
            )
        )


def downgrade() -> None:
    """Drops the new tables/columns (the data in them is lost); restores CASCADE foreign keys."""
    if op.get_bind().dialect.name == "postgresql":
        for table, column in _RESTRICTED:
            _swap_fk(table, column, "CASCADE")
    op.drop_table("device_heartbeats")
    op.drop_table("devices")
    op.drop_index("ix_vehicles_is_active", table_name="vehicles")
    op.drop_column("vehicles", "deleted_at")
    op.drop_column("vehicles", "is_active")
