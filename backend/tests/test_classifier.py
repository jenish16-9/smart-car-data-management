from app.services.audio_classifier import AUDIO_CLASSES, MODEL_VERSION, classify_audio


def test_mock_classifier_returns_valid_deterministic_result():
    first, second = classify_audio("s3://bucket/a.wav"), classify_audio("s3://bucket/a.wav")
    assert first.predicted_class in AUDIO_CLASSES
    assert 0.0 <= first.confidence <= 1.0
    assert (first.predicted_class, first.confidence) == (second.predicted_class, second.confidence)
    assert first.model_version == MODEL_VERSION and first.model_version.startswith("mock")


def test_mock_classifier_filename_hint():
    assert classify_audio("https://x/front_glass_break.wav").predicted_class == "glass_break"
