from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.device import DeviceState
from app.models.vehicle import Vehicle, VehicleStatus, utc_now
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


def create_vehicle(db: Session, owner_id: str, payload: VehicleCreate) -> Vehicle:
    vehicle = Vehicle(id=str(uuid4()), owner_id=owner_id, **payload.model_dump())
    db.add(vehicle)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A vehicle with this VIN already exists",
        ) from exc
    db.refresh(vehicle)
    return vehicle


def list_vehicles(db: Session, owner_id: str) -> list[Vehicle]:
    return list(
        db.scalars(
            select(Vehicle)
            .where(Vehicle.owner_id == owner_id, Vehicle.removed_at.is_(None))
            .order_by(Vehicle.created_at.desc())
        )
    )


def get_owned_vehicle(db: Session, owner_id: str, vehicle_id: str) -> Vehicle:
    vehicle = db.scalar(
        select(Vehicle).where(
            Vehicle.id == vehicle_id,
            Vehicle.owner_id == owner_id,
            Vehicle.removed_at.is_(None),
        )
    )
    if vehicle is None:
        # Do not reveal whether a vehicle belonging to another owner exists.
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


def update_vehicle(
    db: Session,
    owner_id: str,
    vehicle_id: str,
    payload: VehicleUpdate,
) -> Vehicle:
    vehicle = get_owned_vehicle(db, owner_id, vehicle_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(vehicle, field, value)
    if payload.status == VehicleStatus.DEACTIVATED:
        for device in vehicle.devices:
            if device.state != DeviceState.RETIRED:
                device.state = DeviceState.DISABLED
    db.commit()
    db.refresh(vehicle)
    return vehicle


def remove_vehicle(db: Session, owner_id: str, vehicle_id: str) -> None:
    vehicle = get_owned_vehicle(db, owner_id, vehicle_id)
    now = utc_now()
    vehicle.status = VehicleStatus.DEACTIVATED
    vehicle.removed_at = now
    for device in vehicle.devices:
        if device.state != DeviceState.RETIRED:
            device.state = DeviceState.RETIRED
            device.retired_at = now
        device.removed_at = now
    db.commit()
