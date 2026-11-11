from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_admin
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.alert import AlertActionRequest, AlertCreate, AlertDetail, AlertOut, AlertStatus
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: AlertCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> AlertOut:
    return await alert_service.create_alert(session, user, payload)


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    vehicle_id: str | None = None,
    status: AlertStatus | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertOut]:
    return await alert_service.list_alerts(session, user, vehicle=vehicle_id, status=status, limit=limit, offset=offset)


@router.get("/{alert_id}", response_model=AlertDetail)
async def get_alert(
    alert_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AlertDetail:
    return await alert_service.get_detail(session, mongo, user, alert_id)


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: UUID,
    payload: AlertActionRequest | None = None,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    return await alert_service.acknowledge(session, user, alert_id, payload.notes if payload else None)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: UUID,
    payload: AlertActionRequest | None = None,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    return await alert_service.resolve(session, user, alert_id, payload.notes if payload else None)
