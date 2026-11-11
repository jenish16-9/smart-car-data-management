"""Dataset discovery, label mapping, Git LFS checks, and leakage-safe grouping."""

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

FOLDER_TO_EVENT_TYPE = {
    "collision_sounds": "crash",
    "car_crash": "crash",
    "emergency_sirens": "emergency_vehicle_siren",
    "glass_breaking": "glass_breaking",
    "glass_breaking_backup_20251115_174210": "glass_breaking",
    "human_scream": "screaming",
    "environmental_sounds": "normal",
    "road_traffic": "normal",
}


@dataclass(frozen=True)
class DatasetRecord:
    path: Path
    event_type: str
    original_split: str
    source_group: str
    is_lfs_pointer: bool


def is_git_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(42).startswith(b"version https://git-lfs.github.com/spec/")
    except OSError:
        return False


def source_group(path: Path) -> str:
    """Strip augmentation suffixes so derivatives cannot leak across splits."""
    stem = path.stem.lower()
    stem = re.split(r"_aug", stem, maxsplit=1)[0]
    stem = re.sub(r"^esc50_glass_breaking_", "", stem)
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_")


def discover_dataset(root: Path) -> tuple[list[DatasetRecord], Counter[str]]:
    records: list[DatasetRecord] = []
    excluded: Counter[str] = Counter()
    for split in ("train", "val", "test"):
        split_root = root / split
        if not split_root.is_dir():
            continue
        for path in split_root.rglob("*.wav"):
            folder = path.parent.name
            event_type = FOLDER_TO_EVENT_TYPE.get(folder)
            if event_type is None:
                excluded[folder] += 1
                continue
            records.append(
                DatasetRecord(
                    path=path,
                    event_type=event_type,
                    original_split=split,
                    source_group=f"{event_type}:{source_group(path)}",
                    is_lfs_pointer=is_git_lfs_pointer(path),
                )
            )
    return records, excluded


def split_leakage(records: list[DatasetRecord]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for record in records:
        groups[record.source_group].add(record.original_split)
    return {group: splits for group, splits in groups.items() if len(splits) > 1}


def group_aware_split(records: list[DatasetRecord]) -> dict[str, list[DatasetRecord]]:
    """Deterministically assign source recordings 70/15/15 within every label."""
    groups_by_label: dict[str, dict[str, list[DatasetRecord]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        groups_by_label[record.event_type][record.source_group].append(record)

    result: dict[str, list[DatasetRecord]] = {"train": [], "val": [], "test": []}
    for event_type, groups in groups_by_label.items():
        ordered = sorted(
            groups,
            key=lambda group: hashlib.sha256(f"smart-car-audio-v1:{group}".encode()).digest(),
        )
        count = len(ordered)
        if count < 3:
            raise ValueError(f"{event_type} has only {count} independent source groups; at least 3 are required")
        train_end = max(1, round(count * 0.70))
        val_end = min(count - 1, max(train_end + 1, round(count * 0.85)))
        for index, group in enumerate(ordered):
            split = "train" if index < train_end else "val" if index < val_end else "test"
            result[split].extend(groups[group])
    return result


def class_counts(records: list[DatasetRecord]) -> dict[str, int]:
    return dict(sorted(Counter(record.event_type for record in records).items()))
