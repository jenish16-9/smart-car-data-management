import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import alerts, analytics, audio, auth, telemetry, users, vehicles
from app.core.config import settings
from app.core.errors import ServiceError
from app.db.init_db import init_db
from app.db.mongodb import close_mongo
from app.db.postgres import dispose_engine

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await init_db()
    except Exception as exc:  # keep the API (and /health) up so the problem is visible
        logger.warning("Database initialisation failed (%s). Is PostgreSQL/MongoDB running and migrated?", exc)
    yield
    await dispose_engine()
    close_mongo()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=headers)


for module in (auth, users, vehicles, audio, alerts, telemetry, analytics):
    app.include_router(module.router, prefix=settings.api_prefix)


@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok"}
