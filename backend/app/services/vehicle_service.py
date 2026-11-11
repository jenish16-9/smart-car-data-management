from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate


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
            .where(Vehicle.owner_id == owner_id)
            .order_by(Vehicle.created_at.desc())
        )
    )


def get_owned_vehicle(db: Session, owner_id: str, vehicle_id: str) -> Vehicle:
    vehicle = db.scalar(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.owner_id == owner_id)
    )
    if vehicle is None:
        # Do not reveal whether a vehicle belonging to another owner exists.
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle
