import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, UTCDateTime
from app.models.common import utcnow


class Device(Base):
    """Registered IoT device. Heartbeat history is stored in MongoDB."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), index=True, nullable=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    hardware_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    # Attribute names follow this component's API; database column names retain
    # the shared database component's established schema.
    name: Mapped[str] = mapped_column("device_name", String(100))
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state: Mapped[str] = mapped_column("status", String(20), default="PENDING")
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column("last_seen_at", UTCDateTime, nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    vehicle = relationship("Vehicle", lazy="joined", back_populates="devices")
