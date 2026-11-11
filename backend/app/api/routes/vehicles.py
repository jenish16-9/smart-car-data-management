from fastapi import APIRouter, Depends, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.mongodb import get_mongo_db
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.vehicle import DeviceLogOut, VehicleControlsUpdate, VehicleCreate, VehicleOut, VehicleUpdate
from app.services import vehicle_service

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    payload: VehicleCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> VehicleOut:
    return VehicleOut.from_model(await vehicle_service.create_vehicle(session, user, payload))


@router.get("", response_model=list[VehicleOut])
async def list_vehicles(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[VehicleOut]:
    vehicles = await vehicle_service.list_vehicles(session, user, limit=limit, offset=offset)
    return [VehicleOut.from_model(vehicle) for vehicle in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(
    vehicle_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> VehicleOut:
    return VehicleOut.from_model(await vehicle_service.get_accessible(session, user, vehicle_id))


@router.patch("/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: str,
    payload: VehicleUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> VehicleOut:
    return VehicleOut.from_model(await vehicle_service.update_vehicle(session, user, vehicle_id, payload))


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    await vehicle_service.delete_vehicle(session, user, vehicle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{vehicle_id}/controls", response_model=VehicleOut)
async def update_controls(
    vehicle_id: str,
    payload: VehicleControlsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> VehicleOut:
    """Set monitoring mode, audio capture and recording; each change is written to the device log."""
    return VehicleOut.from_model(await vehicle_service.update_controls(session, mongo, user, vehicle_id, payload))


@router.get("/{vehicle_id}/logs", response_model=list[DeviceLogOut])
async def device_logs(
    vehicle_id: str,
    limit: int = Query(20, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> list[DeviceLogOut]:
    return await vehicle_service.device_logs(session, mongo, user, vehicle_id, limit)
