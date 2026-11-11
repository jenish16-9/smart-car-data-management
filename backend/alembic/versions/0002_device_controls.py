"""device controls: monitoring mode, audio capture, recording

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_status",
        sa.Column("monitoring_mode", sa.String(20), nullable=False, server_default="continuous"),
    )
    op.add_column(
        "device_status",
        sa.Column("audio_capture_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("device_status", sa.Column("recording", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("device_status", "recording")
    op.drop_column("device_status", "audio_capture_enabled")
    op.drop_column("device_status", "monitoring_mode")
