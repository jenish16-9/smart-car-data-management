READING = {
    "location": {"latitude": 37.3352, "longitude": -121.8811},
    "speed": 42.5,
    "engine_temperature": 88.4,
    "battery_level": 76,
    "gps_status": "locked",
}


async def test_insert_telemetry(client, admin_headers, vehicle, mongo_db):
    response = await client.post("/telemetry/CAR-1024", json=READING, headers=admin_headers)
    assert response.status_code == 201
    assert response.json()["vehicle_id"] == "CAR-1024" and response.json()["speed"] == 42.5
    assert await mongo_db["telemetry_events"].count_documents({"vehicle_id": "CAR-1024"}) == 1
    assert await mongo_db["sensor_events"].count_documents({"vehicle_id": "CAR-1024"}) == 2


async def test_insert_telemetry_updates_device_status(client, admin_headers, vehicle):
    await client.post("/telemetry/CAR-1024", json=READING, headers=admin_headers)
    device = (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()["device"]
    assert device["battery_level"] == 76 and device["gps_status"] == "locked" and device["engine_status"] == "healthy"


async def test_retrieve_telemetry_history_and_latest(client, admin_headers, vehicle):
    for minute, speed in ((0, 10.0), (5, 20.0), (10, 30.0)):
        stamp = f"2026-11-10T20:{minute:02d}:00Z"
        await client.post(
            "/telemetry/CAR-1024", json={**READING, "speed": speed, "timestamp": stamp}, headers=admin_headers
        )

    history = (await client.get("/telemetry/CAR-1024", headers=admin_headers)).json()
    assert [row["speed"] for row in history] == [30.0, 20.0, 10.0]  # newest first
    latest = (await client.get("/telemetry/CAR-1024/latest", headers=admin_headers)).json()
    assert latest["speed"] == 30.0

    limited = await client.get("/telemetry/CAR-1024", params={"limit": 1}, headers=admin_headers)
    assert len(limited.json()) == 1


async def test_latest_without_data_is_404(client, admin_headers, vehicle):
    assert (await client.get("/telemetry/CAR-1024/latest", headers=admin_headers)).status_code == 404


async def test_telemetry_validation_and_access(client, admin_headers, user_headers, vehicle):
    bad = await client.post(
        "/telemetry/CAR-1024", json={"location": {"latitude": 95, "longitude": 0}}, headers=admin_headers
    )
    assert bad.status_code == 422
    forbidden = await client.post("/telemetry/CAR-1024", json=READING, headers=user_headers)
    assert forbidden.status_code == 404


async def test_first_telemetry_logs_connection(client, admin_headers, mongo_db):
    await client.post("/vehicles", json={"vehicle_code": "CAR-7", "vehicle_type": "Sedan"}, headers=admin_headers)
    await client.post("/telemetry/CAR-7", json={"speed": 1}, headers=admin_headers)
    await client.post("/telemetry/CAR-7", json={"speed": 2}, headers=admin_headers)
    logs = (await client.get("/vehicles/CAR-7/logs", headers=admin_headers)).json()
    assert [entry["event_type"] for entry in logs] == ["connection_established"]


async def test_uptime_starts_with_telemetry_and_clears_when_disconnected(client, admin_headers, vehicle):
    before = (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()
    await client.post("/telemetry/CAR-1024", json={"speed": 5}, headers=admin_headers)
    after = (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()
    assert after["device"]["online_since"] is not None
    patched = await client.patch("/vehicles/CAR-1024", json={"status": "disconnected"}, headers=admin_headers)
    assert patched.json()["device"]["online_since"] is None
    assert before["status"] == "connected"
