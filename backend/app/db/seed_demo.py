"""Demo data: ten vehicles with varied statuses, locations, device states, telemetry and alerts.

Idempotent and development-only:  python -m app.db.seed_demo

- Vehicles that already exist are kept as they are (their existing data is never overwritten);
  telemetry and alerts are only added to vehicles that have none.
- Vehicles are owned by the administrator; some are also assigned to a demo "driver" user so
  the access-control rules can be tried (that user is created with a random password, printed once).
"""

import asyncio
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.mongodb import TELEMETRY, close_mongo, ensure_indexes, get_mongo_db
from app.db.postgres import dispose_engine, get_sessionmaker
from app.models.alert import Alert
from app.models.common import utcnow
from app.models.user import User
from app.repositories import alert_repository, telemetry_repository, user_repository, vehicle_repository

logger = logging.getLogger(__name__)

DRIVER_EMAIL = "driver@example.com"


@dataclass(frozen=True)
class AlertSpec:
    event_type: str
    severity: str
    confidence: float
    location: str
    status: str  # open | acknowledged | resolved
    minutes_ago: int


@dataclass(frozen=True)
class VehicleSpec:
    code: str
    vehicle_type: str
    status: str  # connected | disconnected | maintenance
    lat: float
    lng: float
    speed: float
    engine_temp: float
    battery: int
    gps: str
    engine: str
    microphone: str
    mode: str
    capture: bool
    last_seen_minutes: int
    uptime_hours: float | None  # None when not connected
    drifting: bool = False  # moving vehicles get a short track
    driver: bool = False  # also assigned to the demo driver
    alerts: tuple[AlertSpec, ...] = field(default_factory=tuple)


SPECS: tuple[VehicleSpec, ...] = (
    VehicleSpec(
        "CAR-1024",
        "Sedan",
        "connected",
        37.3352,
        -121.8811,
        42.5,
        88.4,
        76,
        "locked",
        "healthy",
        "online",
        "continuous",
        True,
        2,
        54.0,
        drifting=True,
        driver=True,
    ),
    VehicleSpec(
        "CAR-1025",
        "SUV",
        "connected",
        37.30,
        -121.95,
        0.0,
        74.0,
        90,
        "locked",
        "healthy",
        "online",
        "continuous",
        True,
        3,
        28.0,
        driver=True,
    ),
    VehicleSpec(
        "CAR-1026",
        "Sedan",
        "connected",
        37.4323,
        -121.8996,
        0.0,
        72.1,
        88,
        "locked",
        "healthy",
        "online",
        "continuous",
        True,
        1,
        123.5,
        driver=True,
    ),
    VehicleSpec(
        "CAR-1027",
        "SUV",
        "connected",
        37.3688,
        -122.0363,
        63.5,
        91.2,
        71,
        "locked",
        "healthy",
        "online",
        "motion_triggered",
        True,
        1,
        6.25,
        drifting=True,
        driver=True,
        alerts=(AlertSpec("engine_noise", "medium", 0.86, "Engine Bay", "open", 18),),
    ),
    VehicleSpec(
        "CAR-1028",
        "Truck",
        "connected",
        37.4419,
        -122.1430,
        0.0,
        69.5,
        93,
        "locked",
        "healthy",
        "online",
        "continuous",
        True,
        4,
        12.0,
        driver=True,
    ),
    VehicleSpec(
        "CAR-1029",
        "Van",
        "disconnected",
        37.5485,
        -121.9886,
        0.0,
        0.0,
        12,
        "no_signal",
        "unknown",
        "offline",
        "continuous",
        True,
        4320,
        None,
        driver=True,
        alerts=(AlertSpec("horn", "low", 0.82, "Front", "resolved", 4500),),
    ),
    VehicleSpec(
        "CAR-1030",
        "Sedan",
        "maintenance",
        37.4852,
        -122.2364,
        0.0,
        112.0,
        54,
        "locked",
        "warning",
        "offline",
        "paused",
        False,
        95,
        None,
        alerts=(AlertSpec("engine_noise", "high", 0.91, "Engine Bay", "acknowledged", 240),),
    ),
    VehicleSpec(
        "CAR-1031",
        "SUV",
        "connected",
        37.7749,
        -122.4194,
        48.0,
        86.3,
        82,
        "locked",
        "healthy",
        "online",
        "continuous",
        True,
        2,
        31.0,
        drifting=True,
        alerts=(AlertSpec("glass_break", "high", 0.93, "Rear Left", "open", 35),),
    ),
    VehicleSpec(
        "CAR-1032",
        "Hatchback",
        "connected",
        37.8044,
        -122.2712,
        71.2,
        95.6,
        64,
        "locked",
        "healthy",
        "online",
        "continuous",
        True,
        1,
        2.5,
        drifting=True,
        alerts=(AlertSpec("crash", "critical", 0.97, "Front Left", "open", 9),),
    ),
    VehicleSpec(
        "CAR-1033",
        "Coupe",
        "disconnected",
        37.2972,
        -121.8300,
        0.0,
        0.0,
        8,
        "no_signal",
        "unknown",
        "offline",
        "continuous",
        True,
        360,
        None,
    ),
)


