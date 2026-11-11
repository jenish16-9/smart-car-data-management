"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

import sqlalchemy as sa

from alembic import op
from app.db.postgres import UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_code", sa.String(40), nullable=False),
        sa.Column("vehicle_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_seen_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_vehicles_vehicle_code", "vehicles", ["vehicle_code"], unique=True)

    op.create_table(
        "vehicle_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "vehicle_id", name="uq_assignment_user_vehicle"),
    )
    op.create_index("ix_vehicle_assignments_user_id", "vehicle_assignments", ["user_id"])
    op.create_index("ix_vehicle_assignments_vehicle_id", "vehicle_assignments", ["vehicle_id"])

    op.create_table(
        "audio_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(80), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_at", UTCDateTime(), nullable=False),
        sa.Column("processing_status", sa.String(20), nullable=False),
    )
    op.create_index("ix_audio_records_vehicle_id", "audio_records", ["vehicle_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("audio_record_id", sa.Uuid(), sa.ForeignKey("audio_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("detected_at", UTCDateTime(), nullable=False),
        sa.Column("reviewed_at", UTCDateTime(), nullable=True),
        sa.Column("resolved_at", UTCDateTime(), nullable=True),
    )
    op.create_index("ix_alerts_vehicle_id", "alerts", ["vehicle_id"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_detected_at", "alerts", ["detected_at"])

    op.create_table(
        "alert_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alert_id", sa.Uuid(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ix_alert_actions_alert_id", "alert_actions", ["alert_id"])

    op.create_table(
        "device_status",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("microphone_status", sa.String(20), nullable=False),
        sa.Column("gps_status", sa.String(20), nullable=False),
        sa.Column("engine_status", sa.String(20), nullable=False),
        sa.Column("battery_level", sa.Integer(), nullable=True),
        sa.Column("last_sync_at", UTCDateTime(), nullable=True),
    )
    op.create_index("ix_device_status_vehicle_id", "device_status", ["vehicle_id"], unique=True)


def downgrade() -> None:
    for table in (
        "device_status",
        "alert_actions",
        "alerts",
        "audio_records",
        "vehicle_assignments",
        "vehicles",
        "user_sessions",
        "users",
    ):
        op.drop_table(table)
