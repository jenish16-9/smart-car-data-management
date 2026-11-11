from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.device import Device
from app.models.heartbeat import DeviceHeartbeat
from app.schemas.device import (
    DeviceConfigurationUpdate,
    DeviceResponse,
    DeviceUpdate,
    HeartbeatCreate,
    HeartbeatRecord,
    HeartbeatResponse,
)
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["Devices"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: DbSession, user: AuthenticatedUser) -> Device:
    return device_service.get_owned_device(db, user.id, device_id)


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    db: DbSession,
    user: AuthenticatedUser,
) -> Device:
    return device_service.update_device(db, user.id, device_id, payload)


@router.put("/{device_id}/configuration", response_model=DeviceResponse)
def update_device_configuration(
    device_id: str,
    payload: DeviceConfigurationUpdate,
    db: DbSession,
    user: AuthenticatedUser,
) -> Device:
    return device_service.update_configuration(db, user.id, device_id, payload)


@router.post("/{device_id}/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    device_id: str,
    payload: HeartbeatCreate,
    db: DbSession,
    user: AuthenticatedUser,
) -> HeartbeatResponse:
    return device_service.process_heartbeat(db, user.id, device_id, payload)


@router.get("/{device_id}/heartbeats", response_model=list[HeartbeatRecord])
def list_heartbeats(
    device_id: str, db: DbSession, user: AuthenticatedUser
) -> list[DeviceHeartbeat]:
    return device_service.list_heartbeats(db, user.id, device_id)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(device_id: str, db: DbSession, user: AuthenticatedUser) -> Response:
    device_service.remove_device(db, user.id, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
