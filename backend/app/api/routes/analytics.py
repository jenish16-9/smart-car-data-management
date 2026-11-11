from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.analytics import AnalyticsSummary, EventsByTypeItem, EventsOverTimePoint
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def analytics_summary(
    vehicle_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AnalyticsSummary:
    return await analytics_service.summary(session, mongo, user, vehicle_id)


@router.get("/events-over-time", response_model=list[EventsOverTimePoint])
async def events_over_time(
    vehicle_id: str | None = None,
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> list[EventsOverTimePoint]:
    return await analytics_service.events_over_time(session, mongo, user, vehicle_id, days)


@router.get("/events-by-type", response_model=list[EventsByTypeItem])
async def events_by_type(
    vehicle_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> list[EventsByTypeItem]:
    return await analytics_service.events_by_type(session, mongo, user, vehicle_id)
