from fastapi import APIRouter, Depends, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.device import (
    DeviceConfigurationUpdate,
    DeviceOut,
    DeviceUpdate,
    HeartbeatCreate,
    HeartbeatRecord,
    HeartbeatResponse,
)
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    return DeviceOut.model_validate(await device_service.get_accessible(session, user, device_id))


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: str,
    payload: DeviceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    return DeviceOut.model_validate(await device_service.update_device(session, user, device_id, payload))


@router.put("/{device_id}/configuration", response_model=DeviceOut)
async def update_configuration(
    device_id: str,
    payload: DeviceConfigurationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceOut:
    return DeviceOut.model_validate(await device_service.update_configuration(session, user, device_id, payload))


@router.post("/{device_id}/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    device_id: str,
    payload: HeartbeatCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> HeartbeatResponse:
    return await device_service.process_heartbeat(session, mongo, user, device_id, payload)


@router.get("/{device_id}/heartbeats", response_model=list[HeartbeatRecord])
async def heartbeats(
    device_id: str,
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> list[HeartbeatRecord]:
    return await device_service.heartbeat_history(session, mongo, user, device_id, limit)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(
    device_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await device_service.remove_device(session, user, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
