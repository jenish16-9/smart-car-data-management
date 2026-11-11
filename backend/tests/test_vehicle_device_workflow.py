from fastapi.testclient import TestClient

from app.core.security import CurrentUser, get_current_user
from app.main import app


VEHICLE = {
    "vin": "1HGBH41JXMN109186",
    "name": "Family Car",
    "make": "Honda",
    "model": "Civic",
    "year": 2024,
    "license_plate": "AUDIO1",
}
DEVICE = {
    "hardware_id": "AUD-EDGE-0001",
    "name": "Cabin AudioGuard",
    "firmware_version": "1.0.0",
    "configuration": {"captureMode": "event"},
}


def test_vehicle_device_vertical_slice(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    vehicle_response = client.post(
        "/api/v1/vehicles", json=VEHICLE, headers=auth_headers
    )
    assert vehicle_response.status_code == 201
    vehicle = vehicle_response.json()
    assert vehicle["status"] == "ACTIVE"

    device_response = client.post(
        f"/api/v1/vehicles/{vehicle['id']}/devices",
        json=DEVICE,
        headers=auth_headers,
    )
    assert device_response.status_code == 201
    device = device_response.json()
    assert device["vehicle_id"] == vehicle["id"]
    assert device["state"] == "PENDING"

    vehicles = client.get("/api/v1/vehicles", headers=auth_headers)
    assert vehicles.status_code == 200
    assert [item["id"] for item in vehicles.json()] == [vehicle["id"]]

    devices = client.get(
        f"/api/v1/vehicles/{vehicle['id']}/devices", headers=auth_headers
    )
    assert devices.status_code == 200
    assert [item["id"] for item in devices.json()] == [device["id"]]

    fetched = client.get(f"/api/v1/devices/{device['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["hardware_id"] == DEVICE["hardware_id"]


def test_management_endpoints_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/vehicles")
    assert response.status_code == 401
    assert response.json()["detail"] == "Valid bearer token required"


def test_vehicle_validation(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/vehicles", json={**VEHICLE, "vin": "invalid"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_duplicate_hardware_id_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    first_vehicle = client.post(
        "/api/v1/vehicles", json=VEHICLE, headers=auth_headers
    ).json()
    second_vehicle = client.post(
        "/api/v1/vehicles",
        json={**VEHICLE, "vin": "2C3KA53G76H245678", "name": "Second Car"},
        headers=auth_headers,
    ).json()
    assert (
        client.post(
            f"/api/v1/vehicles/{first_vehicle['id']}/devices",
            json=DEVICE,
            headers=auth_headers,
        ).status_code
        == 201
    )
    duplicate = client.post(
        f"/api/v1/vehicles/{second_vehicle['id']}/devices",
        json=DEVICE,
        headers=auth_headers,
    )
    assert duplicate.status_code == 409


def test_invalid_vehicle_association(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/vehicles/not-a-vehicle/devices",
        json=DEVICE,
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_owner_cannot_access_another_users_vehicle(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    vehicle = client.post("/api/v1/vehicles", json=VEHICLE, headers=auth_headers).json()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="user-2", email="other@example.com", role="admin"
    )
    try:
        response = client.get(f"/api/v1/vehicles/{vehicle['id']}", headers=auth_headers)
        assert response.status_code == 404
        assert client.get("/api/v1/vehicles", headers=auth_headers).json() == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)
