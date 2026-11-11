from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import alert_repository, analysis_repository, audio_repository, vehicle_repository
from app.schemas.analytics import AnalyticsSummary, EventsByTypeItem, EventsOverTimePoint
from app.services import vehicle_service


async def _scope(session: AsyncSession, user: User, vehicle: str | None):
    """Return (vehicle UUIDs | None, vehicle codes | None); None means unrestricted."""
    if vehicle:
        found = await vehicle_service.get_accessible(session, user, vehicle)
        return [found.id], [found.vehicle_code]
    scope = await vehicle_repository.accessible_scope(session, user)
    if scope is None:
        return None, None
    return [v.id for v in scope], [v.vehicle_code for v in scope]


def _percent(value: float) -> int:
    return int(round(value * 100))


async def summary(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, vehicle: str | None
) -> AnalyticsSummary:
    ids, codes = await _scope(session, user, vehicle)
    alerts = await alert_repository.stats(session, ids)
    events = await analysis_repository.summary(mongo, codes)
    return AnalyticsSummary(
        total_events=int(events["total"]),
        critical_events=alerts["critical"],
        average_confidence=_percent(events["average_confidence"]),
        resolution_rate=round(alerts["resolved"] * 100 / alerts["total"]) if alerts["total"] else 0,
        vehicle_count=await vehicle_repository.count(session, ids),
        audio_upload_count=await audio_repository.count(session, ids),
        detection_count=int(events["detections"]),
        active_alert_count=alerts["active"],
    )


async def events_over_time(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, vehicle: str | None, days: int
) -> list[EventsOverTimePoint]:
    _, codes = await _scope(session, user, vehicle)
    rows = await analysis_repository.events_over_time(mongo, codes, days=days)
    return [EventsOverTimePoint(**row) for row in rows]


async def events_by_type(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, vehicle: str | None
) -> list[EventsByTypeItem]:
    _, codes = await _scope(session, user, vehicle)
    rows = await analysis_repository.events_by_type(mongo, codes)
    return [EventsByTypeItem(**{**row, "average_confidence": _percent(row["average_confidence"])}) for row in rows]
