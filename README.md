# Smart Car Data Management

FastAPI and static-JavaScript starter for the Smart Car AudioGuard dashboard.
The first device-management vertical slice supports authenticated vehicle
registration, device registration under an owned vehicle, and API-backed list
and detail views.

## Structure

```text
smart-car-data-management-fullstack/
├── frontend/              # Current dashboard UI
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── api.js              # Fetch wrapper for the backend
├── backend/               # FastAPI service layer
│   ├── app/
│   │   ├── api/routes/    # HTTP endpoints
│   │   ├── core/          # Settings and security
│   │   ├── models/        # Database models
│   │   ├── schemas/       # Request/response contracts
│   │   ├── services/      # Business logic
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
└── README.md
```

## Backend setup

Python 3.11 or newer is recommended.

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env  # Windows; use `cp` on macOS/Linux
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

SQLite is the development default. The database team can supply a PostgreSQL
SQLAlchemy URL through `DATABASE_URL` without changing the service or route
layers. Do not commit `.env` or database files.

The API documentation is at `http://localhost:8000/docs`.

## Run the frontend

From `frontend/`, start any static server. For example:

```bash
python3 -m http.server 5173
```

Open `http://localhost:5173`.

The development login is `admin@example.com` / `admin123`. The current token
adapter is development-only and must be replaced by the shared identity provider
before production use.

## Vehicle and device API examples

Obtain the development token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}'
```

Register a vehicle, replacing `$TOKEN` with the returned token:

```bash
curl -X POST http://localhost:8000/api/v1/vehicles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"vin":"1HGBH41JXMN109186","name":"Family Car","make":"Honda","model":"Civic","year":2024}'
```

Register a device, replacing `$VEHICLE_ID`:

```bash
curl -X POST http://localhost:8000/api/v1/vehicles/$VEHICLE_ID/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hardware_id":"AUD-EDGE-0001","name":"Cabin AudioGuard","firmware_version":"1.0.0"}'
```

New devices begin in `PENDING`. The current management API includes:

- `PATCH /api/v1/vehicles/{vehicleId}` to update or deactivate a vehicle
- `DELETE /api/v1/vehicles/{vehicleId}` for soft removal
- `PATCH /api/v1/devices/{deviceId}` to update, disable, or retire a device
- `PUT /api/v1/devices/{deviceId}/configuration` to replace validated settings
- `POST /api/v1/devices/{deviceId}/heartbeat` to record connectivity and health
- `GET /api/v1/devices/{deviceId}/heartbeats` for recent heartbeat history
- `DELETE /api/v1/devices/{deviceId}` for soft removal with retained history

Connectivity thresholds are configured with
`DEVICE_DELAYED_AFTER_SECONDS` (default 90) and
`DEVICE_OFFLINE_AFTER_SECONDS` (default 300). A healthy heartbeat moves a
non-disabled device to `ONLINE`; a health warning moves it to `WARNING`.
Elapsed time moves it to `DELAYED` and then `OFFLINE`. Heartbeats are recorded
for `DISABLED` devices but never reactivate them. `RETIRED` is terminal and
rejects new heartbeats and configuration changes.

Vehicle and device DELETE operations are soft removals. They disappear from
active inventory while their records and heartbeat history remain available
for auditing and future database integration.

## Tests

From `backend/` with the virtual environment active:

```bash
ruff format --check app tests alembic
ruff check app tests alembic
mypy app
pytest -q
```

The integration tests use an isolated in-memory SQLite database and cover the
vehicle/device workflow, authentication, ownership isolation, validation,
invalid associations, duplicate hardware IDs, settings, lifecycle transitions,
heartbeat connectivity, terminal retirement, and retained history.

The frontend is intentionally dependency-free, so it has no bundling/build
step. Validate its JavaScript modules with `node --check frontend/app.js` and
`node --check frontend/api.js` from the repository root.

Alerts and analytics remain backed by the original mock data. Audio simulation,
classifier interfaces, model training, and inference are intentionally deferred
to the audio/ML phase.


