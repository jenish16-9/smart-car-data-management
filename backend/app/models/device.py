import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.postgres import Base, UTCDateTime
from app.models.common import utcnow

DEVICE_STATUSES = ("PENDING", "ACTIVE", "ONLINE", "WARNING", "DELAYED", "OFFLINE", "DISABLED", "RETIRED")
DEVICE_TYPES = ("microphone", "audio_sensor", "gps", "imu", "camera", "gateway", "other")


class Device(Base):
    """An IoT device installed in a vehicle. A vehicle has many devices.

    Device-level controls (monitoring mode, audio capture, recording) live here, not on the vehicle.
    Devices are never deleted in normal flows: they are retired (soft removal).
    """

    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_vehicle_status", "vehicle_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), index=True, nullable=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    hardware_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), default="other")
    manufacturer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    # Device-level controls and state
    monitoring_mode: Mapped[str] = mapped_column(String(20), default="continuous", server_default="continuous")
    audio_capture_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    recording: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    online_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 of the device key

    vehicle = relationship("Vehicle", back_populates="devices", lazy="joined")

    # Compatibility aliases used by the v1 vehicle-scoped device API and UI.
    name = synonym("device_name")
    state = synonym("status")
    last_heartbeat_at = synonym("last_seen_at")

    @property
    def online(self) -> bool:
        return self.is_active and self.status in ("ACTIVE", "ONLINE", "WARNING")


class DeviceHeartbeat(Base):
    """Append-only heartbeat history (one row per heartbeat received)."""

    __tablename__ = "device_heartbeats"
    __table_args__ = (Index("ix_heartbeats_device_received", "device_id", "received_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    heartbeat_status: Mapped[str] = mapped_column(String(20), default="ok", index=True)
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
