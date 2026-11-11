"""Audio classification.

*** MOCK IMPLEMENTATION - NOT A TRAINED MODEL ***

`classify_audio` below does not listen to any audio. It returns a pseudo-random but
deterministic label derived from a hash of the path so the rest of the pipeline
(MongoDB result, alert creation, dashboard) can be built and tested end to end.
Its output must not be used for real safety or security decisions.

To plug in a real model (PyTorch, TensorFlow, YAMNet, ...), keep this interface:
replace the body of `classify_audio` (and bump MODEL_NAME / MODEL_VERSION). Nothing
else in the application needs to change.
"""

import hashlib
import time
from dataclasses import dataclass

MODEL_NAME = "mock-audio-classifier"
MODEL_VERSION = "mock-0.1"

AUDIO_CLASSES = ("glass_break", "engine_noise", "cabin_noise", "horn", "crash", "normal")

# Demo/test convenience: a keyword in the path forces that label (e.g. "front_glass_break.wav").
_KEYWORD_HINTS = {name: name for name in AUDIO_CLASSES} | {"glass": "glass_break", "engine": "engine_noise"}


@dataclass(frozen=True)
class AudioClassificationResult:
    predicted_class: str
    confidence: float
    model_name: str
    model_version: str
    processing_time_ms: int


def _hinted_class(audio_path: str) -> str | None:
    lowered = audio_path.lower()
    return next((label for keyword, label in _KEYWORD_HINTS.items() if keyword in lowered), None)


def classify_audio(audio_path: str) -> AudioClassificationResult:
    """MOCK: deterministic placeholder classification of `audio_path` (see module docstring)."""
    started = time.perf_counter()
    digest = hashlib.sha256(audio_path.encode("utf-8")).digest()
    predicted = _hinted_class(audio_path) or AUDIO_CLASSES[digest[0] % len(AUDIO_CLASSES)]
    confidence = round(0.70 + (digest[1] / 255) * 0.29, 2)  # 0.70 - 0.99
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return AudioClassificationResult(
        predicted_class=predicted,
        confidence=confidence,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        processing_time_ms=elapsed_ms,
    )
