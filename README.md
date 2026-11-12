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
        users, vehicles, assignments, sessions,     telemetry_events, sensor_events,
        audio metadata, alerts, alert_actions,      audio_analysis_results, device_logs
        device_status

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
│       ├── api/routes/    auth users vehicles audio alerts telemetry analytics
│       ├── core/          config security dependencies errors
│       ├── db/            postgres mongodb init_db
│       ├── models/        user vehicle audio alert device_status   (PostgreSQL)
│       ├── schemas/       Pydantic request/response models
│       ├── repositories/  user vehicle audio alert (PG), telemetry analysis (MongoDB)
│       └── services/      auth vehicle audio alert telemetry analytics audio_classifier
└── docs/database-design.md
```

## PostgreSQL responsibilities

Relational, transactional data: `users`, `user_sessions` (revocable login sessions), `vehicles`,
`vehicle_assignments`, `audio_records` (metadata + storage URL), `alerts`, `alert_actions`
(audit trail) and `device_status` (latest health snapshot per vehicle).

## MongoDB responsibilities

High-volume / flexible data: `telemetry_events` (GPS + vehicle readings), `sensor_events`,
`audio_analysis_results` (ML output) and `device_logs`. Vehicles are referenced by their
`vehicle_code` (e.g. `CAR-1024`).

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
| `DEMO_DRIVER_PASSWORD` | Optional: password of the demo driver the seed creates (never printed) |
| `DEVICE_HEARTBEAT_TIMEOUT_SECONDS`, `LOW_BATTERY_WARNING_PERCENT` | Device lifecycle tuning (defaults 300 and 15) |

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

## Cloud development databases (Neon/Supabase + MongoDB Atlas)

The same code runs against local databases or shared **development** cloud databases; only `.env` changes.
**Never commit `.env`** (it is git-ignored) and never put real credentials in `.env.example`, code, issues or chat.
Use development-only credentials and a development-only database, never production ones.

### 1. PostgreSQL on Neon (or Supabase)
1. Create a project at <https://neon.tech> (or <https://supabase.com>) and a database named `smart_car_dev`.
2. Create a role for each teammate (Neon: *Roles* tab; Supabase: SQL editor `CREATE ROLE ... LOGIN PASSWORD '...'`) with rights on `smart_car_dev` only.
3. Copy the connection string and set `POSTGRES_URL`. `postgres://`, `postgresql://` and `?sslmode=require` are accepted and converted automatically for asyncpg (`channel_binding` is dropped). Pooler hosts (Neon `-pooler`, Supabase pooler) are detected and prepared-statement caching is turned off.
4. Access: both providers require TLS and a password. If you enable IP allow-lists (Neon *IP Allow*; Supabase *Network restrictions*), list only your team's addresses.
5. Run migrations (use a **direct** (non-pooled) host if your provider recommends it for DDL): `alembic upgrade head`.

### 2. MongoDB Atlas
1. Create a free cluster at <https://www.mongodb.com/atlas> (project *smart-car-dev*).
2. *Database Access* → add one database user per teammate, role `readWrite` on database `smart_car_dev` only (not Atlas admin).
3. *Network Access* → add each teammate's current IP (or a VPN/office range). **Do not use `0.0.0.0/0`.**
4. *Connect* → *Drivers* → copy the `mongodb+srv://...` string into `MONGODB_URL` and set `MONGODB_DATABASE=smart_car_dev`. SRV URLs need `dnspython`, which is in `requirements.txt`.
5. Collections and indexes are created automatically at API start (or `python -m app.db.init_db`).

### 3. URL-encode special characters in passwords
Characters such as `@ : / ? # % & + =` or spaces break a URL unless encoded. Encode only the password:
```bash
python3 -c "import urllib.parse,getpass; print(urllib.parse.quote(getpass.getpass(), safe=''))"
```
Paste the output in place of `CHANGE_ME`. (Use `quote`, not `quote_plus`: SQLAlchemy does not decode `+` as a space.)
Simplest alternative: generate a password with letters and digits only.

