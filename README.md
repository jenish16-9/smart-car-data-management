# Smart Car Data Management

Full-stack starter for the Smart Car Data Management dashboard.

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

## Run the frontend

From `frontend/`, start any static server. For example:

```bash
python3 -m http.server 5173
```

Open `http://localhost:5173`.

## Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API documentation is available at `http://localhost:8000/docs`.

The current frontend is intentionally kept as a simple static UI so it can be
run immediately. The backend uses in-memory sample data for now; replace the
repository/service functions with PostgreSQL and authentication when you begin
the production implementation.

The backend test login is `admin@example.com` with password `admin123`.


