from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.device import DeviceState
from app.models.heartbeat import DeviceHealth


class DeviceCreate(BaseModel):
    hardware_id: str = Field(min_length=3, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("hardware_id")
    @classmethod
    def normalize_hardware_id(cls, value: str) -> str:
        return value.strip().upper()


class DeviceResponse(DeviceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vehicle_id: str
    state: DeviceState
    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    state: DeviceState | None = None

    @model_validator(mode="after")
    def validate_staff_state(self) -> "DeviceUpdate":
        if self.state not in {None, DeviceState.DISABLED, DeviceState.RETIRED}:
            raise ValueError("Staff may only set device state to DISABLED or RETIRED")
        return self


class DeviceConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    capture_enabled: bool = Field(default=True, alias="captureEnabled")
    monitoring_mode: Literal["event", "continuous", "paused"] = Field(
        default="event", alias="monitoringMode"
    )
    heartbeat_interval_seconds: int = Field(
        default=30, ge=5, le=3600, alias="heartbeatIntervalSeconds"
    )


class DeviceConfigurationUpdate(BaseModel):
    configuration: DeviceConfiguration


class HeartbeatCreate(BaseModel):
    reported_at: datetime | None = None
    health: DeviceHealth = DeviceHealth.HEALTHY
    metrics: dict[str, Any] = Field(default_factory=dict)


class HeartbeatRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    health: DeviceHealth
    reported_at: datetime | None
    received_at: datetime
    metrics: dict[str, Any]


class HeartbeatResponse(HeartbeatRecord):
    device_state: DeviceState
