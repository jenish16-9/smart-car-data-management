# Smart Car Data Management

Monitors smart vehicles: cabin audio, engine noise, glass-break sounds, GPS location,
telemetry, device status, alerts and analytics.

- **Frontend** – static HTML / CSS / vanilla JS dashboard (`frontend/`).
- **Backend** – FastAPI + SQLAlchemy 2 (async) + Motor, JWT auth (`backend/`).
- **Databases** – PostgreSQL for relational data, MongoDB for high-volume data.

## System architecture

```text
 Browser (frontend/)  ──HTTP/JSON + JWT──▶  FastAPI (backend/app)
                                              │  routes → services → repositories
                          ┌───────────────────┴───────────────────┐
                          ▼                                       ▼
                  PostgreSQL (SQLAlchemy)                 MongoDB (Motor)
        users, vehicles, devices, assignments,      telemetry_events, sensor_events,
        audio metadata, alerts, alert_actions,      audio_analysis_results, device_logs
        device_status                               device_heartbeats

 Audio files themselves live in object storage (S3 / MinIO). Only the URL + metadata is stored.
```

Layering: **routes** (HTTP only) → **services** (business rules, access control, workflow) →
**repositories** (queries). Details and diagrams: [docs/database-design.md](docs/database-design.md).

## Folder structure

```text
├── frontend/
│   ├── index.html  styles.css  app.js  api.js      # UI + API client (falls back to sample data)
├── backend/
│   ├── .env.example  requirements.txt  alembic.ini  pytest.ini  pyproject.toml
│   ├── alembic/                       # migrations (versions/0001_initial_schema.py)
│   ├── tests/                         # pytest suite (isolated, in-memory databases)
│   └── app/
│       ├── main.py
│       ├── api/routes/    auth users vehicles devices audio alerts telemetry analytics
│       ├── core/          config security dependencies errors
│       ├── db/            postgres mongodb init_db
│       ├── models/        user vehicle device audio alert device_status   (PostgreSQL)
│       ├── schemas/       Pydantic request/response models
│       ├── repositories/  user vehicle audio alert (PG), telemetry analysis (MongoDB)
│       └── services/      auth vehicle audio alert telemetry analytics audio_classifier
└── docs/database-design.md
```

## PostgreSQL responsibilities

Relational, transactional data: `users`, `user_sessions` (revocable login sessions), `vehicles`,
`vehicle_assignments`, `devices` (identity, configuration and current state), `audio_records`
(metadata + storage URL), `alerts`, `alert_actions` (audit trail) and `device_status` (latest
vehicle-level health snapshot).

## MongoDB responsibilities

High-volume / flexible data: `telemetry_events` (GPS + vehicle readings), `sensor_events`,
`audio_analysis_results` (ML output), `device_logs` and append-only `device_heartbeats`. Vehicles
are referenced by their `vehicle_code` (e.g. `CAR-1024`); heartbeat documents also reference the
PostgreSQL device UUID as a string.

## Environment setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit the values
```

| Variable | Purpose |
| --- | --- |
| `APP_NAME`, `API_PREFIX`, `ENVIRONMENT` | App metadata; `ENVIRONMENT=development` enables the dev login seed |
| `FRONTEND_ORIGIN` | Allowed CORS origin(s), comma-separated (default `http://localhost:5173`) |
| `POSTGRES_URL` | `postgresql+asyncpg://user:password@host:5432/smart_car` |
| `MONGODB_URL`, `MONGODB_DATABASE` | MongoDB connection |
| `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Token signing. `JWT_SECRET` is **required** unless `ENVIRONMENT=development` |
| `DEV_ADMIN_EMAIL`, `DEV_ADMIN_PASSWORD` | Development administrator, created at startup (development only) |
| `DEVICE_DELAYED_AFTER_SECONDS`, `DEVICE_OFFLINE_AFTER_SECONDS` | Connectivity thresholds (defaults: 90 / 300 seconds) |

`.env` is git-ignored. Use a strong random `JWT_SECRET` anywhere real.

## PostgreSQL setup

Not installed? On macOS: `brew install postgresql@16 && brew services start postgresql@16`
(Linux: `sudo apt install postgresql`; or run the `postgres` Docker image). Then:

```bash
createdb smart_car          # or: psql -c 'CREATE DATABASE smart_car;'
```

Set `POSTGRES_URL` in `.env` to match your user and password.

## MongoDB setup

macOS: `brew tap mongodb/brew && brew install mongodb-community && brew services start mongodb-community`
(Linux: follow the MongoDB install guide; or run the `mongo` Docker image). The database and
collections are created on first write, and indexes at API startup (`python -m app.db.init_db`
does it on demand).

## Alembic migrations

```bash
cd backend
alembic upgrade head                                  # create / update PostgreSQL tables
alembic revision --autogenerate -m "describe change"  # after changing models
alembic downgrade -1                                  # roll back one revision
```

The database URL comes from `POSTGRES_URL`.

## Start the backend

```bash
cd backend && source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>. Health check: `GET /health`.

