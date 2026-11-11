from app.db.seed_demo import DRIVER_EMAIL, SPECS, seed_demo
from app.repositories import user_repository
from tests.conftest import ADMIN_EMAIL

DRIVER_PASSWORD = "driver-test-pass"


async def _seed(sessionmaker, mongo_db):
    async with sessionmaker() as session:
        admin = await user_repository.get_by_email(session, ADMIN_EMAIL)
        return await seed_demo(session, mongo_db, admin, DRIVER_PASSWORD)


async def test_seed_creates_ten_varied_vehicles_and_is_idempotent(client, admin_headers, sessionmaker, mongo_db):
    first = await _seed(sessionmaker, mongo_db)
    assert len(first["created"]) == 10 and first["driver_created"]
    telemetry_count = await mongo_db["telemetry_events"].count_documents({})
    second = await _seed(sessionmaker, mongo_db)
    assert second["created"] == [] and second["driver_created"] is False
    assert await mongo_db["telemetry_events"].count_documents({}) == telemetry_count

    vehicles = (await client.get("/vehicles", headers=admin_headers)).json()
    assert [v["vehicle_code"] for v in vehicles] == [f"CAR-{n}" for n in range(1024, 1034)]
    assert {v["status"] for v in vehicles} == {"connected", "disconnected", "maintenance"}
    assert len({v["device"]["battery_level"] for v in vehicles}) > 5
    by_code = {v["vehicle_code"]: v for v in vehicles}
    assert by_code["CAR-1029"]["device"]["online_since"] is None
    assert by_code["CAR-1026"]["device"]["online_since"] is not None
    assert by_code["CAR-1030"]["device"]["monitoring_mode"] == "paused"


async def test_every_vehicle_has_its_own_telemetry_and_alerts(client, admin_headers, sessionmaker, mongo_db):
    await _seed(sessionmaker, mongo_db)
    for spec in SPECS:
        latest = (await client.get(f"/telemetry/{spec.code}/latest", headers=admin_headers)).json()
        assert latest["vehicle_id"] == spec.code
        assert round(latest["location"]["latitude"], 3) == round(spec.lat, 3)
        alerts = (await client.get("/alerts", params={"vehicle_id": spec.code}, headers=admin_headers)).json()
        assert len(alerts) == len(spec.alerts) and all(a["vehicle_code"] == spec.code for a in alerts)
    assert (await client.get("/alerts", params={"vehicle_id": "CAR-1028"}, headers=admin_headers)).json() == []


async def test_driver_only_sees_assigned_vehicles(client, admin_headers, sessionmaker, mongo_db):
    await _seed(sessionmaker, mongo_db)
    login = await client.post("/auth/login", json={"email": DRIVER_EMAIL, "password": DRIVER_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assigned = [spec.code for spec in SPECS if spec.driver]
    assert [v["vehicle_code"] for v in (await client.get("/vehicles", headers=headers)).json()] == assigned
    assert (await client.get("/vehicles/CAR-1031", headers=headers)).status_code == 404
    visible = {a["vehicle_code"] for a in (await client.get("/alerts", headers=headers)).json()}
    assert visible == {"CAR-1027", "CAR-1029"}


async def test_seed_creates_devices_with_every_lifecycle_status_and_is_idempotent(
    client, admin_headers, sessionmaker, mongo_db
):
    from sqlalchemy import func, select

    from app.models.device import Device, DeviceHeartbeat

    async def counts():
        async with sessionmaker() as session:
            return [
                (await session.execute(select(func.count()).select_from(model))).scalar_one()
                for model in (Device, DeviceHeartbeat)
            ]

    await _seed(sessionmaker, mongo_db)
    first = await counts()
    await _seed(sessionmaker, mongo_db)
    assert await counts() == first  # no duplicate devices or heartbeats

    devices = (await client.get("/devices?include_retired=true&limit=500", headers=admin_headers)).json()
    assert len({d["hardware_id"] for d in devices}) == len(devices)
    assert {d["status"] for d in devices} == {"PENDING", "ACTIVE", "WARNING", "DELAYED", "DISABLED", "RETIRED"}
    assert len([d for d in devices if d["vehicle_code"] == "CAR-1024"]) == 3
    assert {d["device_type"] for d in devices} >= {"microphone", "gps", "imu", "camera", "gateway", "audio_sensor"}

    car = (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()
    assert len(car["devices"]) == 3 and car["default_device_id"]
    beats = await client.get(f"/devices/{car['default_device_id']}/heartbeats", headers=admin_headers)
    assert len(beats.json()) == 5
