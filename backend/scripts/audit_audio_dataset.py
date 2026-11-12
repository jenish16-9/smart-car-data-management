"""Audit audio labels, Git LFS materialization, and source-group split leakage."""

import argparse
import json
from collections import Counter
from pathlib import Path

from app.ml.dataset import class_counts, cross_label_source_conflicts, discover_dataset, split_leakage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero for LFS pointers or split leakage")
    args = parser.parse_args()

    records, excluded = discover_dataset(args.dataset.resolve())
    pointers = [record for record in records if record.is_lfs_pointer]
    leakage = split_leakage(records)
    label_conflicts = cross_label_source_conflicts(records)
    payload = {
        "dataset": str(args.dataset.resolve()),
        "usable_label_counts": class_counts(records),
        "original_split_counts": dict(sorted(Counter(record.original_split for record in records).items())),
        "excluded_folder_counts": dict(sorted(excluded.items())),
        "git_lfs_pointer_count": len(pointers),
        "materialized_wav_count": len(records) - len(pointers),
        "cross_split_source_group_count": len(leakage),
        "cross_label_source_group_count": len(label_conflicts),
        "cross_split_source_group_examples": [
            {"source_group": group, "splits": sorted(splits)} for group, splits in list(sorted(leakage.items()))[:20]
        ],
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Dataset: {payload['dataset']}")
        print(f"Mapped files: {len(records)}")
        print(f"Classes: {payload['usable_label_counts']}")
        print(f"Excluded folders: {payload['excluded_folder_counts']}")
        print(f"Git LFS pointers (not audio): {len(pointers)}")
        print(f"Materialized WAV files: {len(records) - len(pointers)}")
        print(f"Source groups crossing original splits: {len(leakage)}")
        print(f"Source groups carrying conflicting labels: {len(label_conflicts)}")
        if leakage:
            print("The trainer will replace the supplied split with a deterministic group-aware split.")
    return 2 if args.strict and (pointers or leakage or label_conflicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
