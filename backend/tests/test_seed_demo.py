from app.db.seed_demo import DRIVER_EMAIL, SPECS, seed_demo
from app.repositories import user_repository
from tests.conftest import ADMIN_EMAIL


async def _seed(sessionmaker, mongo_db):
    async with sessionmaker() as session:
        admin = await user_repository.get_by_email(session, ADMIN_EMAIL)
        return await seed_demo(session, mongo_db, admin)


async def test_seed_creates_ten_varied_vehicles_and_is_idempotent(client, admin_headers, sessionmaker, mongo_db):
    first = await _seed(sessionmaker, mongo_db)
    assert len(first["created"]) == 10 and first["driver_password"]
    telemetry_count = await mongo_db["telemetry_events"].count_documents({})
    second = await _seed(sessionmaker, mongo_db)
    assert second["created"] == [] and second["driver_password"] is None
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
    report = await _seed(sessionmaker, mongo_db)
    login = await client.post("/auth/login", json={"email": DRIVER_EMAIL, "password": report["driver_password"]})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assigned = [spec.code for spec in SPECS if spec.driver]
    assert [v["vehicle_code"] for v in (await client.get("/vehicles", headers=headers)).json()] == assigned
    assert (await client.get("/vehicles/CAR-1031", headers=headers)).status_code == 404
    visible = {a["vehicle_code"] for a in (await client.get("/alerts", headers=headers)).json()}
    assert visible == {"CAR-1027", "CAR-1029"}
