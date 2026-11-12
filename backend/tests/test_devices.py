from datetime import timedelta

from app.core.config import settings
from app.models.common import utcnow
from app.repositories import device_repository

DEVICE = {
    "hardware_id": "AUD-EDGE-0001",
    "name": "Cabin AudioGuard",
    "firmware_version": "1.0.0",
}


async def register_device(client, admin_headers, vehicle, **changes):
    response = await client.post(
        f"/vehicles/{vehicle['id']}/devices",
        json={**DEVICE, **changes},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_register_list_and_get_device(client, admin_headers, vehicle):
    device = await register_device(client, admin_headers, vehicle)
    assert device["state"] == "PENDING"
    assert device["vehicle_id"] == vehicle["id"]
    listed = (await client.get(f"/vehicles/{vehicle['vehicle_code']}/devices", headers=admin_headers)).json()
    assert [item["id"] for item in listed] == [device["id"]]
    fetched = await client.get(f"/devices/{device['id']}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["hardware_id"] == DEVICE["hardware_id"]


async def test_vehicle_audio_state_follows_registered_device_heartbeat(client, admin_headers, vehicle):
    assert (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()["audio_device_state"] == "OFFLINE"
    device = await register_device(client, admin_headers, vehicle)
    assert (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()["audio_device_state"] == "PENDING"
    await client.post(f"/devices/{device['id']}/heartbeat", json={"health": "HEALTHY"}, headers=admin_headers)
    assert (await client.get("/vehicles/CAR-1024", headers=admin_headers)).json()["audio_device_state"] == "ONLINE"


async def test_duplicate_hardware_and_invalid_association(client, admin_headers, vehicle):
    await register_device(client, admin_headers, vehicle)
    duplicate = await client.post(f"/vehicles/{vehicle['id']}/devices", json=DEVICE, headers=admin_headers)
    assert duplicate.status_code == 409
    missing = await client.post(
        "/vehicles/not-a-vehicle/devices",
        json={**DEVICE, "hardware_id": "OTHER-DEVICE"},
        headers=admin_headers,
    )
    assert missing.status_code == 404


async def test_device_access_is_scoped(client, admin_headers, user_headers, vehicle):
    device = await register_device(client, admin_headers, vehicle)
    assert (await client.get(f"/devices/{device['id']}", headers=user_headers)).status_code == 404
    assert (
        await client.patch(
            f"/devices/{device['id']}",
            json={"name": "Unauthorized"},
            headers=user_headers,
        )
    ).status_code == 404


async def test_configuration_disable_and_terminal_retirement(client, admin_headers, vehicle):
    device = await register_device(client, admin_headers, vehicle)
    configured = await client.put(
        f"/devices/{device['id']}/configuration",
        json={
            "configuration": {
                "captureEnabled": True,
                "monitoringMode": "continuous",
                "heartbeatIntervalSeconds": 30,
            }
        },
        headers=admin_headers,
    )
    assert configured.status_code == 200
    assert configured.json()["configuration"]["monitoringMode"] == "continuous"
    invalid = await client.put(
        f"/devices/{device['id']}/configuration",
        json={"configuration": {"heartbeatIntervalSeconds": 1}},
        headers=admin_headers,
    )
    assert invalid.status_code == 422

    disabled = await client.patch(
        f"/devices/{device['id']}",
        json={"state": "DISABLED"},
        headers=admin_headers,
    )
    assert disabled.json()["state"] == "DISABLED"
    heartbeat = await client.post(
        f"/devices/{device['id']}/heartbeat",
        json={"health": "HEALTHY"},
        headers=admin_headers,
    )
    assert heartbeat.json()["device_state"] == "DISABLED"

    retired = await client.patch(
        f"/devices/{device['id']}",
        json={"state": "RETIRED"},
        headers=admin_headers,
    )
    assert retired.json()["state"] == "RETIRED"
    assert (
        await client.post(
            f"/devices/{device['id']}/heartbeat",
            json={"health": "HEALTHY"},
            headers=admin_headers,
        )
    ).status_code == 409
    assert (
        await client.put(
            f"/devices/{device['id']}/configuration",
            json={"configuration": {}},
            headers=admin_headers,
        )
    ).status_code == 409


async def test_heartbeat_states_and_history(client, admin_headers, vehicle, sessionmaker, mongo_db):
    device = await register_device(client, admin_headers, vehicle)
    healthy = await client.post(
        f"/devices/{device['id']}/heartbeat",
        json={"health": "HEALTHY", "metrics": {"batteryPercent": 88}},
        headers=admin_headers,
    )
    assert healthy.status_code == 200
    assert healthy.json()["device_state"] == "ONLINE"
    assert await mongo_db["device_heartbeats"].count_documents({"device_id": device["id"]}) == 1

    async with sessionmaker() as session:
        stored = await device_repository.get_by_id(session, device["id"])
        stored.last_heartbeat_at = utcnow() - timedelta(seconds=settings.device_delayed_after_seconds + 1)
        await session.commit()
    delayed = await client.get(f"/devices/{device['id']}", headers=admin_headers)
    assert delayed.json()["state"] == "DELAYED"

    async with sessionmaker() as session:
        stored = await device_repository.get_by_id(session, device["id"])
        stored.last_heartbeat_at = utcnow() - timedelta(seconds=settings.device_offline_after_seconds + 1)
        await session.commit()
    offline = await client.get(f"/devices/{device['id']}", headers=admin_headers)
    assert offline.json()["state"] == "OFFLINE"

    warning = await client.post(
        f"/devices/{device['id']}/heartbeat",
        json={"health": "WARNING", "metrics": {"temperatureCelsius": 95}},
        headers=admin_headers,
    )
    assert warning.json()["device_state"] == "WARNING"
    history = await client.get(f"/devices/{device['id']}/heartbeats", headers=admin_headers)
    assert history.status_code == 200
    assert [item["health"] for item in history.json()] == ["WARNING", "HEALTHY"]


async def test_soft_removal_preserves_history(client, admin_headers, vehicle, mongo_db):
    device = await register_device(client, admin_headers, vehicle)
    await client.post(
        f"/devices/{device['id']}/heartbeat",
        json={"health": "HEALTHY"},
        headers=admin_headers,
    )
    removed = await client.delete(f"/devices/{device['id']}", headers=admin_headers)
    assert removed.status_code == 204
    listed = await client.get(f"/vehicles/{vehicle['id']}/devices", headers=admin_headers)
    assert listed.json() == []
    retained = await client.get(f"/devices/{device['id']}", headers=admin_headers)
    assert retained.json()["state"] == "RETIRED"
    assert await mongo_db["device_heartbeats"].count_documents({"device_id": device["id"]}) == 1


async def test_vehicle_delete_detaches_and_retires_device(client, admin_headers, vehicle):
    device = await register_device(client, admin_headers, vehicle)
    assert (await client.delete(f"/vehicles/{vehicle['id']}", headers=admin_headers)).status_code == 204
    retained = await client.get(f"/devices/{device['id']}", headers=admin_headers)
    assert retained.status_code == 200
    assert retained.json()["vehicle_id"] is None
    assert retained.json()["state"] == "RETIRED"
