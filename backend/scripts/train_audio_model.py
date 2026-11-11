"""Train and honestly evaluate a CPU-friendly acoustic-event baseline."""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.audio_features import FeatureConfig, features_from_wav
from app.ml.dataset import DatasetRecord, class_counts, discover_dataset, group_aware_split
from app.services.audio_classifier import ALERT_EVENT_TYPES


def _limit_augmentations(records: list[DatasetRecord], maximum: int) -> list[DatasetRecord]:
    grouped: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        grouped[record.source_group].append(record)
    return [
        record
        for group in sorted(grouped)
        for record in sorted(grouped[group], key=lambda item: str(item.path))[:maximum]
    ]


def _matrix(records: list[DatasetRecord], config: FeatureConfig, split: str) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    labels: list[str] = []
    total = len(records)
    for index, record in enumerate(records, start=1):
        try:
            features.append(features_from_wav(record.path, config))
            labels.append(record.event_type)
        except ValueError as exc:
            raise ValueError(f"Cannot extract {record.path}: {exc}") from exc
        if index == 1 or index % 250 == 0 or index == total:
            print(f"[{split}] extracted {index}/{total}", flush=True)
    return np.vstack(features), np.asarray(labels)


def _model(c_value: float) -> object:
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=c_value, class_weight="balanced", max_iter=1500, random_state=281),
    )


def _metrics(model: object, features: np.ndarray, labels: np.ndarray) -> dict:
    predictions = model.predict(features)
    classes = list(model.classes_)
    return {
        "accuracy": round(float(accuracy_score(labels, predictions)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(labels, predictions)), 6),
        "macro_f1": round(float(f1_score(labels, predictions, average="macro")), 6),
        "labels": classes,
        "confusion_matrix": confusion_matrix(labels, predictions, labels=classes).tolist(),
        "classification_report": classification_report(labels, predictions, labels=classes, output_dict=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("ml_artifacts/audio-baseline.joblib"))
    parser.add_argument("--max-augmentations-per-source", type=int, default=12)
    parser.add_argument("--minimum-confidence", type=float, default=0.45)
    args = parser.parse_args()

    records, excluded = discover_dataset(args.dataset.resolve())
    if not records:
        raise SystemExit("No mapped WAV files were found")
    pointer_count = sum(record.is_lfs_pointer for record in records)
    if pointer_count:
        raise SystemExit(
            f"Cannot train: {pointer_count}/{len(records)} mapped WAV files are Git LFS pointers, not audio. "
            "Fetch the LFS objects from the dataset's original Git repository first."
        )

    splits = group_aware_split(records)
    splits = {
        name: _limit_augmentations(items, max(1, args.max_augmentations_per_source)) for name, items in splits.items()
    }
    print(f"Group-aware counts: { {name: class_counts(items) for name, items in splits.items()} }")
    if excluded:
        print(f"Excluded unmapped folders: {dict(excluded)}")

    config = FeatureConfig()
    x_train, y_train = _matrix(splits["train"], config, "train")
    x_val, y_val = _matrix(splits["val"], config, "val")
    x_test, y_test = _matrix(splits["test"], config, "test")

    candidates: list[tuple[float, float, object]] = []
    for c_value in (0.25, 1.0, 4.0):
        model = _model(c_value)
        model.fit(x_train, y_train)
        score = f1_score(y_val, model.predict(x_val), average="macro")
        print(f"Validation macro-F1 for C={c_value}: {score:.4f}")
        candidates.append((float(score), c_value, model))
    _, best_c, _ = max(candidates, key=lambda item: item[0])

    final_model = _model(best_c)
    final_model.fit(np.vstack([x_train, x_val]), np.concatenate([y_train, y_val]))
    test_metrics = _metrics(final_model, x_test, y_test)
    trained_classes = [str(item) for item in final_model.classes_]
    unsupported = sorted(set(ALERT_EVENT_TYPES) - set(trained_classes))
    timestamp = datetime.now(UTC)
    artifact = {
        "model": final_model,
        "model_name": "smart-car-logmel-logistic-regression",
        "model_version": f"dataset-baseline-{timestamp:%Y%m%dT%H%M%SZ}",
        "feature_config": config.to_dict(),
        "minimum_confidence": args.minimum_confidence,
        "trained_event_types": trained_classes,
        "unsupported_event_types": unsupported,
        "best_c": best_c,
        "created_at": timestamp.isoformat(),
        "dataset_counts": {name: class_counts(items) for name, items in splits.items()},
        "test_metrics": test_metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    metrics_path = args.output.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps({key: value for key, value in artifact.items() if key != "model"}, indent=2))
    print(json.dumps(test_metrics, indent=2))
    print(f"Unsupported required categories (no mapped training data): {unsupported}")
    print(f"Saved model: {args.output.resolve()}")
    print(f"Saved metrics: {metrics_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
