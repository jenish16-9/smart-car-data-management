from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeviceState = Literal[
    "PENDING",
    "ONLINE",
    "WARNING",
    "DELAYED",
    "OFFLINE",
    "DISABLED",
    "RETIRED",
]
DeviceHealth = Literal["HEALTHY", "WARNING"]


class DeviceConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    capture_enabled: bool = Field(default=True, alias="captureEnabled")
    monitoring_mode: Literal["event", "continuous", "paused"] = Field(default="event", alias="monitoringMode")
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=3600, alias="heartbeatIntervalSeconds")


class DeviceCreate(BaseModel):
    hardware_id: str = Field(min_length=3, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    configuration: DeviceConfiguration = Field(default_factory=DeviceConfiguration)

    @field_validator("hardware_id")
    @classmethod
    def normalize_hardware_id(cls, value: str) -> str:
        return value.strip().upper()


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    state: DeviceState | None = None

    @model_validator(mode="after")
    def validate_staff_state(self) -> "DeviceUpdate":
        if self.state not in {None, "DISABLED", "RETIRED"}:
            raise ValueError("Staff may only set device state to DISABLED or RETIRED")
        return self


class DeviceConfigurationUpdate(BaseModel):
    configuration: DeviceConfiguration


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    vehicle_id: UUID | None
    owner_id: UUID | None
    hardware_id: str
    name: str
    firmware_version: str | None
    state: DeviceState
    configuration: dict[str, Any]
    last_heartbeat_at: datetime | None
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HeartbeatCreate(BaseModel):
    reported_at: datetime | None = None
    health: DeviceHealth = "HEALTHY"
    metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reported_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("reported_at must include a timezone")
        return value


class HeartbeatRecord(BaseModel):
    heartbeat_id: UUID
    device_id: UUID
    vehicle_id: str | None
    health: DeviceHealth
    reported_at: datetime | None
    received_at: datetime
    metrics: dict[str, Any]


class HeartbeatResponse(HeartbeatRecord):
    device_state: DeviceState


class SimulatedAudioEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    vehicle_id: str = Field(alias="vehicleId")
    device_id: UUID = Field(alias="deviceId")
    event_type: str = Field(alias="eventType")
    confidence: float = Field(ge=0, le=1)
    severity: str | None = None
    timestamp: datetime
    location: str | None = None
    is_simulation: bool = Field(default=True, alias="isSimulation")
    model_version: str = Field(alias="modelVersion")
    processing_timestamp: datetime = Field(alias="processingTimestamp")
    alert_id: UUID | None = Field(default=None, alias="alertId")
