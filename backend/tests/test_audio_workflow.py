import pytest

from app.services import audio_classifier
from app.services.audio_classifier import AudioClassificationResult


def _fake(predicted: str, confidence: float):
    def classify(audio_path: str) -> AudioClassificationResult:
        return AudioClassificationResult(predicted, confidence, "test-model", "t-1", 12)

    return classify


def _audio(**overrides):
    return {
        "vehicle_id": "CAR-1024",
        "storage_url": "https://storage.example.com/audio/clip.wav",
        "file_name": "clip.wav",
        "file_type": "audio/wav",
        "duration_seconds": 4.2,
        "file_size": 1024,
        **overrides,
    }


async def test_confident_detection_creates_alert(client, admin_headers, vehicle, mongo_db, monkeypatch):
    monkeypatch.setattr(audio_classifier, "classify_audio", _fake("glass_break", 0.91))
    response = await client.post("/audio", json=_audio(), headers=admin_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["processing_status"] == "completed"
    assert body["analysis"]["predicted_class"] == "glass_break" and body["alert_id"]
    assert await mongo_db["audio_analysis_results"].count_documents({"audio_record_id": body["id"]}) == 1

    alert = (await client.get(f"/alerts/{body['alert_id']}", headers=admin_headers)).json()
    assert alert["event_type"] == "glass_break" and alert["severity"] == "high"
    assert alert["audio_record_id"] == body["id"] and alert["analysis"]["model_name"] == "test-model"
    assert alert["actions"][0]["action_type"] == "created"


@pytest.mark.parametrize(("predicted", "confidence"), [("normal", 0.99), ("engine_noise", 0.79)])
async def test_no_alert_for_normal_or_low_confidence(
    client, admin_headers, vehicle, monkeypatch, predicted, confidence
):
    monkeypatch.setattr(audio_classifier, "classify_audio", _fake(predicted, confidence))
    body = (await client.post("/audio", json=_audio(), headers=admin_headers)).json()
    assert body["processing_status"] == "completed" and body["alert_id"] is None
    assert (await client.get("/alerts", headers=admin_headers)).json() == []


async def test_threshold_is_inclusive(client, admin_headers, vehicle, monkeypatch):
    monkeypatch.setattr(audio_classifier, "classify_audio", _fake("horn", 0.80))
    assert (await client.post("/audio", json=_audio(), headers=admin_headers)).json()["alert_id"]


async def test_classifier_failure_marks_audio_failed(client, admin_headers, vehicle, monkeypatch):
    def boom(_: str):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(audio_classifier, "classify_audio", boom)
    response = await client.post("/audio", json=_audio(), headers=admin_headers)
    assert response.status_code == 201 and response.json()["processing_status"] == "failed"
    fetched = await client.get(f"/audio/{response.json()['id']}", headers=admin_headers)
    assert fetched.json()["processing_status"] == "failed"


async def test_audio_listing_get_and_status_update(client, admin_headers, vehicle):
    created = (await client.post("/audio", json=_audio(), headers=admin_headers)).json()
    listed = (await client.get("/audio", headers=admin_headers)).json()
    assert [a["id"] for a in listed] == [created["id"]]
    assert listed[0]["analysis"]["predicted_class"] == created["analysis"]["predicted_class"]
    assert (await client.get(f"/audio/{created['id']}", headers=admin_headers)).json()["analysis"] is not None
    patched = await client.patch(
        f"/audio/{created['id']}/status", json={"processing_status": "pending"}, headers=admin_headers
    )
    assert patched.json()["processing_status"] == "pending"


async def test_audio_requires_object_storage_url(client, admin_headers, vehicle):
    response = await client.post("/audio", json=_audio(storage_url="not a url"), headers=admin_headers)
    assert response.status_code == 422


async def test_audio_for_inaccessible_vehicle_is_404(client, admin_headers, user_headers, vehicle):
    assert (await client.post("/audio", json=_audio(), headers=user_headers)).status_code == 404
