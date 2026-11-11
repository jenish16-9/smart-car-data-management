from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.vehicle import utc_now

VEHICLE = {
    "vin": "1HGBH41JXMN109186",
    "name": "Lifecycle Car",
    "make": "Honda",
    "model": "Civic",
    "year": 2024,
}
DEVICE = {
    "hardware_id": "AUD-EDGE-LIFECYCLE",
    "name": "Lifecycle Device",
    "firmware_version": "1.0.0",
}


def create_vehicle_and_device(
    client: TestClient, headers: dict[str, str]
) -> tuple[dict[str, object], dict[str, object]]:
    vehicle = client.post("/api/v1/vehicles", json=VEHICLE, headers=headers).json()
    device = client.post(
        f"/api/v1/vehicles/{vehicle['id']}/devices",
        json=DEVICE,
        headers=headers,
    ).json()
    return vehicle, device


def test_device_configuration_disable_and_retirement(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _, device = create_vehicle_and_device(client, auth_headers)
    device_id = device["id"]

    configured = client.put(
        f"/api/v1/devices/{device_id}/configuration",
        json={
            "configuration": {
                "captureEnabled": True,
                "monitoringMode": "continuous",
                "heartbeatIntervalSeconds": 30,
            }
        },
        headers=auth_headers,
    )
    assert configured.status_code == 200
    assert configured.json()["configuration"]["monitoringMode"] == "continuous"
    invalid_configuration = client.put(
        f"/api/v1/devices/{device_id}/configuration",
        json={"configuration": {"heartbeatIntervalSeconds": 1}},
        headers=auth_headers,
    )
    assert invalid_configuration.status_code == 422

    disabled = client.patch(
        f"/api/v1/devices/{device_id}",
        json={"state": "DISABLED", "name": "Disabled Device"},
        headers=auth_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["state"] == "DISABLED"

    heartbeat = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        json={"health": "HEALTHY", "metrics": {"batteryPercent": 90}},
        headers=auth_headers,
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["device_state"] == "DISABLED"

    retired = client.patch(
        f"/api/v1/devices/{device_id}",
        json={"state": "RETIRED"},
        headers=auth_headers,
    )
    assert retired.status_code == 200
    assert retired.json()["state"] == "RETIRED"
    assert (
        client.post(
            f"/api/v1/devices/{device_id}/heartbeat",
            json={"health": "HEALTHY"},
            headers=auth_headers,
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/api/v1/devices/{device_id}/configuration",
            json={"configuration": {}},
            headers=auth_headers,
        ).status_code
        == 409
    )


def test_heartbeat_connectivity_transitions(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    _, device_data = create_vehicle_and_device(client, auth_headers)
    device_id = str(device_data["id"])

    first = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        json={"health": "HEALTHY"},
        headers=auth_headers,
    )
    assert first.status_code == 200
    assert first.json()["device_state"] == "ONLINE"

    device = db_session.get(Device, device_id)
    assert device is not None
    device.last_heartbeat_at = utc_now() - timedelta(
        seconds=settings.device_delayed_after_seconds + 1
    )
    db_session.commit()
    assert (
        client.get(f"/api/v1/devices/{device_id}", headers=auth_headers).json()["state"]
        == "DELAYED"
    )

    device.last_heartbeat_at = utc_now() - timedelta(
        seconds=settings.device_offline_after_seconds + 1
    )
    db_session.commit()
    assert (
        client.get(f"/api/v1/devices/{device_id}", headers=auth_headers).json()["state"]
        == "OFFLINE"
    )

    warning = client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        json={"health": "WARNING", "metrics": {"temperatureCelsius": 92}},
        headers=auth_headers,
    )
    assert warning.status_code == 200
    assert warning.json()["device_state"] == "WARNING"


def test_soft_device_removal_preserves_heartbeat_history(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    vehicle, device = create_vehicle_and_device(client, auth_headers)
    device_id = device["id"]
    client.post(
        f"/api/v1/devices/{device_id}/heartbeat",
        json={"health": "HEALTHY"},
        headers=auth_headers,
    )

    removed = client.delete(f"/api/v1/devices/{device_id}", headers=auth_headers)
    assert removed.status_code == 204
    assert (
        client.get(f"/api/v1/devices/{device_id}", headers=auth_headers).json()["state"]
        == "RETIRED"
    )
    assert (
        client.get(
            f"/api/v1/vehicles/{vehicle['id']}/devices", headers=auth_headers
        ).json()
        == []
    )
    history = client.get(
        f"/api/v1/devices/{device_id}/heartbeats", headers=auth_headers
    )
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_vehicle_update_deactivation_and_soft_removal(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    vehicle, device = create_vehicle_and_device(client, auth_headers)
    vehicle_id = vehicle["id"]

    updated = client.patch(
        f"/api/v1/vehicles/{vehicle_id}",
        json={"name": "Updated Car", "status": "DEACTIVATED"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Car"
    assert updated.json()["status"] == "DEACTIVATED"
    assert (
        client.get(f"/api/v1/devices/{device['id']}", headers=auth_headers).json()[
            "state"
        ]
        == "DISABLED"
    )
    assert (
        client.post(
            f"/api/v1/vehicles/{vehicle_id}/devices",
            json={**DEVICE, "hardware_id": "ANOTHER-DEVICE"},
            headers=auth_headers,
        ).status_code
        == 409
    )

    removed = client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=auth_headers)
    assert removed.status_code == 204
    assert (
        client.get(f"/api/v1/vehicles/{vehicle_id}", headers=auth_headers).status_code
        == 404
    )
    assert client.get("/api/v1/vehicles", headers=auth_headers).json() == []
    assert (
        client.get(f"/api/v1/devices/{device['id']}", headers=auth_headers).json()[
            "state"
        ]
        == "RETIRED"
    )


def test_device_state_validation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _, device = create_vehicle_and_device(client, auth_headers)
    response = client.patch(
        f"/api/v1/devices/{device['id']}",
        json={"state": "ONLINE"},
        headers=auth_headers,
    )
    assert response.status_code == 422
