"""Inference adapter for a trained scikit-learn audio artifact."""

import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import joblib
import numpy as np

from app.ml.audio_features import FeatureConfig, features_from_wav
from app.models.common import utcnow
from app.services.audio_classifier import AudioClassificationInput, AudioClassificationResult


class SklearnAudioClassifier:
    def __init__(self, artifact_path: str | Path) -> None:
        artifact = joblib.load(artifact_path)
        self.model = artifact["model"]
        self.feature_config = FeatureConfig(**artifact["feature_config"])
        self.model_name = artifact["model_name"]
        self.model_version = artifact["model_version"]
        self.minimum_confidence = float(artifact.get("minimum_confidence", 0.45))

    @staticmethod
    def _source(audio: AudioClassificationInput) -> bytes | Path:
        if audio.audio_bytes is not None:
            return audio.audio_bytes
        if audio.source_uri is not None:
            parsed = urlparse(audio.source_uri)
            if parsed.scheme == "file":
                return Path(unquote(parsed.path.lstrip("/")))
            if not parsed.scheme:
                return Path(audio.source_uri)
            raise ValueError("Real inference requires downloaded audio bytes; remote URI fetching is not configured")
        raise ValueError("This model extracts features from WAV audio and does not accept precomputed feature maps")

    def classify(self, audio: AudioClassificationInput) -> AudioClassificationResult:
        started = time.perf_counter()
        features = features_from_wav(self._source(audio), self.feature_config).reshape(1, -1)
        probabilities = self.model.predict_proba(features)[0]
        best_index = int(np.argmax(probabilities))
        confidence = float(probabilities[best_index])
        event_type = str(self.model.classes_[best_index]) if confidence >= self.minimum_confidence else "normal"
        return AudioClassificationResult(
            event_type=event_type,
            confidence=confidence,
            model_version=self.model_version,
            processing_timestamp=utcnow(),
            model_name=self.model_name,
            processing_time_ms=int((time.perf_counter() - started) * 1000),
        )
