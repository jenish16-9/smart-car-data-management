from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.device import Device, DeviceHeartbeat

DeviceStatusValue = Literal["PENDING", "ACTIVE", "WARNING", "DELAYED", "DISABLED", "RETIRED"]
DeviceType = Literal["microphone", "audio_sensor", "gps", "imu", "camera", "gateway", "other"]
HeartbeatStatus = Literal["ok", "warning", "error"]
MonitoringMode = Literal["continuous", "motion_triggered", "paused"]

HARDWARE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9:_.-]{3,62}$"


class DeviceCreate(BaseModel):
    vehicle_id: str | None = Field(default=None, description="Vehicle UUID or vehicle_code (e.g. CAR-1024).")
    hardware_id: str = Field(pattern=HARDWARE_ID_PATTERN, examples=["MIC-A1B2C3D4"])
    device_type: DeviceType = "audio_sensor"
    device_name: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    firmware_version: str | None = Field(default=None, max_length=40)

    @model_validator(mode="before")
    @classmethod
    def accept_vehicle_scoped_names(cls, value):
        if isinstance(value, dict) and "device_name" not in value and "name" in value:
            value = {**value, "device_name": value["name"]}
        return value


class DeviceUpdate(BaseModel):
    device_name: str | None = Field(default=None, max_length=100)
    device_type: DeviceType | None = None
    manufacturer: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    firmware_version: str | None = Field(default=None, max_length=40)
    status: DeviceStatusValue | None = None
    configuration: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_vehicle_scoped_names(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            if "device_name" not in value and "name" in value:
                value["device_name"] = value["name"]
            if "status" not in value and "state" in value:
                value["status"] = value["state"]
        return value


class DeviceControlsUpdate(BaseModel):
    monitoring_mode: MonitoringMode | None = None
    audio_capture_enabled: bool | None = None
    recording: bool | None = None


class HeartbeatCreate(BaseModel):
    hardware_id: str | None = Field(
        default=None, pattern=HARDWARE_ID_PATTERN, description="Must match the device's registered hardware ID."
    )
    heartbeat_status: HeartbeatStatus = "ok"
    battery_level: int | None = Field(default=None, ge=0, le=100)
    signal_strength: float | None = Field(default=None, ge=-150, le=100, description="dBm or percent")
    firmware_version: str | None = Field(default=None, max_length=40)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    metadata: dict[str, Any] | None = None
    reported_at: datetime | None = None
    health: Literal["HEALTHY", "WARNING"] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reported_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("reported_at must include a timezone")
        return value


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
    heartbeat_id: UUID
    vehicle_id: str | None = None
    health: str
    reported_at: datetime | None = None
    metrics: dict[str, Any]

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
            heartbeat_id=beat.id,
            health="WARNING" if beat.heartbeat_status != "ok" else "HEALTHY",
            metrics=beat.extra or {},
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
    owner_id: UUID | None = None
    name: str
    state: str
    last_heartbeat_at: datetime | None
    retired_at: datetime | None

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
            owner_id=device.owner_id,
            name=device.device_name or device.hardware_id,
            state="ONLINE" if device.status == "ACTIVE" else device.status,
            last_heartbeat_at=device.last_seen_at,
            retired_at=device.retired_at,
        )


class DeviceRegisteredOut(DeviceOut):
    device_key: str = Field(description="Shown once. Send it as the X-Device-Key header on heartbeats.")


class DeviceConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    capture_enabled: bool = Field(default=True, alias="captureEnabled")
    monitoring_mode: MonitoringMode = Field(default="motion_triggered", alias="monitoringMode")
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=3600, alias="heartbeatIntervalSeconds")


class DeviceConfigurationUpdate(BaseModel):
    configuration: DeviceConfiguration


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
