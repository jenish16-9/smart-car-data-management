from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.common import utcnow
from app.models.device import Device
from app.models.user import User
from app.models.vehicle import Vehicle
from app.repositories import telemetry_repository, user_repository, vehicle_repository
from app.schemas.device import DeviceControlsUpdate
from app.schemas.vehicle import DeviceLogOut, VehicleControlsUpdate, VehicleCreate, VehicleUpdate
from app.services.device_rules import default_device, require_controllable


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise ForbiddenError("Administrator access required")


async def get_accessible(session: AsyncSession, user: User, ref: str) -> Vehicle:
    """Return the vehicle, or 404 if it does not exist or the user may not see it."""
    vehicle = await vehicle_repository.get_by_ref(session, ref)
    if vehicle is None or not vehicle.is_active or not await vehicle_repository.user_can_access(session, user, vehicle):
        raise NotFoundError("Vehicle not found")
    await _refresh_registered_devices(session, vehicle)
    return vehicle


async def _refresh_registered_devices(session: AsyncSession, vehicle: Vehicle) -> None:
    from app.services import device_service

    await device_service.refresh_stale(session)


async def _require_unique_identifiers(
    session: AsyncSession, *, vin: str | None, license_plate: str | None, exclude_id=None
) -> None:
    if vin:
        existing = await vehicle_repository.get_by_vin(session, vin)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("A vehicle with this VIN already exists")
    if license_plate:
        existing = await vehicle_repository.get_by_license_plate(session, license_plate)
        if existing is not None and existing.id != exclude_id:
            raise ConflictError("A vehicle with this license plate already exists")


async def _require_user(session: AsyncSession, user_id) -> None:
    if await user_repository.get_by_id(session, user_id) is None:
        raise NotFoundError(f"User {user_id} not found")


async def create_vehicle(session: AsyncSession, user: User, payload: VehicleCreate) -> Vehicle:
    _require_admin(user)
    if await vehicle_repository.get_by_ref(session, payload.vehicle_code):
        raise ConflictError(f"Vehicle {payload.vehicle_code} already exists (it may be deactivated)")
    await _require_unique_identifiers(session, vin=payload.vin, license_plate=payload.license_plate)

    owner_id = payload.owner_id or user.id
    if owner_id != user.id:
        await _require_user(session, owner_id)
    for assigned_id in payload.assigned_user_ids:
        await _require_user(session, assigned_id)

    vehicle = await vehicle_repository.create(
        session,
        vehicle_code=payload.vehicle_code,
        vehicle_type=payload.vehicle_type,
        vin=payload.vin,
        license_plate=payload.license_plate,
        status=payload.status,
        owner_id=owner_id,
    )
    for assigned_id in {owner_id, *payload.assigned_user_ids}:
        await vehicle_repository.add_assignment(session, user_id=assigned_id, vehicle_id=vehicle.id)
    await session.commit()
    return await get_accessible(session, user, str(vehicle.id))


async def list_vehicles(
    session: AsyncSession, user: User, *, limit: int, offset: int, include_inactive: bool = False
) -> list[Vehicle]:
    if include_inactive and user.role != "admin":
        raise ForbiddenError("Only administrators can list deactivated vehicles")
    vehicles = await vehicle_repository.list_for_user(
        session, user, limit=limit, offset=offset, include_inactive=include_inactive
    )
    if vehicles:
        await _refresh_registered_devices(session, vehicles[0])
    return vehicles


async def _require_manage(user: User, vehicle: Vehicle) -> None:
    _require_admin(user)


