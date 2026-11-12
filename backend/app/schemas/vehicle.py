from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.vehicle import Vehicle

VehicleStatus = Literal["connected", "disconnected", "maintenance"]


class DeviceStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    microphone_status: str
    monitoring_mode: str
    audio_capture_enabled: bool
    recording: bool
    gps_status: str
    engine_status: str
    battery_level: int | None
    online_since: datetime | None
    last_sync_at: datetime | None


MonitoringMode = Literal["continuous", "motion_triggered", "paused"]


class VehicleControlsUpdate(BaseModel):
    monitoring_mode: MonitoringMode | None = None
    audio_capture_enabled: bool | None = None
    recording: bool | None = None


class DeviceLogOut(BaseModel):
    vehicle_id: str
    event_type: str
    message: str
    timestamp: datetime


class VehicleCreate(BaseModel):
    vehicle_code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,38}$", examples=["CAR-1024"])
    vehicle_type: str = Field(min_length=1, max_length=40, examples=["Sedan"])
    vin: str | None = Field(default=None, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")
    license_plate: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Z0-9][A-Z0-9 -]*$")
    status: VehicleStatus = "disconnected"
    owner_id: UUID | None = None
    assigned_user_ids: list[UUID] = Field(default_factory=list, description="Admin only.")

    @field_validator("vin", "license_plate", mode="before")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return value.strip().upper() if isinstance(value, str) else value


class VehicleUpdate(BaseModel):
    vehicle_type: str | None = Field(default=None, min_length=1, max_length=40)
    vin: str | None = Field(default=None, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")
    license_plate: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Z0-9][A-Z0-9 -]*$")
    status: VehicleStatus | None = None
    owner_id: UUID | None = None

    @field_validator("vin", "license_plate", mode="before")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return value.strip().upper() if isinstance(value, str) else value


class VehicleOut(BaseModel):
    id: UUID
    vehicle_code: str
    vehicle_type: str
    vin: str | None
    license_plate: str | None
    status: str
    owner_id: UUID | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    device: DeviceStatusOut | None
    audio_device_state: str

    @classmethod
    def from_model(cls, vehicle: Vehicle) -> "VehicleOut":
        device = DeviceStatusOut.model_validate(vehicle.device_status) if vehicle.device_status else None
        return cls(
            id=vehicle.id,
            vehicle_code=vehicle.vehicle_code,
            vehicle_type=vehicle.vehicle_type,
            vin=vehicle.vin,
            license_plate=vehicle.license_plate,
            status=vehicle.status,
            owner_id=vehicle.owner_id,
            last_seen_at=vehicle.last_seen_at,
            created_at=vehicle.created_at,
            updated_at=vehicle.updated_at,
            device=device,
            audio_device_state=_audio_device_state(vehicle),
        )


def _audio_device_state(vehicle: Vehicle) -> str:
    states = {device.state for device in vehicle.devices if device.removed_at is None}
    priority = ("ONLINE", "WARNING", "DELAYED", "PENDING", "OFFLINE", "DISABLED", "RETIRED")
    return next(
        (state for state in priority if state in states),
        "OFFLINE",
    )