async def _count_alerts(session: AsyncSession, vehicle_id) -> int:
    return int(
        (
            await session.execute(select(func.count()).select_from(Alert).where(Alert.vehicle_id == vehicle_id))
        ).scalar_one()
    )


async def _ensure_driver(session: AsyncSession) -> tuple[User, str | None]:
    existing = await user_repository.get_by_email(session, DRIVER_EMAIL)
    if existing:
        return existing, None
    password = secrets.token_urlsafe(9)
    driver = await user_repository.create(
        session, name="Demo Driver", email=DRIVER_EMAIL, password_hash=hash_password(password), role="user"
    )
    await session.commit()
    return driver, password


async def _seed_telemetry(mongo: AsyncIOMotorDatabase, spec: VehicleSpec, now: datetime) -> None:
    if await mongo[TELEMETRY].count_documents({"vehicle_id": spec.code}, limit=1):
        return
    readings = 4 if spec.status == "connected" else 1
    for step in range(readings):
        at = now - timedelta(minutes=spec.last_seen_minutes + step * 5)
        back = step * (0.004 if spec.drifting else 0.0)  # moving vehicles trail behind their latest fix
        document = {
            "vehicle_id": spec.code,
            "timestamp": at,
            "location": {"latitude": round(spec.lat - back, 5), "longitude": round(spec.lng - back * 1.3, 5)},
            "speed": spec.speed,
            "battery_level": spec.battery,
            "gps_status": spec.gps if spec.status == "connected" else "lost",
        }
        if spec.status != "disconnected":
            document["engine_temperature"] = round(spec.engine_temp - step * 0.4, 1)
        await telemetry_repository.insert_telemetry(mongo, document)
        sensors = [
            {
                "vehicle_id": spec.code,
                "sensor_type": "battery_level",
                "value": float(spec.battery),
                "unit": "percent",
                "timestamp": at,
            }
        ]
        if "engine_temperature" in document:
            sensors.append(
                {
                    "vehicle_id": spec.code,
                    "sensor_type": "engine_temperature",
                    "value": document["engine_temperature"],
                    "unit": "celsius",
                    "timestamp": at,
                }
            )
        await telemetry_repository.insert_sensor_events(mongo, sensors)

    last_seen = now - timedelta(minutes=spec.last_seen_minutes)
    if spec.status == "connected" and spec.uptime_hours is not None:
        logs = [("connection_established", "Vehicle connected to server", now - timedelta(hours=spec.uptime_hours))]
    elif spec.status == "maintenance":
        logs = [
            ("monitoring_mode_changed", "Mode set to Paused", last_seen),
            ("maintenance_started", "Vehicle checked in for maintenance", last_seen),
        ]
    else:
        logs = [("connection_lost", "Vehicle lost connection to server", last_seen)]
    for event_type, message, at in logs:
        await telemetry_repository.insert_device_log(
            mongo, vehicle_code=spec.code, event_type=event_type, message=message, timestamp=at
        )


