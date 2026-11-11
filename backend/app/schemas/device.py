from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.device import DeviceState


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
