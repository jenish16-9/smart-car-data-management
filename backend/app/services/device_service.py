"""IoT device registration, lifecycle, device-level controls and heartbeat history."""

import hashlib
import hmac
import secrets
from datetime import datetime
from uuid import UUID, uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.common import utcnow
from app.models.device import Device, DeviceHeartbeat
from app.models.user import User
from app.repositories import analysis_repository, device_repository, telemetry_repository, vehicle_repository
from app.schemas.device import (
    DeviceConfigurationUpdate,
    DeviceControlsUpdate,
    DeviceCreate,
    DeviceOut,
    DeviceUpdate,
    HeartbeatCreate,
    SimulatedAudioEvent,
)
from app.services import alert_service, audio_classifier, vehicle_service
from app.services.device_rules import ONLINE_STATUSES, require_controllable, stale_cutoff, status_after_heartbeat


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise ForbiddenError("Administrator access required")


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def refresh_stale(session: AsyncSession) -> None:
    """Late heartbeat rule: ACTIVE/WARNING devices not heard from within the timeout become DELAYED."""
    if await device_repository.mark_stale_delayed(session, stale_cutoff(utcnow())):
        await session.commit()


async def _load(session: AsyncSession, device_id: str) -> Device:
    parsed = _parse_uuid(device_id)
    device = await device_repository.get(session, parsed) if parsed else None
    if device is None:
        raise NotFoundError("Device not found")
    return device


async def get_accessible(session: AsyncSession, user: User, device_id: str) -> tuple[Device, str]:
    """The device and its vehicle_code; 404 if missing or the user cannot see its vehicle."""
    await refresh_stale(session)
    device = await _load(session, device_id)
    vehicle = await vehicle_repository.get_by_ref(session, str(device.vehicle_id))
    if vehicle is None or not vehicle.is_active or not await vehicle_repository.user_can_access(session, user, vehicle):
        raise NotFoundError("Device not found")
    return device, vehicle.vehicle_code


async def _to_out(session: AsyncSession, device: Device, vehicle_code: str, *, detail: bool = True) -> DeviceOut:
    latest = await device_repository.latest_heartbeat(session, device.id) if detail else None
    return DeviceOut.from_model(device, vehicle_code, latest)


async def register(session: AsyncSession, user: User, payload: DeviceCreate) -> tuple[DeviceOut, str]:
    _require_admin(user)
    if payload.vehicle_id is None:
        raise ConflictError("vehicle_id is required")
    vehicle = await vehicle_service.get_accessible(session, user, payload.vehicle_id)
    if await device_repository.get_by_hardware_id(session, payload.hardware_id):
        raise ConflictError(f"Hardware ID {payload.hardware_id} is already registered")
    key = f"dk_{secrets.token_urlsafe(32)}"
    fields = payload.model_dump(exclude={"vehicle_id"})
    fields["device_name"] = fields.get("device_name") or payload.hardware_id
    device = await device_repository.create(
        session,
        vehicle_id=vehicle.id,
        owner_id=vehicle.owner_id or user.id,
        status="PENDING",  # becomes ACTIVE on its first valid heartbeat
        api_key_hash=_hash_key(key),
        configuration={},
        **fields,
    )
    await session.commit()
    return await _to_out(session, await _load(session, str(device.id)), vehicle.vehicle_code), key


async def rotate_key(session: AsyncSession, user: User, device_id: str) -> str:
    _require_admin(user)
    device, _ = await get_accessible(session, user, device_id)
    if device.status == "RETIRED":
        raise ConflictError("Device is retired")
    key = f"dk_{secrets.token_urlsafe(32)}"
    device.api_key_hash = _hash_key(key)
    await session.commit()
    return key


async def list_devices(
    session: AsyncSession,
    user: User,
    *,
    vehicle: str | None,
    status: str | None,
    include_retired: bool,
    limit: int,
    offset: int,
) -> list[DeviceOut]:
    await refresh_stale(session)
    vehicle_id = (await vehicle_service.get_accessible(session, user, vehicle)).id if vehicle else None
    rows = await device_repository.list_for_user(
        session, user, vehicle_id=vehicle_id, status=status, include_retired=include_retired, limit=limit, offset=offset
    )
    return [DeviceOut.from_model(device, code) for device, code in rows]


async def get_detail(session: AsyncSession, user: User, device_id: str) -> DeviceOut:
    device, code = await get_accessible(session, user, device_id)
    return await _to_out(session, device, code)


