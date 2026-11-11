import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, UTCDateTime
from app.models.common import utcnow
from app.models.device_status import DeviceStatus


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="offline")
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    device_status: Mapped["DeviceStatus | None"] = relationship(lazy="joined", uselist=False)
    devices: Mapped[list["Device"]] = relationship(  # noqa: F821
        lazy="selectin", back_populates="vehicle", passive_deletes=True
    )


class VehicleAssignment(Base):
    __tablename__ = "vehicle_assignments"
    __table_args__ = (UniqueConstraint("user_id", "vehicle_id", name="uq_assignment_user_vehicle"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
