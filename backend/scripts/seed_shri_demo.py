"""Create a small, idempotent Shri demo fleet in the configured development databases.

Run from ``backend`` with ``SHRI_DEMO_PASSWORD`` set. The script creates one regular user,
two owned vehicles, their devices and heartbeat history, Bay Area telemetry, and matching
simulation alerts/ML analysis documents. It never changes an existing user's password.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.mongodb import AUDIO_ANALYSIS, TELEMETRY, close_mongo, ensure_indexes, get_mongo_db
from app.db.postgres import dispose_engine, get_sessionmaker
from app.models.alert import Alert, AlertAction
from app.models.common import utcnow
from app.models.device import DeviceHeartbeat
from app.models.user import User
from app.repositories import (
    alert_repository,
    device_repository,
    telemetry_repository,
    user_repository,
    vehicle_repository,
)

DEMO_EMAIL = "shri.demo@example.com"
SEED_TAG = "shri-demo-v1"


@dataclass(frozen=True)
class DemoAlert:
    event_type: str
    severity: str
    confidence: float
    status: str
    location: str
    minutes_ago: int


@dataclass(frozen=True)
class DemoVehicle:
    code: str
    vehicle_type: str
    vin: str
    plate: str
    latitude: float
    longitude: float
    speed: float
    battery: int
    engine_temperature: float
    devices: tuple[tuple[str, str, str], ...]
    alerts: tuple[DemoAlert, ...]


VEHICLES = (
    DemoVehicle(
        code="SHRI-MODEL3",
        vehicle_type="Tesla Model 3",
        vin="5YJ3E1EA7KF317001",
        plate="SHRI-M3",
        latitude=37.3541,
        longitude=-121.9552,
        speed=32.0,
        battery=84,
        engine_temperature=41.0,
        devices=(
            ("SHRI-M3-MIC-01", "microphone", "Model 3 cabin microphone"),
            ("SHRI-M3-GPS-01", "gps", "Model 3 GPS tracker"),
            ("SHRI-M3-GW-01", "gateway", "Model 3 telematics gateway"),
        ),
        alerts=(
            DemoAlert("emergency_vehicle_siren", "medium", 0.88, "open", "Santa Clara", 12),
            DemoAlert("glass_breaking", "high", 0.94, "acknowledged", "Santa Clara", 95),
            DemoAlert("tire_skidding", "high", 0.90, "resolved", "San Jose", 1440),
        ),
    ),
    DemoVehicle(
        code="SHRI-COROLLA",
        vehicle_type="Toyota Corolla",
        vin="JTDBR32E720123456",
        plate="SHRI-COR",
        latitude=37.3382,
        longitude=-121.8863,
        speed=18.0,
        battery=73,
        engine_temperature=87.5,
        devices=(
            ("SHRI-COR-MIC-01", "microphone", "Corolla cabin microphone"),
            ("SHRI-COR-GPS-01", "gps", "Corolla GPS tracker"),
            ("SHRI-COR-IMU-01", "imu", "Corolla motion sensor"),
        ),
        alerts=(
            DemoAlert("screaming", "critical", 0.96, "open", "Downtown San Jose", 7),
            DemoAlert("crash", "critical", 0.98, "acknowledged", "San Jose", 180),
            DemoAlert("abnormal_engine_noise", "medium", 0.85, "resolved", "San Jose", 2880),
        ),
    ),
)


async def _ensure_user(session, password: str):
    user = await user_repository.get_by_email(session, DEMO_EMAIL)
    if user is not None:
        return user, False
    user = await user_repository.create(
        session,
        name="Shri",
        email=DEMO_EMAIL,
        password_hash=hash_password(password),
        role="user",
    )
    await session.commit()
    return user, True


async def _ensure_devices(session, vehicle, owner, spec: DemoVehicle, now):
    created = 0
    devices = []
    for index, (hardware_id, device_type, name) in enumerate(spec.devices):
        device = await device_repository.get_by_hardware_id(session, hardware_id)
        if device is None:
            device = await device_repository.create(
                session,
                vehicle_id=vehicle.id,
                owner_id=owner.id,
                hardware_id=hardware_id,
                device_name=name,
                device_type=device_type,
                manufacturer="AudioGuard Demo",
                model="AG-2026",
                firmware_version="1.0.0-demo",
                status="ACTIVE",
                last_seen_at=now - timedelta(minutes=index + 1),
                online_since=now - timedelta(hours=6),
                battery_level=max(spec.battery - index, 0),
                monitoring_mode="motion_triggered",
                audio_capture_enabled=True,
                configuration={
                    "captureEnabled": True,
                    "monitoringMode": "motion_triggered",
                    "heartbeatIntervalSeconds": 30,
                },
            )
            created += 1
        devices.append(device)
        count = await session.scalar(
            select(func.count()).select_from(DeviceHeartbeat).where(DeviceHeartbeat.device_id == device.id)
        )
        if not count:
            for step in range(3):
                received = now - timedelta(minutes=index + 1 + step * 5)
                await device_repository.add_heartbeat(
                    session,
                    device_id=device.id,
                    received_at=received,
                    heartbeat_status="ok",
                    battery_level=max(spec.battery - index - step, 0),
                    signal_strength=-48.0 - index * 4 - step,
                    firmware_version="1.0.0-demo",
                    latitude=spec.latitude if device_type == "gps" else None,
                    longitude=spec.longitude if device_type == "gps" else None,
                    extra={"source": SEED_TAG},
                )
    return devices, created


async def _ensure_telemetry(mongo, spec: DemoVehicle, primary_device, now) -> int:
    if await mongo[TELEMETRY].count_documents({"vehicle_id": spec.code, "source": SEED_TAG}, limit=1):
        return 0
    for step in range(6):
        timestamp = now - timedelta(minutes=step * 6 + 1)
        await telemetry_repository.insert_telemetry(
            mongo,
            {
                "vehicle_id": spec.code,
                "device_id": str(primary_device.id),
                "hardware_id": primary_device.hardware_id,
                "timestamp": timestamp,
                "location": {
                    "latitude": round(spec.latitude - step * 0.0012, 5),
                    "longitude": round(spec.longitude - step * 0.0014, 5),
                },
                "speed": max(spec.speed - step * 2.5, 0),
                "engine_temperature": round(spec.engine_temperature - step * 0.3, 1),
                "battery_level": max(spec.battery - step, 0),
                "gps_status": "locked",
                "source": SEED_TAG,
            },
        )
    await telemetry_repository.insert_device_log(
        mongo,
        vehicle_code=spec.code,
        event_type="demo_seeded",
        message=f"{spec.vehicle_type} demo telemetry initialized",
        timestamp=now,
        device_id=str(primary_device.id),
        hardware_id=primary_device.hardware_id,
    )
    return 6


async def _ensure_alerts(session, mongo, vehicle, admin, spec: DemoVehicle, now) -> int:
    created = 0
    for item in spec.alerts:
        event_id = str(uuid5(NAMESPACE_URL, f"{SEED_TAG}:{spec.code}:{item.event_type}"))
        existing = await session.scalar(select(Alert).where(Alert.simulation_event_id == event_id))
        detected = now - timedelta(minutes=item.minutes_ago)
        if existing is None:
            reviewed = detected + timedelta(minutes=4) if item.status != "open" else None
            alert = await alert_repository.create(
                session,
                vehicle_id=vehicle.id,
                event_type=item.event_type,
                severity=item.severity,
                confidence=item.confidence,
                status=item.status,
                location=item.location,
                detected_at=detected,
                reviewed_at=reviewed,
                resolved_at=detected + timedelta(minutes=18) if item.status == "resolved" else None,
                is_simulation=True,
                simulation_event_id=event_id,
            )
            await alert_repository.add_action(
                session, alert_id=alert.id, user_id=None, action_type="created", notes="Shri demo data"
            )
            if item.status in {"acknowledged", "resolved"}:
                await alert_repository.add_action(
                    session, alert_id=alert.id, user_id=admin.id, action_type="acknowledged", notes="Demo review"
                )
            if item.status == "resolved":
                await alert_repository.add_action(
                    session, alert_id=alert.id, user_id=admin.id, action_type="resolved", notes="Demo resolved"
                )
            created += 1
        else:
            existing.severity = item.severity
            existing.confidence = item.confidence
            existing.status = item.status
            existing.location = item.location
            existing.detected_at = detected
            existing.reviewed_at = detected + timedelta(minutes=4) if item.status != "open" else None
            existing.resolved_at = detected + timedelta(minutes=18) if item.status == "resolved" else None
            existing.is_simulation = True
            actions = set(
                await session.scalars(select(AlertAction.action_type).where(AlertAction.alert_id == existing.id))
            )
            if item.status in {"acknowledged", "resolved"} and "acknowledged" not in actions:
                await alert_repository.add_action(
                    session,
                    alert_id=existing.id,
                    user_id=admin.id,
                    action_type="acknowledged",
                    notes="Demo review",
                )
            if item.status == "resolved" and "resolved" not in actions:
                await alert_repository.add_action(
                    session,
                    alert_id=existing.id,
                    user_id=admin.id,
                    action_type="resolved",
                    notes="Demo resolved",
                )
        if not await mongo[AUDIO_ANALYSIS].find_one({"event_id": event_id}, {"_id": 1}):
            await mongo[AUDIO_ANALYSIS].insert_one(
                {
                    "event_id": event_id,
                    "vehicle_id": spec.code,
                    "model_name": "audioguard-demo-baseline",
                    "model_version": "demo-1.0",
                    "predicted_class": item.event_type,
                    "confidence": item.confidence,
                    "processing_time_ms": 18,
                    "is_simulation": True,
                    "created_at": detected,
                    "source": SEED_TAG,
                }
            )
    return created


async def main() -> None:
    if settings.environment != "development":
        raise SystemExit("Refusing to seed Shri demo data unless ENVIRONMENT=development")
    password = os.environ.get("SHRI_DEMO_PASSWORD")
    if not password or len(password) < 12:
        raise SystemExit("Set SHRI_DEMO_PASSWORD to at least 12 characters for the demo login")

    mongo = get_mongo_db()
    await ensure_indexes(mongo)
    totals = {"vehicles": 0, "devices": 0, "telemetry": 0, "alerts": 0}
    try:
        async with get_sessionmaker()() as session:
            admin = await user_repository.get_by_email(session, settings.dev_admin_email)
            if admin is None or admin.role != "admin":
                admin = await session.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
            if admin is None or admin.role != "admin":
                raise SystemExit("The development database must contain an administrator")
            user, user_created = await _ensure_user(session, password)
            now = utcnow()
            for spec in VEHICLES:
                vehicle = await vehicle_repository.get_by_ref(session, spec.code)
                if vehicle is None:
                    vehicle = await vehicle_repository.create(
                        session,
                        vehicle_code=spec.code,
                        vehicle_type=spec.vehicle_type,
                        vin=spec.vin,
                        license_plate=spec.plate,
                        status="connected",
                        owner_id=user.id,
                        last_seen_at=now - timedelta(minutes=1),
                    )
                    totals["vehicles"] += 1
                    vehicle = await vehicle_repository.get_by_ref(session, spec.code)
                await vehicle_repository.add_assignment(session, user_id=user.id, vehicle_id=vehicle.id)
                snapshot = vehicle.device_status
                snapshot.microphone_status = "online"
                snapshot.gps_status = "locked"
                snapshot.engine_status = "healthy"
                snapshot.battery_level = spec.battery
                snapshot.monitoring_mode = "motion_triggered"
                snapshot.audio_capture_enabled = True
                snapshot.last_sync_at = now - timedelta(minutes=1)
                snapshot.online_since = snapshot.online_since or now - timedelta(hours=6)
                devices, count = await _ensure_devices(session, vehicle, user, spec, now)
                totals["devices"] += count
                await session.commit()
                totals["telemetry"] += await _ensure_telemetry(mongo, spec, devices[0], now)
                totals["alerts"] += await _ensure_alerts(session, mongo, vehicle, admin, spec, now)
                await session.commit()
        print(f"Shri demo user: {DEMO_EMAIL} ({'created' if user_created else 'already existed'})")
        print(
            "Created this run: "
            f"{totals['vehicles']} vehicles, {totals['devices']} devices, "
            f"{totals['telemetry']} telemetry readings, {totals['alerts']} alerts"
        )
    finally:
        await dispose_engine()
        close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
