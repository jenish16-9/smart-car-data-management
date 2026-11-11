import io
import wave
from datetime import UTC, datetime

from app.services import audio_classifier
from app.services.audio_classifier import AudioClassificationResult


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()


async def register_device(client, headers, vehicle, hardware_id="AUDIO-SIM-1") -> dict:
    response = await client.post(
        f"/vehicles/{vehicle['id']}/devices",
        json={"hardware_id": hardware_id, "name": "Demo microphone", "firmware_version": "1.0"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def fake_result() -> AudioClassificationResult:
    return AudioClassificationResult(
        event_type="glass_breaking",
        confidence=0.91,
        model_version="baseline-test-1",
        processing_timestamp=datetime.now(UTC),
        model_name="test-classifier",
        processing_time_ms=12,
    )


async def test_device_audio_upload_classifies_and_preserves_simulation(
    client, admin_headers, vehicle, mongo_db, monkeypatch
):
    device = await register_device(client, admin_headers, vehicle)
    monkeypatch.setattr(audio_classifier, "classify_audio", lambda _audio: fake_result())

    response = await client.post(
        f"/devices/{device['id']}/classify-audio",
        files={"audio": ("glass.wav", wav_bytes(), "audio/wav")},
        data={"location": "Parking garage"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    event = response.json()
    assert event["vehicleId"] == vehicle["vehicle_code"]
    assert event["deviceId"] == device["id"]
    assert event["eventType"] == "glass_breaking"
    assert event["confidence"] == 0.91
    assert event["severity"] == "high"
    assert event["location"] == "Parking garage"
    assert event["isSimulation"] is True
    assert event["modelVersion"] == "baseline-test-1"

    stored = await mongo_db["audio_analysis_results"].find_one({"event_id": event["eventId"]})
    assert stored["device_id"] == device["id"]
    assert stored["predicted_class"] == "glass_breaking"
    assert stored["is_simulation"] is True


async def test_device_audio_upload_enforces_access_format_and_lifecycle(
    client, admin_headers, user_headers, vehicle, monkeypatch
):
    device = await register_device(client, admin_headers, vehicle, "AUDIO-SIM-2")
    monkeypatch.setattr(audio_classifier, "classify_audio", lambda _audio: fake_result())
    endpoint = f"/devices/{device['id']}/classify-audio"

    forbidden = await client.post(
        endpoint,
        files={"audio": ("demo.wav", wav_bytes(), "audio/wav")},
        headers=user_headers,
    )
    assert forbidden.status_code == 404

    invalid = await client.post(
        endpoint,
        files={"audio": ("demo.txt", b"not audio", "text/plain")},
        headers=admin_headers,
    )
    assert invalid.status_code == 422

    await client.patch(endpoint.removesuffix("/classify-audio"), json={"state": "DISABLED"}, headers=admin_headers)
    disabled = await client.post(
        endpoint,
        files={"audio": ("demo.wav", wav_bytes(), "audio/wav")},
        headers=admin_headers,
    )
    assert disabled.status_code == 409
    assert "Disabled device" in disabled.json()["detail"]

    await client.patch(endpoint.removesuffix("/classify-audio"), json={"state": "RETIRED"}, headers=admin_headers)
    retired = await client.post(
        endpoint,
        files={"audio": ("demo.wav", wav_bytes(), "audio/wav")},
        headers=admin_headers,
    )
    assert retired.status_code == 409
    assert "Retired device" in retired.json()["detail"]


async def test_device_audio_upload_reports_classifier_failure(client, admin_headers, vehicle, monkeypatch):
    device = await register_device(client, admin_headers, vehicle, "AUDIO-SIM-3")

    def fail(_audio: bytes):
        raise RuntimeError("model artifact unavailable")

    monkeypatch.setattr(audio_classifier, "classify_audio", fail)
    response = await client.post(
        f"/devices/{device['id']}/classify-audio",
        files={"audio": ("demo.wav", wav_bytes(), "audio/wav")},
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Audio classification failed: model artifact unavailable"
