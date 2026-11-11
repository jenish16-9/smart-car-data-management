# Audio model development

## Current status

The application has two interchangeable classifier backends:

- `mock` (default): deterministic workflow testing only; it does not inspect audio.
- `sklearn`: a trained CPU baseline using log-mel, temporal energy, zero-crossing, and spectral
  summary features followed by class-balanced logistic regression.

No production-accuracy claim is made. A model artifact is deliberately not committed. Training
creates the artifact and a JSON evaluation report in the ignored `backend/ml_artifacts/` directory.

## Dataset audit (November 11, 2026)

The supplied `dataset/` directory currently contains Git LFS pointer text rather than WAV bytes.
The audit found 8,553 mapped pointers and zero materialized mapped WAV files, so real training
cannot run until the dataset's original LFS objects are fetched. The copied folder is not itself a
Git repository and has no remote, so `git lfs pull` cannot work inside it. Re-clone the original
dataset repository with Git LFS enabled, or ask its owner to provide the materialized audio files.

The supplied split also has 460 source groups crossing train/validation/test boundaries because
augmented derivatives of the same recording appear in multiple splits. Evaluating those splits
directly would leak source audio into the test set and overstate accuracy. The trainer ignores the
supplied split assignment and deterministically reassigns complete source groups 70/15/15 within
each label.

Mapped labels:

| Dataset folder | Application event type |
| --- | --- |
| `collision_sounds`, `car_crash` | `crash` |
| `emergency_sirens` | `emergency_vehicle_siren` |
| `glass_breaking` and its backup folder | `glass_breaking` |
| `human_scream` | `screaming` |
| `environmental_sounds`, `road_traffic` | `normal` |

`alert_sounds` is excluded because its semantic meaning is not documented and it cannot safely be
assigned to one of the required categories. The dataset has no explicitly labeled `gunshot`,
`tire_skidding`, or `abnormal_engine_noise` samples. The resulting baseline therefore cannot claim
to recognize those three categories; the training report lists them as unsupported.

## Setup and audit

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe -m scripts.audit_audio_dataset ..\..\dataset --json
```

After replacing the pointers with real WAV files, the audit should report a nonzero
`materialized_wav_count` and `git_lfs_pointer_count: 0`.

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
