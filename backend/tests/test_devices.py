"""Devices: registration, lifecycle, device-level controls, heartbeats, soft removal, access scoping."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.models.common import utcnow
from app.models.device import Device, DeviceHeartbeat
from app.models.vehicle import Vehicle


async def register(client, headers, hardware_id="MIC-0001", vehicle="CAR-1024", **extra):
    body = {"vehicle_id": vehicle, "hardware_id": hardware_id, "device_type": "microphone", **extra}
    return await client.post("/devices", json=body, headers=headers)


async def beat(client, device, key=None, headers=None, **extra):
    body = {"hardware_id": device["hardware_id"], **extra}
    send = {"X-Device-Key": key} if key else headers
    return await client.post(f"/devices/{device['id']}/heartbeat", json=body, headers=send)


@pytest.fixture
async def device(client, admin_headers, vehicle) -> dict:
    response = await register(client, admin_headers, device_name="Cabin mic", manufacturer="Acme", model="M1")
    assert response.status_code == 201, response.text
    return response.json()


# --- registration -----------------------------------------------------------------------------------------------
async def test_register_device_starts_pending_and_returns_key_once(client, admin_headers, device):
    assert device["status"] == "PENDING" and device["vehicle_code"] == "CAR-1024"
    assert device["device_key"].startswith("dk_") and device["online"] is False
    fetched = (await client.get(f"/devices/{device['id']}", headers=admin_headers)).json()
    assert "device_key" not in fetched and fetched["hardware_id"] == "MIC-0001"


async def test_duplicate_hardware_id_is_rejected(client, admin_headers, device):
    assert (await register(client, admin_headers)).status_code == 409


async def test_register_validates_input_and_vehicle(client, admin_headers, vehicle):
    assert (await register(client, admin_headers, hardware_id="x")).status_code == 422
    assert (await register(client, admin_headers, hardware_id="OK-1234", vehicle="CAR-NOPE")).status_code == 404
    bad = {"vehicle_id": "CAR-1024", "hardware_id": "OK-12345", "device_type": "toaster"}
    assert (await client.post("/devices", json=bad, headers=admin_headers)).status_code == 422


async def test_register_requires_authentication_and_admin(client, user_headers, vehicle):
    body = {"vehicle_id": "CAR-1024", "hardware_id": "MIC-9999", "device_type": "gps"}
    assert (await client.post("/devices", json=body)).status_code == 401
    assert (await client.post("/devices", json=body, headers=user_headers)).status_code in (403, 404)


async def test_vehicle_scoped_registration_is_admin_only(client, admin_headers, user_headers):
    owner = (await client.get("/users/me", headers=user_headers)).json()
    owned = await client.post(
        "/vehicles",
        json={"vehicle_code": "CAR-OWNER", "vehicle_type": "Sedan", "owner_id": owner["id"]},
        headers=admin_headers,
    )
    assert owned.status_code == 201
    body = {"hardware_id": "NESTED-0001", "device_type": "microphone"}
    endpoint = f"/vehicles/{owned.json()['id']}/devices"
    assert (await client.post(endpoint, json=body)).status_code == 401
    denied = await client.post(endpoint, json=body, headers=user_headers)
    assert denied.status_code == 403
    created = await client.post(endpoint, json=body, headers=admin_headers)
    assert created.status_code == 201
    assert created.json()["configuration"]["monitoringMode"] == "motion_triggered"


# --- multiple devices per vehicle, listing, filters ---------------------------------------------------------------
async def test_vehicle_supports_multiple_devices_and_filters(client, admin_headers, vehicle):
    await register(client, admin_headers, "MIC-0001")
    gps = await client.post(
        "/devices",
        json={"vehicle_id": "CAR-1024", "hardware_id": "GPS-0001", "device_type": "gps"},
        headers=admin_headers,
    )
    assert gps.status_code == 201
    detail = (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()
    assert {d["hardware_id"] for d in detail["devices"]} == {"MIC-0001", "GPS-0001"}
    assert detail["default_device_id"] is not None and detail["vehicle_type"] == "Sedan"

    assert len((await client.get("/devices", headers=admin_headers)).json()) == 2
    by_vehicle = await client.get("/devices?vehicle_id=CAR-1024", headers=admin_headers)
    assert len(by_vehicle.json()) == 2
    assert (await client.get("/devices?status=ACTIVE", headers=admin_headers)).json() == []
    assert len((await client.get("/devices?status=PENDING", headers=admin_headers)).json()) == 2
    assert (await client.get("/devices?vehicle_id=CAR-NOPE", headers=admin_headers)).status_code == 404


async def test_users_only_see_devices_of_their_vehicles(client, admin_headers, user_headers, vehicle):
    me = (await client.get("/users/me", headers=user_headers)).json()
    await client.post(
        "/vehicles",
        json={"vehicle_code": "CAR-MINE", "vehicle_type": "SUV", "assigned_user_ids": [me["id"]]},
        headers=admin_headers,
    )
    other = await register(client, admin_headers, "MIC-OTHER", "CAR-1024")
    mine = await register(client, admin_headers, "MIC-MINE", "CAR-MINE")
    listed = (await client.get("/devices", headers=user_headers)).json()
    assert [d["hardware_id"] for d in listed] == ["MIC-MINE"]
    assert (await client.get(f"/devices/{mine.json()['id']}", headers=user_headers)).status_code == 200
    assert (await client.get(f"/devices/{other.json()['id']}", headers=user_headers)).status_code == 404
    patch = await client.patch(f"/devices/{mine.json()['id']}", json={"device_name": "x"}, headers=user_headers)
    assert patch.status_code == 403
    assert (await client.delete(f"/devices/{mine.json()['id']}", headers=user_headers)).status_code == 403
    assert (await beat(client, mine.json(), headers=user_headers)).status_code == 403
    assert (
        await client.post(
            f"/devices/{mine.json()['id']}/classify-audio",
            files={"audio": ("demo.wav", b"RIFF0000WAVE", "audio/wav")},
            headers=user_headers,
        )
    ).status_code == 403


# --- heartbeats ---------------------------------------------------------------------------------------------------
async def test_heartbeat_activates_device_and_keeps_history(client, admin_headers, device):
    key = device["device_key"]
    first = await beat(client, device, key=key, battery_level=80, signal_strength=-60, metadata={"temp": 41})
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "ACTIVE" and body["online"] is True and body["last_seen_at"] is not None
    assert body["latest_heartbeat"]["battery_level"] == 80 and body["online_since"] is not None
    await beat(client, device, key=key, battery_level=79, latitude=37.3, longitude=-121.9)
    history = (await client.get(f"/devices/{device['id']}/heartbeats", headers=admin_headers)).json()
    assert len(history) == 2 and history[0]["latitude"] == 37.3  # newest first
    limited = (await client.get(f"/devices/{device['id']}/heartbeats?limit=1&offset=1", headers=admin_headers)).json()
    assert len(limited) == 1 and limited[0]["metadata"] == {"temp": 41}
    future = (utcnow() + timedelta(hours=1)).isoformat()
    after = await client.get(f"/devices/{device['id']}/heartbeats", params={"start": future}, headers=admin_headers)
    assert after.json() == []


async def test_heartbeat_identity_checks(client, admin_headers, device):
    assert (await beat(client, device, key="dk_wrong")).status_code == 403
    mismatch = await client.post(
        f"/devices/{device['id']}/heartbeat",
        json={"hardware_id": "SOMETHING-ELSE"},
        headers={"X-Device-Key": device["device_key"]},
    )
    assert mismatch.status_code == 403
    assert (
        await client.post(f"/devices/{device['id']}/heartbeat", json={"hardware_id": "MIC-0001"})
    ).status_code == 401
    assert (await beat(client, device, headers=admin_headers)).status_code == 200  # signed-in user path


async def test_warning_and_low_battery_heartbeats_set_warning(client, device):
    key = device["device_key"]
    assert (await beat(client, device, key=key, heartbeat_status="warning")).json()["status"] == "WARNING"
    assert (await beat(client, device, key=key, battery_level=5)).json()["status"] == "WARNING"
    assert (await beat(client, device, key=key, battery_level=90)).json()["status"] == "ACTIVE"


async def test_late_heartbeat_marks_device_delayed_then_recovers(client, admin_headers, device, sessionmaker):
    key = device["device_key"]
    await beat(client, device, key=key)
    async with sessionmaker() as session:
        await session.execute(update(Device).values(last_seen_at=utcnow() - timedelta(hours=1)))
        await session.commit()
    delayed = (await client.get(f"/devices/{device['id']}", headers=admin_headers)).json()
    assert delayed["status"] == "DELAYED" and delayed["online"] is False and delayed["online_since"] is None
    assert len((await client.get("/devices?status=DELAYED", headers=admin_headers)).json()) == 1
    assert (await beat(client, device, key=key)).json()["status"] == "ACTIVE"


# --- lifecycle ----------------------------------------------------------------------------------------------------
async def test_disabled_device_rejects_controls_and_keeps_status_on_heartbeat(client, admin_headers, device):
    key = device["device_key"]
    await beat(client, device, key=key)
    patched = await client.patch(f"/devices/{device['id']}", json={"status": "DISABLED"}, headers=admin_headers)
    assert patched.json()["status"] == "DISABLED" and patched.json()["online"] is False
    blocked = await client.post(f"/devices/{device['id']}/recording/start", headers=admin_headers)
    assert blocked.status_code == 409 and "disabled" in blocked.json()["detail"]
    assert (await beat(client, device, key=key)).json()["status"] == "DISABLED"  # never auto-overwritten
    re_enabled = await client.patch(f"/devices/{device['id']}", json={"status": "ACTIVE"}, headers=admin_headers)
    assert re_enabled.json()["status"] == "ACTIVE"


async def test_soft_removal_retires_device_and_keeps_history(client, admin_headers, device, sessionmaker):
    key = device["device_key"]
    await beat(client, device, key=key)
    assert (await client.delete(f"/devices/{device['id']}", headers=admin_headers)).status_code == 204
    assert (await client.delete(f"/devices/{device['id']}", headers=admin_headers)).status_code == 204  # idempotent

    assert (await client.get("/devices", headers=admin_headers)).json() == []  # hidden by default
    listed = (await client.get("/devices?include_retired=true", headers=admin_headers)).json()
    assert listed[0]["status"] == "RETIRED" and listed[0]["is_active"] is False and listed[0]["removed_at"]
    assert (await beat(client, device, key=key)).status_code == 409
    assert (await client.post(f"/devices/{device['id']}/monitoring/pause", headers=admin_headers)).status_code == 409
    assert (
        await client.patch(f"/devices/{device['id']}", json={"status": "ACTIVE"}, headers=admin_headers)
    ).status_code == 409
    history = (await client.get(f"/devices/{device['id']}/heartbeats", headers=admin_headers)).json()
    assert len(history) == 1
    async with sessionmaker() as session:
        assert (await session.execute(select(func.count()).select_from(Device))).scalar_one() == 1
        assert (await session.execute(select(func.count()).select_from(DeviceHeartbeat))).scalar_one() == 1


# --- device-level controls ----------------------------------------------------------------------------------------
async def test_configuration_requires_admin_and_valid_supported_mode(client, admin_headers, user_headers):
    regular_user = (await client.get("/users/me", headers=user_headers)).json()
    vehicle_response = await client.post(
        "/vehicles",
        json={"vehicle_code": "CAR-CONFIG", "vehicle_type": "Sedan", "assigned_user_ids": [regular_user["id"]]},
        headers=admin_headers,
    )
    assert vehicle_response.status_code == 201
    registered = await register(client, admin_headers, "MIC-CONFIG", "CAR-CONFIG")
    assert registered.status_code == 201
    endpoint = f"/devices/{registered.json()['id']}/configuration"
    config = {
        "configuration": {
            "captureEnabled": True,
            "monitoringMode": "motion_triggered",
            "heartbeatIntervalSeconds": 60,
        }
    }
    # The user can read this assigned vehicle/device but still cannot change device configuration.
    assert (await client.get(endpoint.removesuffix("/configuration"), headers=user_headers)).status_code == 200
    assert (await client.put(endpoint, json=config, headers=user_headers)).status_code == 403
    updated = await client.put(endpoint, json=config, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["configuration"] == config["configuration"]

    config["configuration"]["monitoringMode"] = "event"
    assert (await client.put(endpoint, json=config, headers=admin_headers)).status_code == 422


async def test_configuration_rejects_disabled_and_retired_devices(client, admin_headers, device):
    endpoint = f"/devices/{device['id']}/configuration"
    config = {"configuration": {"monitoringMode": "continuous"}}
    await client.patch(f"/devices/{device['id']}", json={"status": "DISABLED"}, headers=admin_headers)
    disabled = await client.put(endpoint, json=config, headers=admin_headers)
    assert disabled.status_code == 409 and "disabled" in disabled.json()["detail"].lower()

    await client.delete(f"/devices/{device['id']}", headers=admin_headers)
    retired = await client.put(endpoint, json=config, headers=admin_headers)
    assert retired.status_code == 409 and "retired" in retired.json()["detail"].lower()


async def test_device_level_controls_are_independent_per_device(client, admin_headers, vehicle):
    first = (await register(client, admin_headers, "MIC-AAAA")).json()
    second = (await register(client, admin_headers, "MIC-BBBB")).json()
    started = await client.post(f"/devices/{first['id']}/recording/start", headers=admin_headers)
    assert started.status_code == 200 and started.json()["recording"] is True
    assert (await client.get(f"/devices/{second['id']}/status", headers=admin_headers)).json()["recording"] is False
    paused = await client.post(f"/devices/{first['id']}/monitoring/pause", headers=admin_headers)
    assert paused.json()["monitoring_mode"] == "paused" and paused.json()["recording"] is False
    resumed = await client.post(f"/devices/{first['id']}/monitoring/resume", headers=admin_headers)
    assert resumed.json()["monitoring_mode"] == "continuous"
    patched = await client.patch(
        f"/devices/{second['id']}/status", json={"audio_capture_enabled": False}, headers=admin_headers
    )
    assert patched.json()["audio_capture_enabled"] is False
    conflict = await client.patch(f"/devices/{second['id']}/status", json={"recording": True}, headers=admin_headers)
    assert conflict.status_code == 409
    logs = (await client.get("/vehicles/CAR-1024/logs", headers=admin_headers)).json()
    assert any(log.get("hardware_id") == "MIC-AAAA" for log in logs)


async def test_vehicle_level_controls_resolve_the_default_device(client, admin_headers, vehicle):
    registered = (await register(client, admin_headers, "MIC-DEFAULT")).json()
    response = await client.patch("/vehicles/CAR-1024/controls", json={"recording": True}, headers=admin_headers)
    assert response.status_code == 200 and response.json()["device"]["recording"] is True
    assert (await client.get(f"/devices/{registered['id']}/status", headers=admin_headers)).json()["recording"]


async def test_telemetry_for_retired_device_is_rejected_and_tags_documents(client, admin_headers, device, mongo_db):
    ok = await client.post(
        "/telemetry/CAR-1024", json={"battery_level": 70, "device_id": device["id"]}, headers=admin_headers
    )
    assert ok.status_code == 201, ok.text
    stored = await mongo_db["telemetry_events"].find_one({"vehicle_id": "CAR-1024"})
    assert stored["device_id"] == device["id"] and stored["hardware_id"] == "MIC-0001"
    await client.delete(f"/devices/{device['id']}", headers=admin_headers)
    rejected = await client.post(
        "/telemetry/CAR-1024", json={"battery_level": 70, "device_id": device["id"]}, headers=admin_headers
    )
    assert rejected.status_code == 409


# --- vehicles: compatibility and soft delete ---------------------------------------------------------------------
async def test_deactivating_a_vehicle_keeps_devices_and_heartbeats(client, admin_headers, device, sessionmaker):
    await beat(client, device, key=device["device_key"])
    assert (await client.delete("/vehicles/CAR-1024", headers=admin_headers)).status_code == 204
    assert (await client.get("/devices", headers=admin_headers)).json() == []  # hidden with the vehicle
    async with sessionmaker() as session:
        assert (await session.execute(select(func.count()).select_from(Device))).scalar_one() == 1
        assert (await session.execute(select(func.count()).select_from(DeviceHeartbeat))).scalar_one() == 1
        assert (await session.execute(select(Vehicle.vehicle_code))).scalar_one() == "CAR-1024"


async def test_vehicle_without_devices_still_works_with_legacy_controls(client, admin_headers, vehicle):
    assert vehicle["devices"] == [] and vehicle["default_device_id"] is None and vehicle["device"] is not None
    patched = await client.patch("/vehicles/CAR-1024/controls", json={"recording": True}, headers=admin_headers)
    assert patched.json()["device"]["recording"] is True


async def test_vehicle_code_is_unique_and_type_is_exposed(client, admin_headers, vehicle):
    assert vehicle["vehicle_code"] == "CAR-1024" and vehicle["vehicle_type"] == "Sedan"
    duplicate = {"vehicle_code": "CAR-1024", "vehicle_type": "SUV"}
    assert (await client.post("/vehicles", json=duplicate, headers=admin_headers)).status_code == 409
