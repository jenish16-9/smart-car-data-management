from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.common import utcnow
from app.models.device import Device
from app.models.user import User
from app.repositories import device_repository, telemetry_repository, vehicle_repository
from app.schemas.telemetry import TelemetryCreate, TelemetryOut
from app.services import vehicle_service
from app.services.device_rules import default_device

ENGINE_WARNING_CELSIUS = 110.0


async def _resolve_device(session: AsyncSession, vehicle, payload: TelemetryCreate) -> Device | None:
    """The explicit device if given (must belong to the vehicle and not be retired), else the default one."""
    if payload.device_id is None:
        return default_device(vehicle)
    device = await device_repository.get(session, payload.device_id)
    if device is None or device.vehicle_id != vehicle.id:
        raise NotFoundError("Device not found on this vehicle")
    if device.status == "RETIRED":
        raise ConflictError("Device is retired and does not accept telemetry")
    return device


async def _sync_device_status(
    session: AsyncSession, vehicle, payload: TelemetryCreate, timestamp: datetime, device: Device | None
) -> bool:
    """Keep the PostgreSQL snapshot (vehicle + device_status) in step with new telemetry."""
    if device is not None and device.status != "DISABLED":
        device.last_seen_at = timestamp
        if payload.battery_level is not None:
            device.battery_level = payload.battery_level
        if device.status == "DELAYED":
            device.status = "ACTIVE"
        if device.status in ("ACTIVE", "WARNING") and device.online_since is None:
            device.online_since = timestamp
    device = vehicle.device_status
    device.last_sync_at = timestamp
    device.microphone_status = device.microphone_status if device.microphone_status != "offline" else "online"
    if payload.battery_level is not None:
        device.battery_level = payload.battery_level
    if payload.gps_status is not None:
        device.gps_status = payload.gps_status
    if payload.engine_temperature is not None:
        device.engine_status = "warning" if payload.engine_temperature >= ENGINE_WARNING_CELSIUS else "healthy"
    was_connected = vehicle.status == "connected"
    if not was_connected or device.online_since is None:
        device.online_since = timestamp
    if not was_connected:
        for registered in vehicle.devices:
            if registered.status in ("ACTIVE", "WARNING") and registered.online_since is None:
                registered.online_since = timestamp
    await vehicle_repository.update(session, vehicle, last_seen_at=timestamp, status="connected")
    await session.commit()
    return was_connected


async def ingest(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, ref: str, payload: TelemetryCreate
) -> TelemetryOut:
    vehicle = await vehicle_service.get_accessible(session, user, ref)
    timestamp = payload.timestamp or utcnow()
    explicit = payload.device_id is not None
    device = await _resolve_device(session, vehicle, payload)
    document = {
        "vehicle_id": vehicle.vehicle_code,
        "timestamp": timestamp,
        **payload.model_dump(exclude={"timestamp", "device_id"}, exclude_none=True),
    }
    if device is not None and explicit:
        document.update(device_id=str(device.id), hardware_id=device.hardware_id)
    await telemetry_repository.insert_telemetry(mongo, document)

    sensors = []
    if payload.engine_temperature is not None:
        sensors.append(("engine_temperature", payload.engine_temperature, "celsius"))
    if payload.battery_level is not None:
        sensors.append(("battery_level", float(payload.battery_level), "percent"))
    await telemetry_repository.insert_sensor_events(
        mongo,
        [
            {
                "vehicle_id": vehicle.vehicle_code,
                "sensor_type": kind,
                "value": value,
                "unit": unit,
                "timestamp": timestamp,
                **({"device_id": str(device.id), "hardware_id": device.hardware_id} if device and explicit else {}),
            }
            for kind, value, unit in sensors
        ],
    )
    if not await _sync_device_status(session, vehicle, payload, timestamp, device):
        await telemetry_repository.insert_device_log(
            mongo,
            vehicle_code=vehicle.vehicle_code,
            event_type="connection_established",
            message="Vehicle connected to server",
            timestamp=timestamp,
        )
    return TelemetryOut.from_document(document)


async def history(
    session: AsyncSession,
    mongo: AsyncIOMotorDatabase,
    user: User,
    ref: str,
    *,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[TelemetryOut]:
    vehicle = await vehicle_service.get_accessible(session, user, ref)
    documents = await telemetry_repository.list_telemetry(
        mongo, vehicle.vehicle_code, start=start, end=end, limit=limit
    )
    return [TelemetryOut.from_document(doc) for doc in documents]


async def latest(session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, ref: str) -> TelemetryOut:
    vehicle = await vehicle_service.get_accessible(session, user, ref)
    document = await telemetry_repository.latest_telemetry(mongo, vehicle.vehicle_code)
    if document is None:
        raise NotFoundError("No telemetry recorded for this vehicle yet")
    return TelemetryOut.from_document(document)
