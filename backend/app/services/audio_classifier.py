"""Replaceable audio-classification contract and deterministic development mock.

The mock does not listen to audio and must not be used for safety decisions. It exists so
the upload, analysis, alert, and UI workflow can be exercised before a real model and an
evaluated dataset are available. A YAMNet (or other) adapter can implement ``AudioClassifier``
without changing the service layer.
"""

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.models.common import utcnow

MODEL_NAME = "mock-audio-classifier"
MODEL_VERSION = "mock-0.2"

ALERT_EVENT_TYPES = (
    "emergency_vehicle_siren",
    "glass_breaking",
    "screaming",
    "gunshot",
    "crash",
    "tire_skidding",
    "abnormal_engine_noise",
)
AUDIO_CLASSES = (*ALERT_EVENT_TYPES, "normal")

_KEYWORD_HINTS = {
    "ambulance": "emergency_vehicle_siren",
    "emergency_vehicle_siren": "emergency_vehicle_siren",
    "fire_engine": "emergency_vehicle_siren",
    "police_siren": "emergency_vehicle_siren",
    "siren": "emergency_vehicle_siren",
    "glass_breaking": "glass_breaking",
    "glass_break": "glass_breaking",
    "glass": "glass_breaking",
    "screaming": "screaming",
    "scream": "screaming",
    "gunshot": "gunshot",
    "gunfire": "gunshot",
    "crash": "crash",
    "collision": "crash",
    "tire_skidding": "tire_skidding",
    "tire_squeal": "tire_skidding",
    "skidding": "tire_skidding",
    "engine_knocking": "abnormal_engine_noise",
    "abnormal_engine_noise": "abnormal_engine_noise",
    "engine_noise": "abnormal_engine_noise",
    "normal": "normal",
}

FeatureValues = Mapping[str, float | Sequence[float]]


@dataclass(frozen=True)
class AudioClassificationInput:
    """One classifier input: a URI, audio bytes, or pre-extracted numeric features."""

    source_uri: str | None = None
    audio_bytes: bytes | None = None
    features: FeatureValues | None = None

    def __post_init__(self) -> None:
        supplied = sum(value is not None for value in (self.source_uri, self.audio_bytes, self.features))
        if supplied != 1:
            raise ValueError("Provide exactly one of source_uri, audio_bytes, or features")
        if self.source_uri is not None and not self.source_uri.strip():
            raise ValueError("source_uri cannot be empty")
        if self.audio_bytes is not None and not self.audio_bytes:
            raise ValueError("audio_bytes cannot be empty")
        if self.features is not None and not self.features:
            raise ValueError("features cannot be empty")

    def fingerprint_bytes(self) -> bytes:
        if self.source_uri is not None:
            return self.source_uri.encode("utf-8")
        if self.audio_bytes is not None:
            return self.audio_bytes
        return json.dumps(self.features, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class AudioClassificationResult:
    event_type: str
    confidence: float
    model_version: str
    processing_timestamp: datetime
    model_name: str
    processing_time_ms: int

    def __post_init__(self) -> None:
        if self.event_type not in AUDIO_CLASSES:
            raise ValueError(f"Unsupported event type: {self.event_type}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.processing_timestamp.tzinfo is None:
            raise ValueError("processing_timestamp must include a timezone")


@runtime_checkable
class AudioClassifier(Protocol):
    model_name: str
    model_version: str

    def classify(self, audio: AudioClassificationInput) -> AudioClassificationResult: ...


class MockAudioClassifier:
    """Deterministic development implementation; it performs no audio inference."""

    model_name = MODEL_NAME
    model_version = MODEL_VERSION

    @staticmethod
    def _hinted_class(audio: AudioClassificationInput) -> str | None:
        if audio.source_uri is None:
            return None
        lowered = audio.source_uri.lower()
        return next((label for keyword, label in _KEYWORD_HINTS.items() if keyword in lowered), None)

    def classify(self, audio: AudioClassificationInput) -> AudioClassificationResult:
        started = time.perf_counter()
        digest = hashlib.sha256(audio.fingerprint_bytes()).digest()
        event_type = self._hinted_class(audio) or AUDIO_CLASSES[digest[0] % len(AUDIO_CLASSES)]
        confidence = round(0.70 + (digest[1] / 255) * 0.29, 2)
        return AudioClassificationResult(
            event_type=event_type,
            confidence=confidence,
            model_version=self.model_version,
            processing_timestamp=utcnow(),
            model_name=self.model_name,
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )


default_classifier: AudioClassifier = MockAudioClassifier()


class UnavailableAudioClassifier:
    """Fail closed when a configured real model cannot be loaded."""

    model_name = "unavailable-audio-classifier"
    model_version = "unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def classify(self, audio: AudioClassificationInput) -> AudioClassificationResult:
        raise RuntimeError(self.reason)


def configure_default_classifier(backend: str, model_path: str) -> None:
    """Select the development mock or a trained local artifact at application startup."""
    global default_classifier
    if backend == "mock":
        default_classifier = MockAudioClassifier()
        return
    if backend != "sklearn":
        reason = f"Unsupported AUDIO_CLASSIFIER_BACKEND: {backend}"
        default_classifier = UnavailableAudioClassifier(reason)
        raise ValueError(reason)
    try:
        from app.ml.sklearn_classifier import SklearnAudioClassifier

        default_classifier = SklearnAudioClassifier(model_path)
    except Exception as exc:
        reason = f"Could not load audio model {model_path}: {exc}"
        default_classifier = UnavailableAudioClassifier(reason)
        raise RuntimeError(reason) from exc


def classify_audio(audio: str | bytes | FeatureValues | AudioClassificationInput) -> AudioClassificationResult:
    """Compatibility entry point used by the service and existing model adapters."""
    if isinstance(audio, AudioClassificationInput):
        classifier_input = audio
    elif isinstance(audio, str):
        classifier_input = AudioClassificationInput(source_uri=audio)
    elif isinstance(audio, bytes):
        classifier_input = AudioClassificationInput(audio_bytes=audio)
    else:
        classifier_input = AudioClassificationInput(features=audio)
    return default_classifier.classify(classifier_input)
