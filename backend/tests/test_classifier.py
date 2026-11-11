import pytest

from app.services.audio_classifier import (
    ALERT_EVENT_TYPES,
    AUDIO_CLASSES,
    MODEL_VERSION,
    AudioClassificationInput,
    AudioClassifier,
    MockAudioClassifier,
    classify_audio,
)


def test_mock_classifier_returns_valid_deterministic_result():
    first, second = classify_audio("s3://bucket/a.wav"), classify_audio("s3://bucket/a.wav")
    assert first.event_type in AUDIO_CLASSES
    assert 0.0 <= first.confidence <= 1.0
    assert (first.event_type, first.confidence) == (second.event_type, second.confidence)
    assert first.model_version == MODEL_VERSION and first.model_version.startswith("mock")
    assert first.processing_timestamp.tzinfo is not None


def test_mock_classifier_filename_hint():
    hints = {
        "police_siren.wav": "emergency_vehicle_siren",
        "front_glass_break.wav": "glass_breaking",
        "passenger_screaming.wav": "screaming",
        "gunshot.wav": "gunshot",
        "vehicle_crash.wav": "crash",
        "tire_squeal.wav": "tire_skidding",
        "engine_knocking.wav": "abnormal_engine_noise",
    }
    assert set(hints.values()) == set(ALERT_EVENT_TYPES)
    for filename, expected in hints.items():
        assert classify_audio(f"https://x/{filename}").event_type == expected


def test_classifier_accepts_bytes_and_features():
    assert classify_audio(b"synthetic wav bytes").event_type in AUDIO_CLASSES
    assert classify_audio({"embedding": [0.1, 0.2], "energy": 0.8}).event_type in AUDIO_CLASSES


def test_classifier_input_requires_exactly_one_representation():
    with pytest.raises(ValueError, match="exactly one"):
        AudioClassificationInput()
    with pytest.raises(ValueError, match="exactly one"):
        AudioClassificationInput(source_uri="s3://clip.wav", audio_bytes=b"audio")


def test_mock_implements_replaceable_protocol():
    assert isinstance(MockAudioClassifier(), AudioClassifier)
