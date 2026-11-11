from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.device import Device
from app.models.vehicle import Vehicle
from app.schemas.device import DeviceCreate, DeviceResponse
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate
from app.services import device_service, vehicle_service

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: VehicleCreate, db: DbSession, user: AuthenticatedUser
) -> Vehicle:
    return vehicle_service.create_vehicle(db, user.id, payload)


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(db: DbSession, user: AuthenticatedUser) -> list[Vehicle]:
    return vehicle_service.list_vehicles(db, user.id)


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: str, db: DbSession, user: AuthenticatedUser) -> Vehicle:
    return vehicle_service.get_owned_vehicle(db, user.id, vehicle_id)


@router.patch("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: str,
    payload: VehicleUpdate,
    db: DbSession,
    user: AuthenticatedUser,
) -> Vehicle:
    return vehicle_service.update_vehicle(db, user.id, vehicle_id, payload)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vehicle(vehicle_id: str, db: DbSession, user: AuthenticatedUser) -> Response:
    vehicle_service.remove_vehicle(db, user.id, vehicle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{vehicle_id}/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle_device(
    vehicle_id: str,
    payload: DeviceCreate,
    db: DbSession,
    user: AuthenticatedUser,
) -> Device:
    return device_service.create_device(db, user.id, vehicle_id, payload)


@router.get("/{vehicle_id}/devices", response_model=list[DeviceResponse])
def list_vehicle_devices(
    vehicle_id: str, db: DbSession, user: AuthenticatedUser
) -> list[Device]:
    return device_service.list_vehicle_devices(db, user.id, vehicle_id)
