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

New devices begin in `PENDING`. Heartbeat-driven connectivity and device
lifecycle transitions are planned for the next vertical slice.

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
invalid associations, and duplicate hardware IDs.

The frontend is intentionally dependency-free, so it has no bundling/build
step. Validate its JavaScript modules with `node --check frontend/app.js` and
`node --check frontend/api.js` from the repository root.

Alerts and analytics remain backed by the original mock data. No production ML
model is included in this slice.