## Start the frontend

```bash
cd frontend
python3 -m http.server 5173
```

Open <http://localhost:5173>. The frontend calls `http://localhost:8000/api/v1` (override with
`window.API_BASE_URL` before `app.js` loads). **Signing in always requires a registered account and a reachable backend.** If the backend becomes unreachable after sign-in, the UI keeps
working on built-in sample data and shows a notice at the top of the page.

## Demo data (10 vehicles)

```bash
cd backend && source .venv/bin/activate
python -m app.db.seed_demo        # development only; safe to re-run
```

Creates CAR-1024 … CAR-1033 with different types, statuses (connected / disconnected / maintenance),
GPS positions, uptime, battery, engine/microphone states, MongoDB telemetry and alerts (only where
it makes sense, e.g. CAR-1026 and CAR-1028 have none). Existing vehicles are never overwritten.
It also creates a non-admin `driver@example.com` assigned to CAR-1024 … CAR-1029 to demonstrate
access control; its random password is printed once when it is created.

## Development login

```text
email:    admin@example.com
password: admin123
```

Created at startup from `DEV_ADMIN_EMAIL` / `DEV_ADMIN_PASSWORD` in `.env` when
`ENVIRONMENT=development` (copy `.env.example`). Never use these in a real deployment.
Self-registration always creates a regular `user`.

## API endpoints

All under `/api/v1` and protected by a `Bearer` JWT unless marked public.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register` (public), `POST /auth/login` (public), `POST /auth/logout`, `GET /auth/me` |
| Users | `GET /users/me`, `PATCH /users/me` |
| Vehicles | `POST /vehicles`, `GET /vehicles`, `GET /vehicles/{id}`, `PATCH /vehicles/{id}`, `DELETE /vehicles/{id}`, `POST /vehicles/{id}/devices`, `GET /vehicles/{id}/devices`, `PATCH /vehicles/{id}/controls`, `GET /vehicles/{id}/logs` |
| Devices | `GET /devices/{id}`, `PATCH /devices/{id}`, `PUT /devices/{id}/configuration`, `POST /devices/{id}/heartbeat`, `GET /devices/{id}/heartbeats`, `DELETE /devices/{id}` |
| Audio | `POST /audio`, `GET /audio`, `GET /audio/{id}`, `PATCH /audio/{id}/status` |
| Alerts | `POST /alerts`, `GET /alerts`, `GET /alerts/{id}`, `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve` |
| Telemetry | `POST /telemetry/{vehicle}`, `GET /telemetry/{vehicle}`, `GET /telemetry/{vehicle}/latest` |
| Analytics | `GET /analytics/summary`, `GET /analytics/events-over-time`, `GET /analytics/events-by-type` |
| System | `GET /health` (no prefix, public) |

Notes: `{id}` / `{vehicle}` accept a UUID or a vehicle code such as `CAR-1024`. Missing or
invalid tokens return `401`. Non-admin users only see vehicles they own or are assigned to
(others return `404`); acknowledging/resolving alerts is **administrator-only** (`403` otherwise).

## Vehicle and IoT device workflow

Run `alembic upgrade head` to apply migration `0004_iot_devices`. Device identity, ownership,
configuration, current lifecycle state and last-heartbeat time are stored in PostgreSQL. Full
heartbeat history is append-only in MongoDB. Deleting a device is a soft removal: it is retired and
hidden from its vehicle list while its PostgreSQL row and MongoDB history remain. Deleting a vehicle
also detaches and retires its devices before the existing vehicle cleanup runs.

```bash
# Register a device under a vehicle (use an access token from /auth/login)
curl -X POST http://localhost:8000/api/v1/vehicles/CAR-1024/devices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"hardware_id":"AUD-EDGE-0001","name":"Cabin AudioGuard","firmware_version":"1.0.0"}'

