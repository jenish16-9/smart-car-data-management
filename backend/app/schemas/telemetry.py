from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class TelemetryCreate(BaseModel):
    timestamp: datetime | None = Field(default=None, description="Defaults to server time (UTC).")
    location: Location | None = None
    speed: float | None = Field(default=None, ge=0, le=500, description="km/h")
    engine_temperature: float | None = Field(default=None, ge=-60, le=400, description="Celsius")
    battery_level: int | None = Field(default=None, ge=0, le=100)
    gps_status: str | None = Field(default=None, max_length=20)
    device_id: UUID | None = Field(default=None, description="Optional: the IoT device that produced this reading.")


class TelemetryOut(BaseModel):
    vehicle_id: str
    timestamp: datetime
    location: Location | None = None
    speed: float | None = None
    engine_temperature: float | None = None
    battery_level: int | None = None
    gps_status: str | None = None
    device_id: str | None = None
    hardware_id: str | None = None

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> "TelemetryOut":
        return cls(**{k: v for k, v in doc.items() if k in cls.model_fields})
