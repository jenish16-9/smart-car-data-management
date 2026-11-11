from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertAction

ACTIVE_STATUSES = ("open", "acknowledged")
CRITICAL_SEVERITIES = ("high", "critical")


async def create(session: AsyncSession, **fields: object) -> Alert:
    alert = Alert(**fields)
    session.add(alert)
    await session.flush()
    return await get(session, alert.id)  # type: ignore[return-value]  # reload with vehicle


async def get(session: AsyncSession, alert_id: UUID) -> Alert | None:
    result = await session.execute(select(Alert).where(Alert.id == alert_id).execution_options(populate_existing=True))
    return result.scalar_one_or_none()


async def list_alerts(
    session: AsyncSession,
    *,
    vehicle_ids: list[UUID] | None,
    vehicle_id: UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> list[Alert]:
    query = select(Alert).order_by(Alert.detected_at.desc()).limit(limit).offset(offset)
    if vehicle_ids is not None:
        query = query.where(Alert.vehicle_id.in_(vehicle_ids))
    if vehicle_id is not None:
        query = query.where(Alert.vehicle_id == vehicle_id)
    if status:
        query = query.where(Alert.status == status)
    return list((await session.execute(query)).scalars().all())


async def add_action(
    session: AsyncSession, *, alert_id: UUID, user_id: UUID | None, action_type: str, notes: str | None
) -> AlertAction:
    action = AlertAction(alert_id=alert_id, user_id=user_id, action_type=action_type, notes=notes)
    session.add(action)
    await session.flush()
    return action


async def list_actions(session: AsyncSession, alert_id: UUID) -> list[AlertAction]:
    query = select(AlertAction).where(AlertAction.alert_id == alert_id).order_by(AlertAction.created_at)
    return list((await session.execute(query)).scalars().all())


async def save(session: AsyncSession, alert: Alert) -> Alert:
    await session.flush()
    return alert


async def stats(session: AsyncSession, vehicle_ids: list[UUID] | None) -> dict[str, int]:
    """Alert counters used by the analytics summary."""

    def count_where(*conditions: object) -> object:
        query = select(func.count()).select_from(Alert).where(*conditions)
        if vehicle_ids is not None:
            query = query.where(Alert.vehicle_id.in_(vehicle_ids))
        return query

    total = (await session.execute(count_where())).scalar_one()
    active = (await session.execute(count_where(Alert.status.in_(ACTIVE_STATUSES)))).scalar_one()
    resolved = (await session.execute(count_where(Alert.status == "resolved"))).scalar_one()
    critical = (await session.execute(count_where(Alert.severity.in_(CRITICAL_SEVERITIES)))).scalar_one()
    return {"total": int(total), "active": int(active), "resolved": int(resolved), "critical": int(critical)}
