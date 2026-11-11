from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceState
from app.models.heartbeat import DeviceHealth, DeviceHeartbeat
from app.models.vehicle import VehicleStatus, utc_now
from app.schemas.device import (
    DeviceConfigurationUpdate,
    DeviceCreate,
    DeviceUpdate,
    HeartbeatCreate,
    HeartbeatResponse,
)
from app.services.vehicle_service import get_owned_vehicle


def create_device(
    db: Session, owner_id: str, vehicle_id: str, payload: DeviceCreate
) -> Device:
    vehicle = get_owned_vehicle(db, owner_id, vehicle_id)
    if vehicle.status != VehicleStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Vehicle is deactivated")
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
    devices = list(
        db.scalars(
            select(Device)
            .where(
                Device.vehicle_id == vehicle_id,
                Device.owner_id == owner_id,
                Device.removed_at.is_(None),
            )
            .order_by(Device.created_at.desc())
        )
    )
    return [refresh_connectivity(db, device) for device in devices]


def get_owned_device(db: Session, owner_id: str, device_id: str) -> Device:
    device = db.scalar(
        select(Device).where(Device.id == device_id, Device.owner_id == owner_id)
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    refresh_connectivity(db, device)
    return device


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def refresh_connectivity(db: Session, device: Device) -> Device:
    if device.state in {DeviceState.DISABLED, DeviceState.RETIRED}:
        return device
    if device.last_heartbeat_at is None:
        return device
    age = utc_now() - _as_utc(device.last_heartbeat_at)
    previous = device.state
    if age >= timedelta(seconds=settings.device_offline_after_seconds):
        device.state = DeviceState.OFFLINE
    elif age >= timedelta(seconds=settings.device_delayed_after_seconds):
        device.state = DeviceState.DELAYED
    elif device.state in {DeviceState.DELAYED, DeviceState.OFFLINE}:
        device.state = DeviceState.ONLINE
    if device.state != previous:
        db.commit()
        db.refresh(device)
    return device


def update_device(
    db: Session, owner_id: str, device_id: str, payload: DeviceUpdate
) -> Device:
    device = get_owned_device(db, owner_id, device_id)
    if device.state == DeviceState.RETIRED:
        raise HTTPException(status_code=409, detail="Retired device cannot be updated")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(device, field, value)
    if payload.state == DeviceState.RETIRED:
        device.retired_at = utc_now()
    db.commit()
    db.refresh(device)
    return device


def update_configuration(
    db: Session,
    owner_id: str,
    device_id: str,
    payload: DeviceConfigurationUpdate,
) -> Device:
    device = get_owned_device(db, owner_id, device_id)
    if device.state == DeviceState.RETIRED:
        raise HTTPException(
            status_code=409, detail="Retired device configuration cannot be changed"
        )
    device.configuration = payload.configuration.model_dump(by_alias=True)
    db.commit()
    db.refresh(device)
    return device


def process_heartbeat(
    db: Session, owner_id: str, device_id: str, payload: HeartbeatCreate
) -> HeartbeatResponse:
    device = get_owned_device(db, owner_id, device_id)
    if device.state == DeviceState.RETIRED:
        raise HTTPException(status_code=409, detail="Retired device rejects heartbeats")
    now = utc_now()
    if payload.reported_at and _as_utc(payload.reported_at) > now + timedelta(
        minutes=5
    ):
        raise HTTPException(
            status_code=422, detail="Heartbeat timestamp is in the future"
        )
    heartbeat = DeviceHeartbeat(
        id=str(uuid4()),
        device_id=device.id,
        owner_id=owner_id,
        health=payload.health,
        reported_at=payload.reported_at,
        received_at=now,
        metrics=payload.metrics,
    )
    db.add(heartbeat)
    device.last_heartbeat_at = now
    if device.state != DeviceState.DISABLED:
        device.state = (
            DeviceState.WARNING
            if payload.health == DeviceHealth.WARNING
            else DeviceState.ONLINE
        )
    db.commit()
    db.refresh(heartbeat)
    db.refresh(device)
    return HeartbeatResponse(
        **{
            key: value
            for key, value in heartbeat.__dict__.items()
            if not key.startswith("_")
        },
        device_state=device.state,
    )


def list_heartbeats(
    db: Session, owner_id: str, device_id: str
) -> list[DeviceHeartbeat]:
    get_owned_device(db, owner_id, device_id)
    return list(
        db.scalars(
            select(DeviceHeartbeat)
            .where(
                DeviceHeartbeat.device_id == device_id,
                DeviceHeartbeat.owner_id == owner_id,
            )
            .order_by(DeviceHeartbeat.received_at.desc())
            .limit(100)
        )
    )


def remove_device(db: Session, owner_id: str, device_id: str) -> None:
    device = get_owned_device(db, owner_id, device_id)
    now = utc_now()
    device.state = DeviceState.RETIRED
    device.retired_at = device.retired_at or now
    device.removed_at = now
    db.commit()