async def update(session: AsyncSession, user: User, device_id: str, payload: DeviceUpdate) -> DeviceOut:
    _require_admin(user)
    device, code = await get_accessible(session, user, device_id)
    if device.status == "RETIRED":
        raise ConflictError("Retired devices cannot be modified")
    fields = payload.model_dump(exclude_unset=True, exclude_none=True)
    new_status = fields.pop("status", None)
    for key, value in fields.items():
        setattr(device, key, value)
    if new_status is not None:
        _apply_admin_status(device, new_status)
    await session.commit()
    return await _to_out(session, await _load(session, device_id), code)


def _apply_admin_status(device: Device, new_status: str) -> None:
    """Administrators may set any status; leaving the online states clears uptime and recording."""
    device.status = new_status
    if new_status == "RETIRED":
        device.removed_at, device.is_active = utcnow(), False
    if new_status not in ONLINE_STATUSES:
        device.online_since, device.recording = None, False


async def retire(session: AsyncSession, user: User, device_id: str) -> None:
    """Soft removal: status RETIRED, is_active false, removed_at set. History is kept."""
    _require_admin(user)
    device, _ = await get_accessible(session, user, device_id)
    if device.status != "RETIRED":
        _apply_admin_status(device, "RETIRED")
        await session.commit()


async def controls(session: AsyncSession, user: User, device_id: str) -> Device:
    device, _ = await get_accessible(session, user, device_id)
    return device


async def update_controls(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, device_id: str, payload: DeviceControlsUpdate
) -> Device:
    device, code = await get_accessible(session, user, device_id)
    require_controllable(device)
    changes = vehicle_service.control_changes(device, payload)
    await session.commit()
    for _field, event_type, message in changes:
        await telemetry_repository.insert_device_log(
            mongo,
            vehicle_code=code,
            event_type=event_type,
            message=message,
            timestamp=utcnow(),
            device_id=str(device.id),
            hardware_id=device.hardware_id,
        )
    return await _load(session, device_id)


async def _verify_identity(device: Device, payload: HeartbeatCreate) -> None:
    if payload.hardware_id is not None and not hmac.compare_digest(device.hardware_id, payload.hardware_id):
        raise ForbiddenError("Hardware ID does not match this device")


async def heartbeat(
    session: AsyncSession,
    mongo: AsyncIOMotorDatabase,
    device_id: str,
    payload: HeartbeatCreate,
    *,
    user: User | None,
    device_key: str | None,
) -> DeviceOut:
    """Record a heartbeat. Identity: the device key (X-Device-Key) or a signed-in user with access to the
    vehicle, and in both cases the payload hardware_id must match the registered one."""
    device = await _load(session, device_id)
    if device_key is not None:
        if not device.api_key_hash or not hmac.compare_digest(device.api_key_hash, _hash_key(device_key)):
            raise ForbiddenError("Invalid device key")
        vehicle = await vehicle_repository.get_by_ref(session, str(device.vehicle_id))
        code = vehicle.vehicle_code if vehicle else ""
    elif user is not None:
        device, code = await get_accessible(session, user, device_id)
    else:
        raise ForbiddenError("Authentication required")
    await _verify_identity(device, payload)
    if device.status == "RETIRED":
        raise ConflictError("Device is retired and does not accept heartbeats")

    now = utcnow()
    was_online = device.status in ONLINE_STATUSES
    heartbeat_status = "warning" if payload.health == "WARNING" else payload.heartbeat_status
    metrics = {**payload.metrics, **(payload.metadata or {})}
    battery_level = payload.battery_level if payload.battery_level is not None else metrics.get("batteryPercent")
    await device_repository.add_heartbeat(
        session,
        device_id=device.id,
        received_at=now,
        heartbeat_status=heartbeat_status,
        battery_level=battery_level,
        signal_strength=payload.signal_strength,
        firmware_version=payload.firmware_version,
        latitude=payload.latitude,
        longitude=payload.longitude,
        extra=metrics,
    )
    device.last_seen_at = now
    if battery_level is not None:
        device.battery_level = battery_level
    if payload.firmware_version:
        device.firmware_version = payload.firmware_version
    new_status = status_after_heartbeat(device.status, heartbeat_status, battery_level)
    device.status = new_status  # unchanged for DISABLED
    if new_status in ONLINE_STATUSES and not was_online:
        device.online_since = now
    await session.commit()
    if not was_online and new_status in ONLINE_STATUSES:
        await telemetry_repository.insert_device_log(
            mongo,
            vehicle_code=code,
            event_type="device_online",
            message=f"Device {device.hardware_id} is online",
            timestamp=now,
            device_id=str(device.id),
            hardware_id=device.hardware_id,
        )
    return await _to_out(session, await _load(session, device_id), code)