async def update_vehicle(session: AsyncSession, user: User, ref: str, payload: VehicleUpdate) -> Vehicle:
    vehicle = await get_accessible(session, user, ref)
    await _require_manage(user, vehicle)
    fields = payload.model_dump(exclude_unset=True)
    await _require_unique_identifiers(
        session,
        vin=fields.get("vin", vehicle.vin),
        license_plate=fields.get("license_plate", vehicle.license_plate),
        exclude_id=vehicle.id,
    )
    if "owner_id" in fields:
        if user.role != "admin":
            raise ForbiddenError("Only administrators can change the vehicle owner")
        if fields["owner_id"] is not None:
            await _require_user(session, fields["owner_id"])
    if fields.get("status", vehicle.status) != "connected":
        for target in (vehicle.device_status, *vehicle.devices):
            if target is not None:
                target.online_since = None  # uptime only counts while connected
    await vehicle_repository.update(session, vehicle, **fields)
    await session.commit()
    return await get_accessible(session, user, str(vehicle.id))


async def deactivate_vehicle(session: AsyncSession, user: User, ref: str) -> None:
    vehicle = await get_accessible(session, user, ref)
    await _require_manage(user, vehicle)
    await vehicle_repository.deactivate(session, vehicle, at=utcnow())  # soft delete: nothing is removed
    await session.commit()


_MODE_LABELS = {"continuous": "Continuous", "motion_triggered": "Motion Triggered", "paused": "Paused"}


def control_changes(device, payload: VehicleControlsUpdate | DeviceControlsUpdate) -> list[tuple[str, str, str]]:
    """Apply the requested control values to `device`; return (field, event_type, message) per change."""
    changes: list[tuple[str, str, str]] = []
    requested = payload.model_dump(exclude_none=True)
    if requested.get("monitoring_mode") == "paused":
        requested.setdefault("recording", False)  # pausing monitoring also stops recording
    if requested.get("recording") and not requested.get("audio_capture_enabled", device.audio_capture_enabled):
        raise ConflictError("Enable audio capture before starting a recording")
    if requested.get("recording") and requested.get("monitoring_mode", device.monitoring_mode) == "paused":
        raise ConflictError("Resume monitoring before starting a recording")
    if requested.get("audio_capture_enabled") is False:
        requested.setdefault("recording", False)

    if "monitoring_mode" in requested and requested["monitoring_mode"] != device.monitoring_mode:
        mode = requested["monitoring_mode"]
        changes.append(("monitoring_mode", "monitoring_mode_changed", f"Mode set to {_MODE_LABELS[mode]}"))
    if "audio_capture_enabled" in requested and requested["audio_capture_enabled"] != device.audio_capture_enabled:
        on = requested["audio_capture_enabled"]
        changes.append(
            (
                "audio_capture_enabled",
                "audio_capture_toggled",
                "Audio capture enabled" if on else "Audio capture disabled",
            )
        )
    if "recording" in requested and requested["recording"] != device.recording:
        on = requested["recording"]
        changes.append(
            (
                "recording",
                "recording_started" if on else "recording_stopped",
                "Recording started" if on else "Recording stopped",
            )
        )
    for field, _event, _message in changes:
        setattr(device, field, requested[field])
    return changes


async def update_controls(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, ref: str, payload: VehicleControlsUpdate
) -> Vehicle:
    _require_admin(user)
    vehicle = await get_accessible(session, user, ref)
    # Controls belong to a device; vehicle-level calls act on the vehicle's default device
    # (or on the legacy device_status row for vehicles that have no registered device).
    target = default_device(vehicle) or vehicle.device_status
    if isinstance(target, Device):
        require_controllable(target)
    changes = control_changes(target, payload)
    await session.commit()
    for _field, event_type, message in changes:
        await telemetry_repository.insert_device_log(
            mongo,
            vehicle_code=vehicle.vehicle_code,
            event_type=event_type,
            message=message,
            timestamp=utcnow(),
            device_id=str(target.id) if isinstance(target, Device) else None,
            hardware_id=target.hardware_id if isinstance(target, Device) else None,
        )
    return await get_accessible(session, user, str(vehicle.id))


async def device_logs(
    session: AsyncSession, mongo: AsyncIOMotorDatabase, user: User, ref: str, limit: int
) -> list[DeviceLogOut]:
    vehicle = await get_accessible(session, user, ref)
    documents = await telemetry_repository.list_device_logs(mongo, vehicle.vehicle_code, limit)
    return [DeviceLogOut(**doc) for doc in documents]
