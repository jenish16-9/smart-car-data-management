import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.vehicle import utc_now

if TYPE_CHECKING:
    from app.models.device import Device


class DeviceHealth(str, enum.Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"


class DeviceHeartbeat(Base):
    __tablename__ = "device_heartbeats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    health: Mapped[DeviceHealth] = mapped_column(Enum(DeviceHealth), nullable=False)
    reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    device: Mapped["Device"] = relationship(back_populates="heartbeats")  # noqa: F821
