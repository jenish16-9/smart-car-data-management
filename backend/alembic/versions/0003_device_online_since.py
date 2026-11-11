"""device_status.online_since (drives the uptime display)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10
"""

import sqlalchemy as sa

from alembic import op
from app.db.postgres import UTCDateTime

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device_status", sa.Column("online_since", UTCDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("device_status", "online_since")
