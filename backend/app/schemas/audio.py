from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.audio import AudioRecord

ProcessingStatus = Literal["pending", "processing", "completed", "failed"]


class AudioCreate(BaseModel):
    vehicle_id: str = Field(description="Vehicle UUID or vehicle code, e.g. CAR-1024.")
    storage_url: str = Field(
        min_length=1,
        max_length=2048,
        pattern=r"^(https?|s3)://\S+$",
        description="URL of the file already uploaded to object storage (S3/MinIO).",
    )
    file_name: str = Field(min_length=1, max_length=255)
    file_type: str = Field(min_length=1, max_length=80, examples=["audio/wav"])
    duration_seconds: float | None = Field(default=None, ge=0)
    file_size: int | None = Field(default=None, ge=0)


class AudioStatusUpdate(BaseModel):
    processing_status: ProcessingStatus


class AnalysisOut(BaseModel):
    audio_record_id: str | None = None
    event_id: str | None = None
    vehicle_id: str
    model_name: str
    model_version: str
    predicted_class: str
    confidence: float
    processing_time_ms: int
    created_at: datetime

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> "AnalysisOut":
        return cls(**{k: v for k, v in doc.items() if k in cls.model_fields})


class AudioOut(BaseModel):
    id: UUID
    vehicle_id: UUID
    vehicle_code: str
    storage_url: str
    file_name: str
    file_type: str
    duration_seconds: float | None
    file_size: int | None
    uploaded_at: datetime
    processing_status: str
    analysis: AnalysisOut | None = None
    alert_id: UUID | None = None

    @classmethod
    def from_model(
        cls, audio: AudioRecord, analysis: AnalysisOut | None = None, alert_id: UUID | None = None
    ) -> "AudioOut":
        return cls(
            id=audio.id,
            vehicle_id=audio.vehicle_id,
            vehicle_code=audio.vehicle.vehicle_code,
            storage_url=audio.storage_url,
            file_name=audio.file_name,
            file_type=audio.file_type,
            duration_seconds=audio.duration_seconds,
            file_size=audio.file_size,
            uploaded_at=audio.uploaded_at,
            processing_status=audio.processing_status,
            analysis=analysis,
            alert_id=alert_id,
        )
