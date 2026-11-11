import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.vehicle import utc_now

if TYPE_CHECKING:
    from app.models.heartbeat import DeviceHeartbeat
    from app.models.vehicle import Vehicle


class DeviceState(str, enum.Enum):
    PENDING = "PENDING"
    ONLINE = "ONLINE"
    WARNING = "WARNING"
    DELAYED = "DELAYED"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"
    RETIRED = "RETIRED"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    hardware_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    firmware_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    state: Mapped[DeviceState] = mapped_column(
        Enum(DeviceState), default=DeviceState.PENDING, nullable=False
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    vehicle: Mapped["Vehicle"] = relationship(back_populates="devices")  # noqa: F821
    heartbeats: Mapped[list["DeviceHeartbeat"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
