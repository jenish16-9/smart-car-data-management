from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertAction
from app.models.audio import AudioRecord
from app.models.device_status import DeviceStatus
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleAssignment


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _accessible(user: User) -> ColumnElement[bool]:
    assigned = select(VehicleAssignment.vehicle_id).where(VehicleAssignment.user_id == user.id)
    return or_(Vehicle.owner_id == user.id, Vehicle.id.in_(assigned))


async def get_by_ref(session: AsyncSession, ref: str) -> Vehicle | None:
    """Find a vehicle by UUID or by vehicle_code (e.g. CAR-1024)."""
    vehicle_uuid = _parse_uuid(ref)
    condition = Vehicle.id == vehicle_uuid if vehicle_uuid else Vehicle.vehicle_code == ref
    result = await session.execute(select(Vehicle).where(condition).execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def list_for_user(session: AsyncSession, user: User, *, limit: int, offset: int) -> list[Vehicle]:
    query = select(Vehicle).order_by(Vehicle.vehicle_code).limit(limit).offset(offset)
    if user.role != "admin":
        query = query.where(_accessible(user))
    return list((await session.execute(query)).scalars().all())


async def accessible_scope(session: AsyncSession, user: User) -> list[Vehicle] | None:
    """None means unrestricted (administrator); otherwise the vehicles the user may see."""
    if user.role == "admin":
        return None
    return list((await session.execute(select(Vehicle).where(_accessible(user)))).scalars().all())


async def user_can_access(session: AsyncSession, user: User, vehicle: Vehicle) -> bool:
    if user.role == "admin" or vehicle.owner_id == user.id:
        return True
    result = await session.execute(
        select(VehicleAssignment.id).where(
            VehicleAssignment.user_id == user.id, VehicleAssignment.vehicle_id == vehicle.id
        )
    )
    return result.first() is not None


async def create(session: AsyncSession, **fields: object) -> Vehicle:
    vehicle = Vehicle(**fields)
    session.add(vehicle)
    await session.flush()
    session.add(DeviceStatus(vehicle_id=vehicle.id))
    await session.flush()
    return vehicle


async def add_assignment(session: AsyncSession, *, user_id: UUID, vehicle_id: UUID) -> None:
    existing = await session.execute(
        select(VehicleAssignment.id).where(
            VehicleAssignment.user_id == user_id, VehicleAssignment.vehicle_id == vehicle_id
        )
    )
    if existing.first() is None:
        session.add(VehicleAssignment(user_id=user_id, vehicle_id=vehicle_id))
        await session.flush()


async def update(session: AsyncSession, vehicle: Vehicle, **fields: object) -> Vehicle:
    for key, value in fields.items():
        setattr(vehicle, key, value)
    await session.flush()
    return vehicle


async def delete(session: AsyncSession, vehicle: Vehicle) -> None:
    """Delete a vehicle and its relational children (explicit, so it also works on SQLite)."""
    alert_ids = select(Alert.id).where(Alert.vehicle_id == vehicle.id)
    await session.execute(sql_delete(AlertAction).where(AlertAction.alert_id.in_(alert_ids)))
    for model in (Alert, AudioRecord, DeviceStatus, VehicleAssignment):
        await session.execute(sql_delete(model).where(model.vehicle_id == vehicle.id))
    await session.execute(sql_delete(Vehicle).where(Vehicle.id == vehicle.id))
    await session.flush()


async def count(session: AsyncSession, vehicle_ids: list[UUID] | None) -> int:
    query = select(func.count()).select_from(Vehicle)
    if vehicle_ids is not None:
        query = query.where(Vehicle.id.in_(vehicle_ids))
    return int((await session.execute(query)).scalar_one())