async def _seed_alerts(session: AsyncSession, spec: VehicleSpec, vehicle, admin: User, now: datetime) -> None:
    if await _count_alerts(session, vehicle.id):
        return
    for item in spec.alerts:
        detected = now - timedelta(minutes=item.minutes_ago)
        alert = await alert_repository.create(
            session,
            vehicle_id=vehicle.id,
            event_type=item.event_type,
            severity=item.severity,
            confidence=item.confidence,
            status=item.status,
            location=item.location,
            detected_at=detected,
            reviewed_at=None if item.status == "open" else detected + timedelta(minutes=5),
            resolved_at=detected + timedelta(minutes=30) if item.status == "resolved" else None,
        )
        await alert_repository.add_action(
            session, alert_id=alert.id, user_id=None, action_type="created", notes="Demo data"
        )
        if item.status in ("acknowledged", "resolved"):
            await alert_repository.add_action(
                session, alert_id=alert.id, user_id=admin.id, action_type="acknowledged", notes=None
            )
        if item.status == "resolved":
            await alert_repository.add_action(
                session, alert_id=alert.id, user_id=admin.id, action_type="resolved", notes=None
            )


async def seed_demo(session: AsyncSession, mongo: AsyncIOMotorDatabase, admin: User) -> dict[str, object]:
    """Create/complete the demo vehicles. Returns a small report."""
    now = utcnow()
    driver, driver_password = await _ensure_driver(session)
    created: list[str] = []
    for spec in SPECS:
        vehicle = await vehicle_repository.get_by_ref(session, spec.code)
        if vehicle is None:
            vehicle = await vehicle_repository.create(
                session,
                vehicle_code=spec.code,
                vehicle_type=spec.vehicle_type,
                status=spec.status,
                owner_id=admin.id,
                last_seen_at=now - timedelta(minutes=spec.last_seen_minutes),
            )
            vehicle = await vehicle_repository.get_by_ref(session, spec.code)
            device = vehicle.device_status
            device.microphone_status, device.gps_status, device.engine_status = spec.microphone, spec.gps, spec.engine
            device.battery_level = spec.battery
            device.monitoring_mode, device.audio_capture_enabled, device.recording = spec.mode, spec.capture, False
            device.last_sync_at = now - timedelta(minutes=spec.last_seen_minutes)
            created.append(spec.code)
        device = vehicle.device_status
        if device is not None and device.online_since is None and vehicle.status == "connected" and spec.uptime_hours:
            device.online_since = now - timedelta(hours=spec.uptime_hours)
        await vehicle_repository.add_assignment(session, user_id=admin.id, vehicle_id=vehicle.id)
        if spec.driver:
            await vehicle_repository.add_assignment(session, user_id=driver.id, vehicle_id=vehicle.id)
        await session.commit()
        await _seed_telemetry(mongo, spec, now)
        await _seed_alerts(session, spec, vehicle, admin, now)
        await session.commit()
    return {"created": created, "driver_email": DRIVER_EMAIL, "driver_password": driver_password}


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    if settings.environment != "development":
        raise SystemExit("Refusing to seed demo data unless ENVIRONMENT=development")
    mongo = get_mongo_db()
    await ensure_indexes(mongo)
    try:
        async with get_sessionmaker()() as session:
            admin = (
                await user_repository.get_by_email(session, settings.dev_admin_email)
                if settings.dev_admin_email
                else None
            )
            if admin is None:
                raise SystemExit(
                    "No administrator found. Set DEV_ADMIN_EMAIL/DEV_ADMIN_PASSWORD and start the API once."
                )
            report = await seed_demo(session, mongo, admin)
        print(f"Vehicles created: {report['created'] or 'none (all already existed)'}")
        if report["driver_password"]:
            print(f"Demo driver created: {report['driver_email']} / {report['driver_password']}  (shown once)")
        else:
            print(f"Demo driver already exists: {report['driver_email']}")
    finally:
        await dispose_engine()
        close_mongo()


if __name__ == "__main__":
    asyncio.run(_main())
