"""Pure device lifecycle rules (no database access)."""

from datetime import datetime, timedelta

from app.core.config import settings
from app.core.errors import ConflictError
from app.models.device import Device
from app.models.vehicle import Vehicle

ONLINE_STATUSES = ("ACTIVE", "WARNING")
BLOCKED_STATUSES = ("DISABLED", "RETIRED")  # no control commands
CONTROL_TYPES = ("microphone", "audio_sensor", "gateway", "other")


def default_device(vehicle: Vehicle) -> Device | None:
    """The device used when a caller only knows the vehicle: first non-retired device, online ones first."""
    candidates = [d for d in vehicle.devices if d.status != "RETIRED" and d.is_active]
    if not candidates:
        return None
    candidates.sort(key=lambda d: (d.status not in ONLINE_STATUSES, d.device_type not in CONTROL_TYPES))
    return candidates[0]


def stale_cutoff(now: datetime) -> datetime:
    return now - timedelta(seconds=settings.device_heartbeat_timeout_seconds)


def status_after_heartbeat(current: str, heartbeat_status: str, battery_level: int | None) -> str:
    """DISABLED and RETIRED are never overwritten by heartbeats; PENDING/DELAYED/ACTIVE/WARNING are re-derived."""
    if current in BLOCKED_STATUSES:
        return current
    low_battery = battery_level is not None and battery_level < settings.low_battery_warning_percent
    return "WARNING" if heartbeat_status != "ok" or low_battery else "ACTIVE"


def require_controllable(device: Device) -> None:
    if device.status == "RETIRED":
        raise ConflictError("Device is retired and does not accept commands")
    if device.status == "DISABLED":
        raise ConflictError("Device is disabled; an administrator must re-enable it first")
