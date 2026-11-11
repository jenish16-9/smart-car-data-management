import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base, UTCDateTime
from app.models.common import utcnow


class DeviceStatus(Base):
    """Latest device health snapshot; exactly one row per vehicle."""

    __tablename__ = "device_status"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), unique=True, index=True
    )
    microphone_status: Mapped[str] = mapped_column(String(20), default="offline")
    gps_status: Mapped[str] = mapped_column(String(20), default="no_signal")
    engine_status: Mapped[str] = mapped_column(String(20), default="unknown")
    monitoring_mode: Mapped[str] = mapped_column(String(20), default="continuous", server_default="continuous")
    audio_capture_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    recording: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    online_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, default=utcnow)
