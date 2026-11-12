from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, DeviceHeartbeat
from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories.vehicle_repository import accessible_condition


def parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def get_by_id(session: AsyncSession, device_id: str) -> Device | None:
    parsed = parse_uuid(device_id)
    return await get(session, parsed) if parsed else None


async def get(session: AsyncSession, device_id: UUID) -> Device | None:
    query = select(Device).where(Device.id == device_id).execution_options(populate_existing=True)
    return (await session.execute(query)).scalar_one_or_none()


async def get_by_hardware_id(session: AsyncSession, hardware_id: str) -> Device | None:
    return (await session.execute(select(Device).where(Device.hardware_id == hardware_id))).scalar_one_or_none()


async def list_for_user(
    session: AsyncSession,
    user: User,
    *,
    vehicle_id: UUID | None,
    status: str | None,
    include_retired: bool,
    limit: int,
    offset: int,
) -> list[tuple[Device, str]]:
    """Devices of active vehicles the user may see, as (device, vehicle_code)."""
    query = (
        select(Device, Vehicle.vehicle_code)
        .join(Vehicle, Vehicle.id == Device.vehicle_id)
        .where(Vehicle.is_active.is_(True))
        .order_by(Vehicle.vehicle_code, Device.registered_at)
        .limit(limit)
        .offset(offset)
    )
    if user.role != "admin":
        query = query.where(accessible_condition(user))
    if vehicle_id is not None:
        query = query.where(Device.vehicle_id == vehicle_id)
    if status is not None:
        query = query.where(Device.status == status)
    elif not include_retired:
        query = query.where(Device.status != "RETIRED")
    return [(row[0], row[1]) for row in (await session.execute(query)).all()]


async def create(session: AsyncSession, **fields: object) -> Device:
    fields.setdefault("device_name", fields.get("hardware_id"))
    device = Device(**fields)
    session.add(device)
    await session.flush()
    return device


async def refresh(session: AsyncSession, device: Device) -> Device:
    await session.refresh(device)
    return device


async def list_for_vehicle(session: AsyncSession, vehicle_id: UUID, *, include_removed: bool = False) -> list[Device]:
    query = select(Device).where(Device.vehicle_id == vehicle_id)
    if not include_removed:
        query = query.where(Device.removed_at.is_(None), Device.status != "RETIRED")
    result = await session.execute(query.order_by(Device.created_at.desc()))
    return list(result.scalars().all())


async def mark_stale_delayed(session: AsyncSession, cutoff: datetime) -> int:
    """ACTIVE/WARNING devices whose last heartbeat is older than `cutoff` become DELAYED."""
    stale = (Device.last_seen_at.is_(None)) | (Device.last_seen_at < cutoff)
    result = await session.execute(
        update(Device)
        .where(Device.status.in_(("ACTIVE", "WARNING")), Device.is_active.is_(True), stale)
        .values(status="DELAYED", online_since=None, recording=False)
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)


async def add_heartbeat(session: AsyncSession, **fields: object) -> DeviceHeartbeat:
    beat = DeviceHeartbeat(**fields)
    session.add(beat)
    await session.flush()
    return beat


async def latest_heartbeat(session: AsyncSession, device_id: UUID) -> DeviceHeartbeat | None:
    query = (
        select(DeviceHeartbeat)
        .where(DeviceHeartbeat.device_id == device_id)
        .order_by(DeviceHeartbeat.received_at.desc())
        .limit(1)
    )
    return (await session.execute(query)).scalar_one_or_none()


async def list_heartbeats(
    session: AsyncSession, device_id: UUID, *, start: datetime | None, end: datetime | None, limit: int, offset: int
) -> list[DeviceHeartbeat]:
    query = select(DeviceHeartbeat).where(DeviceHeartbeat.device_id == device_id)
    if start is not None:
        query = query.where(DeviceHeartbeat.received_at >= start)
    if end is not None:
        query = query.where(DeviceHeartbeat.received_at <= end)
    query = query.order_by(DeviceHeartbeat.received_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(query)).scalars().all())
