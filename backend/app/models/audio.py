import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base, UTCDateTime
from app.models.common import utcnow
from app.models.vehicle import Vehicle


class AudioRecord(Base):
    """Metadata only. The audio file itself lives in object storage (S3/MinIO)."""

    __tablename__ = "audio_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    storage_url: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(80))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")

    vehicle: Mapped[Vehicle] = relationship(lazy="joined", innerjoin=True)
