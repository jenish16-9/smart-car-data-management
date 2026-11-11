# ruff: noqa: E402

import io
import math
import struct
import sys
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

np = pytest.importorskip("numpy")
joblib = pytest.importorskip("joblib")
sklearn = pytest.importorskip("sklearn")

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.audio_features import FeatureConfig, decode_wav, features_from_wav
from app.ml.dataset import (
    DatasetRecord,
    cross_label_source_conflicts,
    discover_dataset,
    event_type_for_path,
    group_aware_split,
    split_leakage,
)
from app.ml.sklearn_classifier import SklearnAudioClassifier
from app.services.audio_classifier import AudioClassificationInput, AudioClassifier
from scripts.train_audio_model import main as train_main


def _temporary_directory() -> TemporaryDirectory:
    base = Path(__file__).parent.parent / ".pytest_cache" / "audio-ml"
    base.mkdir(parents=True, exist_ok=True)
    return TemporaryDirectory(dir=base)


def _wav_bytes(frequency: float, *, seconds: float = 0.25, sample_rate: int = 16_000) -> bytes:
    output = io.BytesIO()
    samples = [
        int(math.sin(2 * math.pi * frequency * index / sample_rate) * 12_000)
        for index in range(int(seconds * sample_rate))
    ]
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return output.getvalue()


def test_wav_feature_extraction_is_fixed_and_finite():
    waveform = decode_wav(_wav_bytes(440))
    features = features_from_wav(_wav_bytes(440))
    assert waveform.dtype == np.float32
    assert features.shape == (FeatureConfig().n_mels * 7 + 10,)
    assert np.isfinite(features).all()


def test_dataset_audit_detects_lfs_and_split_leakage():
    with _temporary_directory() as temporary:
        root = Path(temporary)
        for split in ("train", "test"):
            folder = root / split / "human_scream"
            folder.mkdir(parents=True)
            (folder / f"same_recording{'_aug4' if split == 'test' else ''}.wav").write_text(
                "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 42\n"
            )
        records, excluded = discover_dataset(root)
        assert not excluded and all(record.is_lfs_pointer for record in records)
        assert len(split_leakage(records)) == 1


def test_collision_folder_recovers_explicit_glass_labels():
    base = Path("collision_sounds")
    assert event_type_for_path(base / "vehicle-impact-01.wav") == "crash"
    assert event_type_for_path(base / "glass-shatter-01.wav") == "glass_breaking"
    assert event_type_for_path(base / "esc50_glass_breaking_2-112213-A-39.wav") == "glass_breaking"


def test_cross_label_source_conflicts_are_visible():
    records = [
        DatasetRecord(Path("a.wav"), "crash", "train", "crash:same", False),
        DatasetRecord(Path("b.wav"), "screaming", "test", "screaming:same", False),
    ]
    assert cross_label_source_conflicts(records) == {"same": {"crash", "screaming"}}


def test_group_aware_split_never_separates_augmentations():
    with _temporary_directory() as temporary:
        root = Path(temporary)
        records = []
        for index in range(12):
            for augmentation in range(3):
                records.append(
                    DatasetRecord(
                        path=root / f"source-{index}_aug{augmentation}.wav",
                        event_type="screaming",
                        original_split="train",
                        source_group=f"screaming:source-{index}",
                        is_lfs_pointer=False,
                    )
                )
        splits = group_aware_split(records)
        ownership = {}
        for split, split_records in splits.items():
            for record in split_records:
                assert record.source_group not in ownership or ownership[record.source_group] == split
                ownership[record.source_group] = split
        assert set(splits) == {"train", "val", "test"} and all(splits.values())


def test_trained_classifier_loads_artifact_and_classifies_wav():
    with _temporary_directory() as temporary:
        config = FeatureConfig()
        low = np.vstack([features_from_wav(_wav_bytes(220 + offset), config) for offset in range(5)])
        high = np.vstack([features_from_wav(_wav_bytes(2200 + offset), config) for offset in range(5)])
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=281))
        model.fit(np.vstack([low, high]), np.array(["normal"] * 5 + ["screaming"] * 5))
        artifact = Path(temporary) / "model.joblib"
        joblib.dump(
            {
                "model": model,
                "model_name": "test-audio-model",
                "model_version": "test-1",
                "feature_config": config.to_dict(),
                "minimum_confidence": 0.0,
            },
            artifact,
        )
        classifier = SklearnAudioClassifier(artifact)
        assert isinstance(classifier, AudioClassifier)
        result = classifier.classify(AudioClassificationInput(audio_bytes=_wav_bytes(2200)))
        assert result.event_type == "screaming"
        assert 0 <= result.confidence <= 1
        wav_path = Path(temporary) / "sample.wav"
        wav_path.write_bytes(_wav_bytes(2200))
        assert classifier.classify(AudioClassificationInput(source_uri=str(wav_path))).event_type == "screaming"


def test_training_command_creates_evaluated_artifact():
    with _temporary_directory() as temporary:
        root = Path(temporary)
        for folder, base_frequency in (("human_scream", 2200), ("road_traffic", 220)):
            class_root = root / "dataset" / "train" / folder
            class_root.mkdir(parents=True)
            for index in range(10):
                (class_root / f"{folder}-source-{index}.wav").write_bytes(_wav_bytes(base_frequency + index))
        artifact = root / "model.joblib"
        previous_argv = sys.argv
        sys.argv = [
            "train_audio_model",
            str(root / "dataset"),
            "--output",
            str(artifact),
            "--max-augmentations-per-source",
            "1",
        ]
        try:
            assert train_main() == 0
        finally:
            sys.argv = previous_argv
        saved = joblib.load(artifact)
        assert artifact.exists() and artifact.with_suffix(".metrics.json").exists()
        assert saved["test_metrics"]["accuracy"] == 1.0
        assert set(saved["trained_event_types"]) == {"normal", "screaming"}
