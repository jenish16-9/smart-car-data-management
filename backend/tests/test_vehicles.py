async def test_create_and_retrieve_vehicle(client, admin_headers):
    created = await client.post(
        "/vehicles", json={"vehicle_code": "CAR-2000", "vehicle_type": "SUV"}, headers=admin_headers
    )
    assert created.status_code == 201
    body = created.json()
    assert body["vehicle_code"] == "CAR-2000" and body["device"] is not None

    by_code = await client.get("/vehicles/CAR-2000", headers=admin_headers)
    by_id = await client.get(f"/vehicles/{body['id']}", headers=admin_headers)
    assert by_code.status_code == by_id.status_code == 200
    assert by_code.json()["id"] == by_id.json()["id"] == body["id"]

    listing = await client.get("/vehicles", headers=admin_headers)
    assert [v["vehicle_code"] for v in listing.json()] == ["CAR-2000"]


async def test_duplicate_vehicle_code_conflicts(client, admin_headers, vehicle):
    response = await client.post(
        "/vehicles", json={"vehicle_code": "CAR-1024", "vehicle_type": "Sedan"}, headers=admin_headers
    )
    assert response.status_code == 409


async def test_unknown_vehicle_is_404(client, admin_headers):
    assert (await client.get("/vehicles/CAR-9999", headers=admin_headers)).status_code == 404


async def test_update_and_delete_vehicle(client, admin_headers, vehicle):
    patched = await client.patch("/vehicles/CAR-1024", json={"status": "maintenance"}, headers=admin_headers)
    assert patched.status_code == 200 and patched.json()["status"] == "maintenance"
    assert (await client.delete("/vehicles/CAR-1024", headers=admin_headers)).status_code == 204
    assert (await client.get("/vehicles/CAR-1024", headers=admin_headers)).status_code == 404


async def test_users_only_see_their_assigned_vehicles(client, admin_headers, user_headers):
    me = (await client.get("/users/me", headers=user_headers)).json()
    await client.post(
        "/vehicles",
        json={"vehicle_code": "CAR-A", "vehicle_type": "Sedan", "assigned_user_ids": [me["id"]]},
        headers=admin_headers,
    )
    await client.post("/vehicles", json={"vehicle_code": "CAR-B", "vehicle_type": "SUV"}, headers=admin_headers)

    visible = await client.get("/vehicles", headers=user_headers)
    assert [v["vehicle_code"] for v in visible.json()] == ["CAR-A"]
    assert (await client.get("/vehicles/CAR-B", headers=user_headers)).status_code == 404
    assert len((await client.get("/vehicles", headers=admin_headers)).json()) == 2


async def test_regular_user_cannot_assign_others(client, user_headers):
    response = await client.post(
        "/vehicles",
        json={
            "vehicle_code": "CAR-C",
            "vehicle_type": "Sedan",
            "assigned_user_ids": ["00000000-0000-0000-0000-000000000001"],
        },
        headers=user_headers,
    )
    assert response.status_code == 403


async def test_delete_vehicle_is_a_soft_delete_that_keeps_history(client, admin_headers, vehicle, sessionmaker):
    from sqlalchemy import func, select

    from app.models.alert import Alert
    from app.models.audio import AudioRecord
    from app.models.vehicle import Vehicle

    alert = {"vehicle_id": "CAR-1024", "event_type": "horn", "severity": "low", "confidence": 0.9}
    await client.post("/alerts", json=alert, headers=admin_headers)
    audio = {
        "vehicle_id": "CAR-1024",
        "storage_url": "https://s.example.com/a.wav",
        "file_name": "a.wav",
        "file_type": "audio/wav",
    }
    await client.post("/audio", json=audio, headers=admin_headers)

    assert (await client.delete("/vehicles/CAR-1024", headers=admin_headers)).status_code == 204

    # Hidden from the normal API...
    assert (await client.get("/vehicles/CAR-1024", headers=admin_headers)).status_code == 404
    assert (await client.get("/vehicles", headers=admin_headers)).json() == []
    assert (await client.get("/alerts", headers=admin_headers)).json() == []
    assert (await client.get("/audio", headers=admin_headers)).json() == []
    # ...but nothing was deleted.
    async with sessionmaker() as session:
        assert (await session.execute(select(func.count()).select_from(Alert))).scalar_one() == 1
        assert (await session.execute(select(func.count()).select_from(AudioRecord))).scalar_one() == 1
        row = (await session.execute(select(Vehicle))).scalar_one()
        assert row.is_active is False and row.deleted_at is not None
    # Admins can still list it explicitly; the code stays reserved.
    inactive = (await client.get("/vehicles?include_inactive=true", headers=admin_headers)).json()
    assert [v["vehicle_code"] for v in inactive] == ["CAR-1024"] and inactive[0]["is_active"] is False
    again = {"vehicle_code": "CAR-1024", "vehicle_type": "Sedan"}
    assert (await client.post("/vehicles", json=again, headers=admin_headers)).status_code == 409


async def test_device_controls_update_and_are_logged(client, admin_headers, vehicle):
    device = (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()["device"]
    assert (device["monitoring_mode"], device["audio_capture_enabled"], device["recording"]) == (
        "continuous",
        True,
        False,
    )

    started = await client.patch("/vehicles/CAR-1024/controls", json={"recording": True}, headers=admin_headers)
    assert started.json()["device"]["recording"] is True
    paused = await client.patch(
        "/vehicles/CAR-1024/controls", json={"monitoring_mode": "paused"}, headers=admin_headers
    )
    assert paused.json()["device"]["monitoring_mode"] == "paused" and paused.json()["device"]["recording"] is False

    logs = (await client.get("/vehicles/CAR-1024/logs", headers=admin_headers)).json()
    events = [entry["event_type"] for entry in logs]
    assert set(events) == {"recording_started", "monitoring_mode_changed", "recording_stopped"}
    assert events[-1] == "recording_started"  # oldest last


async def test_device_control_conflicts_and_access(client, admin_headers, user_headers, vehicle):
    await client.patch("/vehicles/CAR-1024/controls", json={"audio_capture_enabled": False}, headers=admin_headers)
    conflict = await client.patch("/vehicles/CAR-1024/controls", json={"recording": True}, headers=admin_headers)
    assert conflict.status_code == 409
    assert (
        await client.patch("/vehicles/CAR-1024/controls", json={"recording": False}, headers=user_headers)
    ).status_code == 404
    assert (
        await client.patch("/vehicles/CAR-1024/controls", json={"monitoring_mode": "bogus"}, headers=admin_headers)
    ).status_code == 422