# First valid heartbeat changes PENDING to ONLINE
curl -X POST http://localhost:8000/api/v1/devices/DEVICE_UUID/heartbeat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"health":"HEALTHY","metrics":{"batteryPercent":88}}'
```

Connectivity states are `PENDING`, `ONLINE`, `WARNING`, `DELAYED`, `OFFLINE`, `DISABLED`, and
`RETIRED`. State is refreshed when a device is read: after the configured thresholds, a missing
heartbeat changes an active device to `DELAYED` and then `OFFLINE`. A valid heartbeat restores an
active device to `ONLINE` (or `WARNING` for a health warning), but never reactivates `DISABLED` or
`RETIRED`. Retirement is terminal and rejects configuration changes and new heartbeats.

## Audio → alert workflow

1. `POST /audio` creates the audio metadata (PostgreSQL `audio_records`).
2. The object-storage URL (`s3://…` / `https://…`) is saved with it. Clients upload the file to
   S3/MinIO themselves; no audio bytes are stored in either database.
3. `services/audio_classifier.classify_audio` processes the file.
4. The result is saved in MongoDB `audio_analysis_results`.
5. If `confidence >= 0.80` **and** the class is not `normal`, a PostgreSQL alert is created.
6. The alert shows up in the dashboard (active alerts, recent events, Alert Details page).
7. An administrator acknowledges or resolves it.
8. Every alert action (`created`, `acknowledged`, `resolved`) is stored in `alert_actions`.

If classification fails, the audio record is kept with `processing_status = failed`.

## Run the tests

```bash
cd backend && source .venv/bin/activate
pytest -q
ruff check . && ruff format --check .      # lint / formatting
```

Tests use an in-memory SQLite database and an in-memory MongoDB mock injected through
FastAPI dependency overrides, so they never connect to (or delete) a real database.

## Future ML model integration

`backend/app/services/audio_classifier.py` currently contains a **mock classifier**. It does
not analyse audio: it returns a deterministic placeholder label from a hash, so the pipeline can
be built and tested. **It is not a trained model and must not be used for real detection.** The
replaceable `AudioClassifier` protocol accepts `AudioClassificationInput` containing exactly one
storage URI, raw audio byte sequence, or extracted numeric feature map. It returns an
`AudioClassificationResult` with `event_type`, `confidence`, `model_version`, and a timezone-aware
`processing_timestamp` (plus model name and measured processing time for persistence/monitoring).

The supported alert categories are `emergency_vehicle_siren`, `glass_breaking`, `screaming`,
`gunshot`, `crash`, `tire_skidding`, and `abnormal_engine_noise`; `normal` is the negative outcome.
To integrate YAMNet or another real model, implement `AudioClassifier`, validate its AudioSet-to-
application label mapping, and replace `default_classifier`. For heavy models, move inference to a
background worker/queue. Accuracy claims require a labeled, held-out evaluation set representing
real vehicle-cabin and road-noise conditions.

The repository also includes an optional, trainable CPU baseline with leakage-safe dataset auditing,
feature extraction, evaluation, artifact loading, and fail-closed configuration. See
[docs/audio-model.md](docs/audio-model.md). Install it with `pip install -r backend/requirements-ml.txt`;
the default application dependency set remains lightweight and continues to use the mock backend.

## Known limitations

- Device controls (monitoring mode, audio capture, recording) are saved to PostgreSQL and logged
  to MongoDB, but there is no real device agent yet, so they do not command physical hardware.
  Uptime is real: it counts from the moment a vehicle's first telemetry arrives (`device_status.online_since`)
  and resets when the vehicle is set to a non-connected status.
- Connectivity timeout state is calculated on device reads; there is no background scheduler that
  proactively writes `DELAYED` or `OFFLINE` while nobody is querying the device.
- The Event Type filter on the Analytics page filters the table and donut client-side only.
- Audio is classified synchronously inside `POST /audio`.
- "Forgot password?" shows a message only; there is no password-reset flow yet.
