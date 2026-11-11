from app.models.common import utcnow
from app.services import audio_classifier
from app.services.audio_classifier import AudioClassificationResult


def _result(event_type: str, confidence: float) -> AudioClassificationResult:
    return AudioClassificationResult(
        event_type=event_type,
        confidence=confidence,
        model_version="1",
        processing_timestamp=utcnow(),
        model_name="test-model",
        processing_time_ms=1,
    )


async def _upload(client, headers, name):
    payload = {
        "vehicle_id": "CAR-1024",
        "storage_url": f"https://s.example.com/{name}",
        "file_name": name,
        "file_type": "audio/wav",
    }
    assert (await client.post("/audio", json=payload, headers=headers)).status_code == 201


async def test_summary_on_empty_system(client, admin_headers):
    response = await client.get("/analytics/summary", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {
        "total_events": 0,
        "critical_events": 0,
        "average_confidence": 0,
        "resolution_rate": 0,
        "vehicle_count": 0,
        "audio_upload_count": 0,
        "detection_count": 0,
        "active_alert_count": 0,
    }


async def test_summary_reflects_audio_and_alerts(client, admin_headers, vehicle, monkeypatch):
    results = iter([("glass_breaking", 0.90), ("normal", 0.70), ("abnormal_engine_noise", 0.90)])
    monkeypatch.setattr(audio_classifier, "classify_audio", lambda _p: _result(*next(results)))
    for name in ("a.wav", "b.wav", "c.wav"):
        await _upload(client, admin_headers, name)
    glass_alert = (await client.get("/alerts", headers=admin_headers)).json()
    resolved_id = next(a["id"] for a in glass_alert if a["event_type"] == "glass_breaking")
    await client.post(f"/alerts/{resolved_id}/resolve", headers=admin_headers)

    summary = (await client.get("/analytics/summary", headers=admin_headers)).json()
    assert summary["total_events"] == 3 and summary["detection_count"] == 2
    assert summary["average_confidence"] == 83  # mean(0.9, 0.7, 0.9)
    assert summary["critical_events"] == 1  # the high-severity glass break
    assert summary["resolution_rate"] == 50 and summary["active_alert_count"] == 1
    assert summary["vehicle_count"] == 1 and summary["audio_upload_count"] == 3


async def test_events_by_type_and_over_time(client, admin_headers, vehicle, monkeypatch):
    results = iter([("glass_breaking", 0.9), ("glass_breaking", 0.8), ("tire_skidding", 0.7)])
    monkeypatch.setattr(audio_classifier, "classify_audio", lambda _p: _result(*next(results)))
    for name in ("a.wav", "b.wav", "c.wav"):
        await _upload(client, admin_headers, name)

    by_type = (await client.get("/analytics/events-by-type", headers=admin_headers)).json()
    assert [(r["event_type"], r["count"], r["average_confidence"]) for r in by_type] == [
        ("glass_breaking", 2, 85),
        ("tire_skidding", 1, 70),
    ]
    over_time = (await client.get("/analytics/events-over-time", headers=admin_headers)).json()
    assert len(over_time) == 1 and over_time[0]["count"] == 3


async def test_analytics_scoped_to_assigned_vehicles(client, admin_headers, user_headers, vehicle):
    await _upload(client, admin_headers, "x.wav")
    summary = (await client.get("/analytics/summary", headers=user_headers)).json()
    assert summary["total_events"] == 0 and summary["vehicle_count"] == 0
    assert (
        await client.get("/analytics/summary", params={"vehicle_id": "CAR-1024"}, headers=user_headers)
    ).status_code == 404
