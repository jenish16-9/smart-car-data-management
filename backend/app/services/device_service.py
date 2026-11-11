from datetime import timedelta
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.common import utcnow
from app.models.device import Device
from app.models.user import User
from app.repositories import device_repository, telemetry_repository, vehicle_repository
from app.schemas.device import (
    DeviceConfigurationUpdate,
    DeviceCreate,
    DeviceUpdate,
    HeartbeatCreate,
    HeartbeatRecord,
    HeartbeatResponse,
)
from app.services import vehicle_service

TERMINAL_STATES = {"DISABLED", "RETIRED"}


async def get_accessible(session: AsyncSession, user: User, device_id: str) -> Device:
    device = await device_repository.get_by_id(session, device_id)
    if device is None:
        raise NotFoundError("Device not found")
    if user.role == "admin" or device.owner_id == user.id:
        return await refresh_connectivity(session, device)
    if device.vehicle and await vehicle_repository.user_can_access(session, user, device.vehicle):
        return await refresh_connectivity(session, device)
    raise NotFoundError("Device not found")


def require_manage(user: User, device: Device) -> None:
    if user.role != "admin" and device.owner_id != user.id:
        raise ForbiddenError("Only the device owner or an administrator can modify it")


async def refresh_connectivity(session: AsyncSession, device: Device) -> Device:
    if device.state in TERMINAL_STATES or device.last_heartbeat_at is None:
        return device
    age = utcnow() - device.last_heartbeat_at
    previous = device.state
    if age >= timedelta(seconds=settings.device_offline_after_seconds):
        device.state = "OFFLINE"
    elif age >= timedelta(seconds=settings.device_delayed_after_seconds):
        device.state = "DELAYED"
    elif device.state in {"DELAYED", "OFFLINE"}:
        device.state = "ONLINE"
    if device.state != previous:
        await session.commit()
        await session.refresh(device)
    return device


async def create_device(
    session: AsyncSession,
    user: User,
    vehicle_ref: str,
    payload: DeviceCreate,
) -> Device:
    vehicle = await vehicle_service.get_accessible(session, user, vehicle_ref)
    if user.role != "admin" and vehicle.owner_id != user.id:
        raise ForbiddenError("Only the vehicle owner or an administrator can add devices")
    if await device_repository.get_by_hardware_id(session, payload.hardware_id):
        raise ConflictError("A device with this hardware ID already exists")
    device = await device_repository.create(
        session,
        vehicle_id=vehicle.id,
        owner_id=vehicle.owner_id or user.id,
        hardware_id=payload.hardware_id,
        name=payload.name,
        firmware_version=payload.firmware_version,
        configuration=payload.configuration.model_dump(by_alias=True),
        state="PENDING",
    )
    await session.commit()
    return await device_repository.refresh(session, device)


async def list_devices(session: AsyncSession, user: User, vehicle_ref: str) -> list[Device]:
    vehicle = await vehicle_service.get_accessible(session, user, vehicle_ref)
    devices = await device_repository.list_for_vehicle(session, vehicle.id)
    return [await refresh_connectivity(session, device) for device in devices]


async def update_device(
    session: AsyncSession,
    user: User,
    device_id: str,
    payload: DeviceUpdate,
) -> Device:
    device = await get_accessible(session, user, device_id)
    require_manage(user, device)
    if device.state == "RETIRED":
        raise ConflictError("Retired device cannot be updated")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    if payload.state == "RETIRED":
        device.retired_at = utcnow()
    await session.commit()
    return await device_repository.refresh(session, device)


async def update_configuration(
    session: AsyncSession,
    user: User,
    device_id: str,
    payload: DeviceConfigurationUpdate,
) -> Device:
    device = await get_accessible(session, user, device_id)
    require_manage(user, device)
    if device.state == "RETIRED":
        raise ConflictError("Retired device configuration cannot be changed")
    device.configuration = payload.configuration.model_dump(by_alias=True)
    await session.commit()
    return await device_repository.refresh(session, device)


async def process_heartbeat(
    session: AsyncSession,
    mongo: AsyncIOMotorDatabase,
    user: User,
    device_id: str,
    payload: HeartbeatCreate,
) -> HeartbeatResponse:
    device = await get_accessible(session, user, device_id)
    if device.state == "RETIRED":
        raise ConflictError("Retired device rejects heartbeats")
    now = utcnow()
    if payload.reported_at and payload.reported_at > now + timedelta(minutes=5):
        raise ConflictError("Heartbeat timestamp is in the future")
    heartbeat_id = str(uuid4())
    document = {
        "heartbeat_id": heartbeat_id,
        "device_id": str(device.id),
        "vehicle_id": device.vehicle.vehicle_code if device.vehicle else None,
        "health": payload.health,
        "reported_at": payload.reported_at,
        "received_at": now,
        "metrics": payload.metrics,
    }
    await telemetry_repository.insert_device_heartbeat(mongo, document)
    device.last_heartbeat_at = now
    if device.state != "DISABLED":
        device.state = "WARNING" if payload.health == "WARNING" else "ONLINE"
    await session.commit()
    await session.refresh(device)
    return HeartbeatResponse(**document, device_state=device.state)


async def heartbeat_history(
    session: AsyncSession,
    mongo: AsyncIOMotorDatabase,
    user: User,
    device_id: str,
    limit: int,
) -> list[HeartbeatRecord]:
    device = await get_accessible(session, user, device_id)
    documents = await telemetry_repository.list_device_heartbeats(mongo, str(device.id), limit)
    return [HeartbeatRecord(**document) for document in documents]


async def remove_device(session: AsyncSession, user: User, device_id: str) -> None:
    device = await get_accessible(session, user, device_id)
    require_manage(user, device)
    now = utcnow()
    device.state = "RETIRED"
    device.retired_at = device.retired_at or now
    device.removed_at = now
    await session.commit()