async def list_heartbeats(
    session: AsyncSession,
    user: User,
    device_id: str,
    *,
    start: datetime | None,
    end: datetime | None,
    limit: int,
    offset: int,
) -> list[DeviceHeartbeat]:
    device, _ = await get_accessible(session, user, device_id)
    return await device_repository.list_heartbeats(session, device.id, start=start, end=end, limit=limit, offset=offset)


async def create_device(session: AsyncSession, user: User, vehicle_ref: str, payload: DeviceCreate) -> DeviceOut:
    """Vehicle-scoped registration used by the management UI; administrators only."""
    _require_admin(user)
    vehicle = await vehicle_service.get_accessible(session, user, vehicle_ref)
    if await device_repository.get_by_hardware_id(session, payload.hardware_id):
        raise ConflictError("A device with this hardware ID already exists")
    configuration = {
        "captureEnabled": True,
        "monitoringMode": "motion_triggered",
        "heartbeatIntervalSeconds": 30,
    }
    device = await device_repository.create(
        session,
        vehicle_id=vehicle.id,
        owner_id=vehicle.owner_id or user.id,
        hardware_id=payload.hardware_id.upper(),
        device_name=payload.device_name or payload.hardware_id,
        device_type=payload.device_type,
        manufacturer=payload.manufacturer,
        model=payload.model,
        firmware_version=payload.firmware_version,
        configuration=configuration,
        status="PENDING",
        api_key_hash=_hash_key(f"dk_{secrets.token_urlsafe(32)}"),
    )
    await session.commit()
    return await _to_out(session, await _load(session, str(device.id)), vehicle.vehicle_code)


async def list_vehicle_devices(session: AsyncSession, user: User, vehicle_ref: str) -> list[DeviceOut]:
    vehicle = await vehicle_service.get_accessible(session, user, vehicle_ref)
    devices = await device_repository.list_for_vehicle(session, vehicle.id)
    return [DeviceOut.from_model(device, vehicle.vehicle_code) for device in devices]


async def update_configuration(
    session: AsyncSession,
    user: User,
    device_id: str,
    payload: DeviceConfigurationUpdate,
) -> DeviceOut:
    _require_admin(user)
    device, code = await get_accessible(session, user, device_id)
    require_controllable(device)
    config = payload.configuration.model_dump(by_alias=True)
    device.configuration = config
    device.audio_capture_enabled = config["captureEnabled"]
    device.monitoring_mode = config["monitoringMode"]
    await session.commit()
    return await _to_out(session, await _load(session, device_id), code)


async def classify_simulated_audio(
    session: AsyncSession,
    mongo: AsyncIOMotorDatabase,
    user: User,
    device_id: str,
    audio_bytes: bytes,
    *,
    location: str | None = None,
) -> SimulatedAudioEvent:
    device, vehicle_code = await get_accessible(session, user, device_id)
    if device.status in {"DISABLED", "RETIRED"}:
        raise ConflictError(f"{device.status.title()} device rejects audio event data")
    if device.vehicle_id is None:
        raise ConflictError("Device is not associated with a vehicle")
    try:
        result = audio_classifier.classify_audio(audio_bytes)
    except (RuntimeError, ValueError) as exc:
        raise UnprocessableError(f"Audio classification failed: {exc}") from exc

    event_id = uuid4()
    timestamp = utcnow()
    severity = alert_service.SEVERITY_BY_CLASS.get(result.event_type)
    document = {
        "audio_record_id": str(event_id),
        "event_id": str(event_id),
        "vehicle_id": vehicle_code,
        "device_id": str(device.id),
        "predicted_class": result.event_type,
        "confidence": result.confidence,
        "severity": severity,
        "timestamp": timestamp,
        "location": location,
        "is_simulation": True,
        "model_version": result.model_version,
        "model_name": result.model_name,
        "processing_time_ms": result.processing_time_ms,
        "processing_timestamp": result.processing_timestamp,
        "created_at": timestamp,
    }
    await analysis_repository.insert_result(mongo, document)
    alert_id = None
    if alert_service.should_raise_alert(result.event_type, result.confidence):
        alert = await alert_service.create_from_simulation(
            session,
            vehicle_id=device.vehicle_id,
            event_id=event_id,
            analysis=document,
            location=location,
        )
        await session.commit()
        alert_id = alert.id
    return SimulatedAudioEvent(
        eventId=event_id,
        vehicleId=vehicle_code,
        deviceId=device.id,
        eventType=result.event_type,
        confidence=result.confidence,
        severity=severity,
        timestamp=timestamp,
        location=location,
        isSimulation=True,
        modelVersion=result.model_version,
        processingTimestamp=result.processing_timestamp,
        alertId=alert_id,
    )
