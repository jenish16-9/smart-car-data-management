from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.telemetry import TelemetryCreate, TelemetryOut
from app.services import telemetry_service

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("/{vehicle_id}", response_model=TelemetryOut, status_code=status.HTTP_201_CREATED)
async def ingest_telemetry(
    vehicle_id: str,
    payload: TelemetryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> TelemetryOut:
    return await telemetry_service.ingest(session, mongo, user, vehicle_id, payload)


@router.get("/{vehicle_id}/latest", response_model=TelemetryOut)
async def latest_telemetry(
    vehicle_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> TelemetryOut:
    return await telemetry_service.latest(session, mongo, user, vehicle_id)


@router.get("/{vehicle_id}", response_model=list[TelemetryOut])
async def telemetry_history(
    vehicle_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> list[TelemetryOut]:
    return await telemetry_service.history(session, mongo, user, vehicle_id, start=start, end=end, limit=limit)
