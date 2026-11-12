ALERT = {
    "vehicle_id": "CAR-1024",
    "event_type": "glass_breaking",
    "severity": "high",
    "confidence": 0.94,
    "location": "Front Right",
}


async def _create_alert(client, headers) -> dict:
    response = await client.post("/alerts", json=ALERT, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_alert(client, admin_headers, vehicle):
    alert = await _create_alert(client, admin_headers)
    assert alert["status"] == "open" and alert["vehicle_code"] == "CAR-1024"
    listing = await client.get("/alerts", headers=admin_headers)
    assert [a["id"] for a in listing.json()] == [alert["id"]]


async def test_create_alert_validates_input(client, admin_headers, vehicle):
    bad = await client.post("/alerts", json={**ALERT, "confidence": 1.5}, headers=admin_headers)
    assert bad.status_code == 422


async def test_acknowledge_alert_records_action(client, admin_headers, vehicle):
    alert = await _create_alert(client, admin_headers)
    response = await client.post(
        f"/alerts/{alert['id']}/acknowledge", json={"notes": "Looking into it"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged" and response.json()["reviewed_at"]

    detail = (await client.get(f"/alerts/{alert['id']}", headers=admin_headers)).json()
    assert [a["action_type"] for a in detail["actions"]] == ["created", "acknowledged"]
    assert detail["actions"][1]["notes"] == "Looking into it"
    assert (await client.post(f"/alerts/{alert['id']}/acknowledge", headers=admin_headers)).status_code == 409


async def test_resolve_alert(client, admin_headers, vehicle):
    alert = await _create_alert(client, admin_headers)
    response = await client.post(f"/alerts/{alert['id']}/resolve", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved" and body["resolved_at"] and body["reviewed_at"]

    detail = (await client.get(f"/alerts/{alert['id']}", headers=admin_headers)).json()
    assert detail["actions"][-1]["action_type"] == "resolved"
    assert (await client.post(f"/alerts/{alert['id']}/resolve", headers=admin_headers)).status_code == 409


async def test_only_admins_can_acknowledge_or_resolve(client, admin_headers, user_headers, vehicle):
    alert = await _create_alert(client, admin_headers)
    for action in ("acknowledge", "resolve"):
        response = await client.post(f"/alerts/{alert['id']}/{action}", headers=user_headers)
        assert response.status_code == 403


async def test_user_cannot_see_alerts_for_unassigned_vehicles(client, admin_headers, user_headers, vehicle):
    alert = await _create_alert(client, admin_headers)
    assert (await client.get("/alerts", headers=user_headers)).json() == []
    assert (await client.get(f"/alerts/{alert['id']}", headers=user_headers)).status_code == 404


async def test_filter_alerts_by_status(client, admin_headers, vehicle):
    first, _second = await _create_alert(client, admin_headers), await _create_alert(client, admin_headers)
    await client.post(f"/alerts/{first['id']}/resolve", headers=admin_headers)
    open_alerts = await client.get("/alerts", params={"status": "open"}, headers=admin_headers)
    assert len(open_alerts.json()) == 1
