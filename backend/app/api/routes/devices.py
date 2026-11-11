from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.device import Device
from app.schemas.device import DeviceResponse
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["Devices"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: DbSession, user: AuthenticatedUser) -> Device:
    return device_service.get_owned_device(db, user.id, device_id)
