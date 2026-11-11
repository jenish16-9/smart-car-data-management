from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


def parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def get_by_id(session: AsyncSession, device_id: str) -> Device | None:
    parsed = parse_uuid(device_id)
    if parsed is None:
        return None
    result = await session.execute(select(Device).where(Device.id == parsed).execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def get_by_hardware_id(session: AsyncSession, hardware_id: str) -> Device | None:
    result = await session.execute(select(Device).where(Device.hardware_id == hardware_id))
    return result.scalar_one_or_none()


async def list_for_vehicle(session: AsyncSession, vehicle_id: UUID, *, include_removed: bool = False) -> list[Device]:
    query = select(Device).where(Device.vehicle_id == vehicle_id)
    if not include_removed:
        query = query.where(Device.removed_at.is_(None))
    result = await session.execute(query.order_by(Device.created_at.desc()))
    return list(result.scalars().all())


async def create(session: AsyncSession, **fields: object) -> Device:
    device = Device(**fields)
    session.add(device)
    await session.flush()
    return device


async def refresh(session: AsyncSession, device: Device) -> Device:
    await session.refresh(device)
    return device