### 4. Configure after cloning
```bash
git clone <repo> && cd smart-car-data-management-fullstack/backend
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env        # then fill in YOUR OWN credentials, ask the team lead for host names
python -m app.db.check_connections   # verifies PostgreSQL + MongoDB (prints no secrets)
alembic upgrade head                 # creates/updates tables; never drops data
python -m app.db.seed_demo           # optional demo data (see below)
uvicorn app.main:app --reload --port 8000
# new terminal
cd frontend && python3 -m http.server 5173
```
Each teammate keeps their own local `.env` and their own database users, so access can be revoked per person. Set a unique `JWT_SECRET` (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`). Share the one development database only for development; production gets separate databases and credentials.

### 5. MongoDB Compass
Open Compass → *New connection* → paste the same `mongodb+srv://...` string (with your own user) → *Connect*. Browse `smart_car_dev` (`telemetry_events`, `audio_analysis_results`, `sensor_events`, `device_logs`). Your IP must be on the Atlas allow-list.

### What the seed script writes
`python -m app.db.seed_demo` writes to **both** databases: PostgreSQL (users `driver@example.com`, vehicles, assignments, device status, alerts, alert actions) and MongoDB (telemetry, sensor events, device logs). It is idempotent: existing vehicles/users are left untouched, and telemetry and alerts are only added to vehicles that have none, so re-running (or a teammate running it against the shared database) creates no duplicates. It refuses to run unless `ENVIRONMENT=development`. The one-time driver password is printed only when the user is first created.

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
| Vehicles | `POST /vehicles`, `GET /vehicles`, `GET /vehicles/{id}`, `PATCH /vehicles/{id}`, `DELETE /vehicles/{id}` (soft delete), `POST/GET /vehicles/{id}/devices`, `PATCH /vehicles/{id}/controls` (acts on the vehicle's default device), `GET /vehicles/{id}/logs` (device activity) |
| Devices | `POST /devices` (admin), `GET /devices?vehicle_id=&status=&include_retired=`, `GET/PATCH /devices/{id}` (PATCH admin), `DELETE /devices/{id}` (admin, soft removal), `PUT /devices/{id}/configuration`, `POST /devices/{id}/rotate-key` (admin), `GET/PATCH /devices/{id}/status`, `POST /devices/{id}/recording/start\|stop`, `POST /devices/{id}/monitoring/pause\|resume`, `POST /devices/{id}/heartbeat`, `GET /devices/{id}/heartbeats?start=&end=&limit=&offset=`, `POST /devices/{id}/classify-audio` (WAV simulation) |
| Audio | `POST /audio`, `GET /audio`, `GET /audio/{id}`, `PATCH /audio/{id}/status` |
| Alerts | `POST /alerts`, `GET /alerts`, `GET /alerts/{id}`, `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve` |
| Telemetry | `POST /telemetry/{vehicle}`, `GET /telemetry/{vehicle}`, `GET /telemetry/{vehicle}/latest` |
| Analytics | `GET /analytics/summary`, `GET /analytics/events-over-time`, `GET /analytics/events-by-type` |
| System | `GET /health` (no prefix, public) |

Notes: `{id}` / `{vehicle}` accept a UUID or a vehicle code such as `CAR-1024`. Missing or
invalid tokens return `401`. Non-admin users only see vehicles they own or are assigned to
(others return `404`); acknowledging/resolving alerts is **administrator-only** (`403` otherwise).

## Devices, heartbeats and soft deletion

A vehicle has **many IoT devices** (`devices` table). Device-level controls (monitoring mode, audio capture,
recording) and lifecycle live on the device; the old per-vehicle `device_status` row is kept for the vehicle
health snapshot (engine/GPS/microphone) and for vehicles that have no registered device yet.
`vehicle_code` (unique, e.g. `CAR-1024`) and `vehicle_type` are retained. Optional unique `vin` and
`license_plate` columns were added without changing existing rows; the management UI requires both for new vehicles.

**Lifecycle statuses**: `PENDING` (registered, no heartbeat yet) → `ACTIVE` (recent heartbeats) / `WARNING`
(heartbeat `warning`/`error` or battery < 15 %) → `DELAYED` (no heartbeat for `DEVICE_HEARTBEAT_TIMEOUT_SECONDS`,
default **300 s**) ; `DISABLED` (administrator turned it off) and `RETIRED` (permanently removed).

| Rule | Behaviour |
| --- | --- |
| Heartbeat timeout | ACTIVE/WARNING devices not heard from within the timeout become DELAYED (evaluated on read); the next heartbeat restores ACTIVE/WARNING |
| DISABLED | Rejects control commands (`409`); heartbeats are recorded but never change the status; only an administrator re-enables it |
| RETIRED | Rejects commands, heartbeats and telemetry (`409`); still listed with `include_retired=true`; history kept; cannot be revived |
| Soft removal | `DELETE /devices/{id}` sets `RETIRED`, `is_active=false`, `removed_at`; no row is deleted |
| Vehicle delete | `DELETE /vehicles/{id}` sets `is_active=false`, `deleted_at`; devices, heartbeats, alerts, audio and telemetry are all kept. The `vehicle_code` stays reserved. Administrators can list them with `GET /vehicles?include_inactive=true`. Foreign keys from devices, heartbeats, alerts and audio records use `ON DELETE RESTRICT` |

**Registration**: administrators call `POST /devices` with `vehicle_id` (UUID or code), `hardware_id` (unique,
4-63 chars of `A-Za-z0-9:_.-`) and `device_type` (`microphone`, `audio_sensor`, `gps`, `imu`, `camera`, `gateway`,
`other`). The response includes a one-time `device_key` (only its SHA-256 hash is stored; `POST /devices/{id}/rotate-key` issues a new one).

**Heartbeats** authenticate with the `X-Device-Key` header (devices) or a Bearer token (signed-in users with access to the
vehicle); the body `hardware_id` must match. Every heartbeat is stored in `device_heartbeats` (history is never overwritten).

```bash
curl -X POST localhost:8000/api/v1/devices -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"vehicle_id":"CAR-1024","hardware_id":"MIC-1024-Z9","device_type":"microphone"}'
curl -X POST localhost:8000/api/v1/devices/$DEVICE_ID/heartbeat -H "X-Device-Key: $DEVICE_KEY" \
  -H 'content-type: application/json' -d '{"hardware_id":"MIC-1024-Z9","battery_level":82,"signal_strength":-61}'
curl "localhost:8000/api/v1/devices/$DEVICE_ID/heartbeats?limit=20" -H "Authorization: Bearer $TOKEN"
curl -X POST localhost:8000/api/v1/devices/$DEVICE_ID/recording/start -H "Authorization: Bearer $TOKEN"
```

Vehicle-level `PATCH /vehicles/{id}/controls` still works and acts on the vehicle's default device (the first
non-retired one, online devices first). Telemetry may include a `device_id`; MongoDB documents then also carry
`device_id` and `hardware_id` (older documents only have `vehicle_id`).

**Migration and seed** (`alembic upgrade head` applies the complete chain through `0006`): `0004` adds the rich
device and heartbeat tables, controls, soft deletion, and legacy-device backfill; `0005` makes that model compatible
with the shared cloud schema; `0006` adds vehicle VIN/license identifiers and simulated-alert provenance. Nothing is
deleted by these upgrades.

```bash
cd backend && alembic upgrade head && python -m app.db.seed_demo
```

The seed adds devices of every status plus heartbeat history, is idempotent (devices are keyed by `hardware_id`),
adopts the migration's legacy device as each vehicle's primary unit, and never prints passwords. Set
`DEMO_DRIVER_PASSWORD` in your `.env` if you also want the `driver@example.com` demo account.

> The cloud PostgreSQL and MongoDB URLs live only in your local `backend/.env`. **Never commit or share
> `backend/.env`**; do not paste connection strings into issues, chat or logs.

## Audio → alert workflow

1. `POST /audio` creates the audio metadata (PostgreSQL `audio_records`).
2. The object-storage URL (`s3://…` / `https://…`) is saved with it. Clients upload the file to
   S3/MinIO themselves; no audio bytes are stored in either database.
3. `services/audio_classifier.classify_audio` processes the file using the configured mock or trained baseline.
4. The result is saved in MongoDB `audio_analysis_results`.
5. If `confidence >= 0.80` **and** the class is not `normal`, a PostgreSQL alert is created.
6. The alert shows up in the dashboard (active alerts, recent events, Alert Details page).
7. An administrator acknowledges or resolves it.
8. Every alert action (`created`, `acknowledged`, `resolved`) is stored in `alert_actions`.

If classification fails, the audio record is kept with `processing_status = failed`.

The management UI also accepts a PCM WAV file at `POST /devices/{id}/classify-audio`. It records the prediction in
MongoDB and creates a PostgreSQL alert when the confidence threshold is met. These records have
`is_simulation=true`, so demo data remains distinguishable from production detections.

## Run the tests

```bash
cd backend && source .venv/bin/activate
pytest -q
ruff check . && ruff format --check .      # lint / formatting
```

Tests use an in-memory SQLite database and an in-memory MongoDB mock injected through
FastAPI dependency overrides, so they never connect to (or delete) a real database.

## Future ML model integration

`backend/app/services/audio_classifier.py` defaults to a deterministic **mock classifier** so the
pipeline works without an artifact. An optional scikit-learn baseline can be trained and selected with
`AUDIO_CLASSIFIER_BACKEND=sklearn`; its dataset audit, training, evaluation, and configuration are documented in
[`docs/audio-model.md`](docs/audio-model.md). The baseline is suitable for a class demo, but it is **not a validated
production safety model**. To integrate a stronger model (PyTorch, TensorFlow, YAMNet, …), keep the interface
`classify_audio(audio_path) -> AudioClassificationResult`, download/stream the file from the
storage URL, run inference, and update `MODEL_NAME` / `MODEL_VERSION`. The rest of the system is
unchanged. For heavy models, move step 3 of the workflow to a background worker/queue.

## Known limitations

- Device controls (monitoring mode, audio capture, recording) are saved to PostgreSQL and logged
  to MongoDB, but there is no real device agent yet, so they do not command physical hardware.
  Uptime is real: it counts from the moment a vehicle's first telemetry arrives (`device_status.online_since`)
  and resets when the vehicle is set to a non-connected status.
- The Event Type filter on the Analytics page filters the table and donut client-side only.
- Audio is classified synchronously inside `POST /audio`.
- "Forgot password?" shows a message only; there is no password-reset flow yet.
