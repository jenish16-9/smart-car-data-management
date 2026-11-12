"""additive compatibility with the shared database device schema

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11

This migration deliberately preserves database-component columns that are not
owned by this service. It also works after a clean 0004 migration by renaming
the three equivalent device columns to the shared schema's established names.
"""

import sqlalchemy as sa

from alembic import op
from app.db.postgres import UTCDateTime

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _columns() -> dict[str, dict]:
    return {column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("devices")}


def _foreign_keys() -> list[dict]:
    return sa.inspect(op.get_bind()).get_foreign_keys("devices")


def _indexes() -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("devices")}


def upgrade() -> None:
    columns = _columns()

    if "name" in columns and "device_name" not in columns:
        op.alter_column("devices", "name", new_column_name="device_name")
    if "state" in columns and "status" not in columns:
        op.alter_column("devices", "state", new_column_name="status")
    if "last_heartbeat_at" in columns and "last_seen_at" not in columns:
        op.alter_column("devices", "last_heartbeat_at", new_column_name="last_seen_at")

    columns = _columns()
    if "owner_id" not in columns:
        op.add_column("devices", sa.Column("owner_id", sa.Uuid(), nullable=True))
        op.execute(
            sa.text(
                "UPDATE devices AS d SET owner_id = v.owner_id "
                "FROM vehicles AS v WHERE d.vehicle_id = v.id AND d.owner_id IS NULL"
            )
        )
    if "retired_at" not in columns:
        op.add_column("devices", sa.Column("retired_at", UTCDateTime(), nullable=True))
    if "registered_at" not in columns:
        op.add_column("devices", sa.Column("registered_at", UTCDateTime(), nullable=True))
        op.execute(sa.text("UPDATE devices SET registered_at = created_at WHERE registered_at IS NULL"))
        op.alter_column("devices", "registered_at", nullable=False)

    columns = _columns()
    op.alter_column("devices", "device_name", type_=sa.String(100), existing_type=columns["device_name"]["type"])
    op.execute(sa.text("UPDATE devices SET device_name = hardware_id WHERE device_name IS NULL"))
    op.alter_column("devices", "device_name", nullable=False)
    op.alter_column("devices", "hardware_id", type_=sa.String(100), existing_type=columns["hardware_id"]["type"])
    op.alter_column(
        "devices", "firmware_version", type_=sa.String(50), existing_type=columns["firmware_version"]["type"]
    )
    op.execute(sa.text("UPDATE devices SET configuration = '{}'::json WHERE configuration IS NULL"))
    op.alter_column("devices", "configuration", nullable=False, server_default=sa.text("'{}'::json"))
    op.alter_column("devices", "vehicle_id", nullable=True)

    foreign_keys = _foreign_keys()
    vehicle_fk = next((fk for fk in foreign_keys if fk["constrained_columns"] == ["vehicle_id"]), None)
    if vehicle_fk and vehicle_fk.get("name"):
        op.drop_constraint(vehicle_fk["name"], "devices", type_="foreignkey")
    op.create_foreign_key(
        "fk_devices_vehicle_id_vehicles", "devices", "vehicles", ["vehicle_id"], ["id"], ondelete="SET NULL"
    )

    owner_fk = next((fk for fk in _foreign_keys() if fk["constrained_columns"] == ["owner_id"]), None)
    if owner_fk is None:
        op.create_foreign_key(
            "fk_devices_owner_id_users", "devices", "users", ["owner_id"], ["id"], ondelete="SET NULL"
        )
    if "ix_devices_owner_id" not in _indexes():
        op.create_index("ix_devices_owner_id", "devices", ["owner_id"])


def downgrade() -> None:
    # Forward-only compatibility: dropping shared or pre-existing columns would
    # risk data owned by the database component.
    pass
