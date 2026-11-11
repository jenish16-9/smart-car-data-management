# Audio model development

## Current status

The application has two interchangeable classifier backends:

- `mock` (default): deterministic workflow testing only; it does not inspect audio.
- `sklearn`: a trained CPU baseline using log-mel, temporal energy, zero-crossing, and spectral
  summary features followed by class-balanced logistic regression.

No production-accuracy claim is made. A model artifact is deliberately not committed. Training
creates the artifact and a JSON evaluation report in the ignored `backend/ml_artifacts/` directory.

## Dataset audit (November 11, 2026)

The professor-provided ZIP contained Git LFS pointer text rather than WAV bytes. The original public
repository was identified as `saimsheikh123/Smart-Car-Alert-Model`; a fresh Git LFS clone
materialized all 9,877 tracked WAV files. Of those, 8,553 map to documented application labels,
1,307 are in the ambiguous `alert_sounds` folder, and 17 are quarantined by the source project.

The supplied split has 460 source groups crossing train/validation/test boundaries because
augmented derivatives of the same recording appear in multiple splits. Evaluating those splits
directly would leak source audio into the test set and overstate accuracy. The trainer ignores the
supplied split assignment and deterministically reassigns complete source groups 70/15/15 within
each label.

Mapped labels:

| Dataset folder | Application event type |
| --- | --- |
| `car_crash`; non-glass files in `collision_sounds` | `crash` |
| Explicit glass/shatter/break sources in `collision_sounds` | `glass_breaking` |
| `emergency_sirens` | `emergency_vehicle_siren` |
| `glass_breaking` and its backup folder | `glass_breaking` |
| `human_scream` | `screaming` |
| `environmental_sounds`, `road_traffic` | `normal` |

`alert_sounds` is excluded because its semantic meaning is not documented and it cannot safely be
assigned to one of the required categories. The dataset has no explicitly labeled `gunshot`,
`tire_skidding`, or `abnormal_engine_noise` samples. The resulting baseline therefore cannot claim
to recognize those three categories; the training report lists them as unsupported.

The source project's `collision_sounds` class merged vehicle impacts with glass audio: more than
1,000 filenames in that folder explicitly identify glass, shattering, or breaking. For this
application, clearly named glass sources and ESC-50 class-39 sources are restored to
`glass_breaking`. Four remaining descriptive source groups carrying contradictory labels are
excluded. Coincidentally identical numeric filenames from unrelated source datasets are not treated
as conflicts.

## Baseline result

The first cleaned, group-safe run trained on 4,259 examples, selected regularization using 910
validation examples, and evaluated once on 865 held-out examples:

| Metric | Result |
| --- | ---: |
| Accuracy | 86.82% |
| Balanced accuracy | 84.84% |
| Macro-F1 | 0.844 |

| Class | Precision | Recall | F1 | Test examples |
| --- | ---: | ---: | ---: | ---: |
| Crash | 0.639 | 0.802 | 0.711 | 86 |
| Emergency vehicle siren | 0.841 | 0.775 | 0.807 | 191 |
| Glass breaking | 0.897 | 0.766 | 0.827 | 137 |
| Normal/background | 0.907 | 0.996 | 0.949 | 235 |
| Screaming | 0.947 | 0.903 | 0.924 | 216 |

These metrics describe only those five categories and this dataset. They are not production or
real-car accuracy claims. The ignored local report `backend/ml_artifacts/audio-baseline.metrics.json`
contains the full confusion matrix and per-class report.

## Setup and audit

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe -m scripts.audit_audio_dataset ..\..\dataset --json
```

The LFS clone should report a nonzero `materialized_wav_count` and
`git_lfs_pointer_count: 0`.

## Train and evaluate

```powershell
.\.venv\Scripts\python.exe -m scripts.train_audio_model ..\..\dataset `
  --output ml_artifacts\audio-baseline.joblib
```

The trainer:

1. rejects LFS pointers and malformed/non-PCM WAVs;
2. groups all augmented derivatives with their source recording;
3. limits each source to 12 derivatives to reduce augmentation imbalance;
4. extracts 16 kHz, three-second acoustic features;
5. chooses regularization strength using only the validation groups;
6. refits on train + validation and reports accuracy, balanced accuracy, macro-F1, per-class
   precision/recall/F1, and a confusion matrix on untouched test groups;
7. saves both the joblib artifact and a human-readable `.metrics.json` report.

## Enable the trained backend

Set these values in the uncommitted `backend/.env` file:

```text
AUDIO_CLASSIFIER_BACKEND=sklearn
AUDIO_MODEL_PATH=ml_artifacts/audio-baseline.joblib
```

If a configured artifact cannot be loaded, the application fails closed for classification rather
than silently returning mock predictions. The trained adapter accepts PCM WAV bytes or a local path.
Cloud object URLs must be downloaded by the storage integration and passed as bytes; remote fetching
is intentionally not embedded in the model.

## Next model iteration

Use a pretrained AudioSet encoder such as YAMNet after the data is materialized. Compare it against
this baseline using the exact same group-safe test groups. Add licensed, independently sourced data
for gunshots, tire skidding, and abnormal engine noise, and include difficult negative cabin sounds
(speech, music, horns, doors, rain, wind, and road vibration). Thresholds must be selected on
validation data and reported per class; a single global accuracy number is insufficient for a
safety-related alert system.
