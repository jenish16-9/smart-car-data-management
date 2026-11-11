from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device import Device, DeviceHeartbeat

DeviceStatusValue = Literal["PENDING", "ACTIVE", "WARNING", "DELAYED", "DISABLED", "RETIRED"]
DeviceType = Literal["microphone", "audio_sensor", "gps", "imu", "camera", "gateway", "other"]
HeartbeatStatus = Literal["ok", "warning", "error"]
MonitoringMode = Literal["continuous", "motion_triggered", "paused"]

HARDWARE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9:_.-]{3,62}$"


class DeviceCreate(BaseModel):
    vehicle_id: str = Field(description="Vehicle UUID or vehicle_code (e.g. CAR-1024).")
    hardware_id: str = Field(pattern=HARDWARE_ID_PATTERN, examples=["MIC-A1B2C3D4"])
    device_type: DeviceType
    device_name: str | None = Field(default=None, max_length=80)
    manufacturer: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    firmware_version: str | None = Field(default=None, max_length=40)


class DeviceUpdate(BaseModel):
    device_name: str | None = Field(default=None, max_length=80)
    device_type: DeviceType | None = None
    manufacturer: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    firmware_version: str | None = Field(default=None, max_length=40)
    status: DeviceStatusValue | None = None
    configuration: dict[str, Any] | None = None


class DeviceControlsUpdate(BaseModel):
    monitoring_mode: MonitoringMode | None = None
    audio_capture_enabled: bool | None = None
    recording: bool | None = None


class HeartbeatCreate(BaseModel):
    hardware_id: str = Field(pattern=HARDWARE_ID_PATTERN, description="Must match the device's registered hardware ID.")
    heartbeat_status: HeartbeatStatus = "ok"
    battery_level: int | None = Field(default=None, ge=0, le=100)
    signal_strength: float | None = Field(default=None, ge=-150, le=100, description="dBm or percent")
    firmware_version: str | None = Field(default=None, max_length=40)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    metadata: dict[str, Any] | None = None


class HeartbeatOut(BaseModel):
    id: UUID
    device_id: UUID
    received_at: datetime
    heartbeat_status: str
    battery_level: int | None
    signal_strength: float | None
    firmware_version: str | None
    latitude: float | None
    longitude: float | None
    metadata: dict[str, Any] | None

    @classmethod
    def from_model(cls, beat: DeviceHeartbeat) -> "HeartbeatOut":
        return cls(
            id=beat.id,
            device_id=beat.device_id,
            received_at=beat.received_at,
            heartbeat_status=beat.heartbeat_status,
            battery_level=beat.battery_level,
            signal_strength=beat.signal_strength,
            firmware_version=beat.firmware_version,
            latitude=beat.latitude,
            longitude=beat.longitude,
            metadata=beat.extra,
        )


class DeviceControlState(BaseModel):
    """Device-level status and controls."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hardware_id: str
    status: str
    is_active: bool
    online: bool
    monitoring_mode: str
    audio_capture_enabled: bool
    recording: bool
    battery_level: int | None
    online_since: datetime | None
    last_seen_at: datetime | None


class DeviceSummary(DeviceControlState):
    """Compact device record embedded in vehicle responses."""

    vehicle_id: UUID
    device_name: str | None
    device_type: str
    firmware_version: str | None


class DeviceOut(DeviceSummary):
    vehicle_code: str
    manufacturer: str | None
    model: str | None
    registered_at: datetime
    removed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    configuration: dict[str, Any] | None
    latest_heartbeat: HeartbeatOut | None = None

    @classmethod
    def from_model(cls, device: Device, vehicle_code: str, latest: DeviceHeartbeat | None = None) -> "DeviceOut":
        data = DeviceSummary.model_validate(device).model_dump()
        return cls(
            **data,
            vehicle_code=vehicle_code,
            manufacturer=device.manufacturer,
            model=device.model,
            registered_at=device.registered_at,
            removed_at=device.removed_at,
            created_at=device.created_at,
            updated_at=device.updated_at,
            configuration=device.configuration,
            latest_heartbeat=HeartbeatOut.from_model(latest) if latest else None,
        )


class DeviceRegisteredOut(DeviceOut):
    device_key: str = Field(description="Shown once. Send it as the X-Device-Key header on heartbeats.")
