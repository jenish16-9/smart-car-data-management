from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.alert import Alert, AlertAction
from app.schemas.audio import AnalysisOut

EventType = Literal[
    "emergency_vehicle_siren",
    "glass_breaking",
    "screaming",
    "gunshot",
    "crash",
    "tire_skidding",
    "abnormal_engine_noise",
]
Severity = Literal["low", "medium", "high", "critical"]
AlertStatus = Literal["open", "acknowledged", "resolved"]


class AlertCreate(BaseModel):
    vehicle_id: str = Field(description="Vehicle UUID or vehicle code, e.g. CAR-1024.")
    audio_record_id: UUID | None = None
    event_type: EventType
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    location: str | None = Field(default=None, max_length=120)
    detected_at: datetime | None = None


class AlertActionRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class AlertActionOut(BaseModel):
    id: UUID
    user_id: UUID | None
    action_type: str
    notes: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, action: AlertAction) -> "AlertActionOut":
        return cls(
            id=action.id,
            user_id=action.user_id,
            action_type=action.action_type,
            notes=action.notes,
            created_at=action.created_at,
        )


class AlertOut(BaseModel):
    id: UUID
    vehicle_id: UUID
    vehicle_code: str
    audio_record_id: UUID | None
    event_type: str
    severity: str
    confidence: float
    status: str
    location: str | None
    is_simulation: bool
    simulation_event_id: str | None
    detected_at: datetime
    reviewed_at: datetime | None
    resolved_at: datetime | None

    @classmethod
    def from_model(cls, alert: Alert) -> "AlertOut":
        return cls(
            id=alert.id,
            vehicle_id=alert.vehicle_id,
            vehicle_code=alert.vehicle.vehicle_code,
            audio_record_id=alert.audio_record_id,
            event_type=alert.event_type,
            severity=alert.severity,
            confidence=alert.confidence,
            status=alert.status,
            location=alert.location,
            is_simulation=alert.is_simulation,
            simulation_event_id=alert.simulation_event_id,
            detected_at=alert.detected_at,
            reviewed_at=alert.reviewed_at,
            resolved_at=alert.resolved_at,
        )


class AlertDetail(AlertOut):
    actions: list[AlertActionOut] = Field(default_factory=list)
    analysis: AnalysisOut | None = None
