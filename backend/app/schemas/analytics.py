from datetime import datetime

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_events: int
    critical_events: int
    average_confidence: int  # percent, 0-100
    resolution_rate: int  # percent, 0-100
    vehicle_count: int
    audio_upload_count: int
    detection_count: int
    active_alert_count: int


class EventsOverTimePoint(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    count: int


class EventsByTypeItem(BaseModel):
    event_type: str
    count: int
    average_confidence: int  # percent
    last_detected: datetime | None
