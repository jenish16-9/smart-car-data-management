from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.device import Device
from app.schemas.device import DeviceCreate
from app.services.vehicle_service import get_owned_vehicle


def create_device(
    db: Session, owner_id: str, vehicle_id: str, payload: DeviceCreate
) -> Device:
    get_owned_vehicle(db, owner_id, vehicle_id)
    device = Device(
        id=str(uuid4()),
        owner_id=owner_id,
        vehicle_id=vehicle_id,
        **payload.model_dump(),
    )
    db.add(device)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A device with this hardware ID already exists",
        ) from exc
    db.refresh(device)
    return device


def list_vehicle_devices(db: Session, owner_id: str, vehicle_id: str) -> list[Device]:
    get_owned_vehicle(db, owner_id, vehicle_id)
    return list(
        db.scalars(
            select(Device)
            .where(Device.vehicle_id == vehicle_id, Device.owner_id == owner_id)
            .order_by(Device.created_at.desc())
        )
    )


def get_owned_device(db: Session, owner_id: str, device_id: str) -> Device:
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.owner_id == owner_id)
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device
