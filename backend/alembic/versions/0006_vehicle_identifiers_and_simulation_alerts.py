"""vehicle identifiers and simulated-alert provenance

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    vehicle_columns = _columns("vehicles")
    if "vin" not in vehicle_columns:
        op.add_column("vehicles", sa.Column("vin", sa.String(17), nullable=True))
    if "license_plate" not in vehicle_columns:
        op.add_column("vehicles", sa.Column("license_plate", sa.String(20), nullable=True))
    vehicle_indexes = _indexes("vehicles")
    if "ix_vehicles_vin" not in vehicle_indexes:
        op.create_index("ix_vehicles_vin", "vehicles", ["vin"], unique=True)
    if "ix_vehicles_license_plate" not in vehicle_indexes:
        op.create_index("ix_vehicles_license_plate", "vehicles", ["license_plate"], unique=True)

    alert_columns = _columns("alerts")
    if "is_simulation" not in alert_columns:
        op.add_column("alerts", sa.Column("is_simulation", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "simulation_event_id" not in alert_columns:
        op.add_column("alerts", sa.Column("simulation_event_id", sa.String(36), nullable=True))
    if "ix_alerts_simulation_event_id" not in _indexes("alerts"):
        op.create_index("ix_alerts_simulation_event_id", "alerts", ["simulation_event_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_simulation_event_id", table_name="alerts")
    op.drop_column("alerts", "simulation_event_id")
    op.drop_column("alerts", "is_simulation")
    op.drop_index("ix_vehicles_license_plate", table_name="vehicles")
    op.drop_index("ix_vehicles_vin", table_name="vehicles")
    op.drop_column("vehicles", "license_plate")
    op.drop_column("vehicles", "vin")
