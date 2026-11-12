"""MongoDB (Motor) connection layer."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.core.config import settings

TELEMETRY = "telemetry_events"
AUDIO_ANALYSIS = "audio_analysis_results"
SENSOR_EVENTS = "sensor_events"
DEVICE_LOGS = "device_logs"
DEVICE_HEARTBEATS = "device_heartbeats"

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url, serverSelectionTimeoutMS=settings.mongodb_timeout_ms)
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency returning the application database."""
    return get_mongo_client()[settings.mongodb_database]


def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
    _client = None


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create all MongoDB indexes (idempotent)."""
    await db[TELEMETRY].create_index([("vehicle_id", ASCENDING)])
    await db[TELEMETRY].create_index([("timestamp", ASCENDING)])
    await db[TELEMETRY].create_index([("vehicle_id", ASCENDING), ("timestamp", ASCENDING)])
    # device_id / hardware_id are optional (older documents only have vehicle_id): sparse-friendly indexes.
    for collection in (TELEMETRY, SENSOR_EVENTS, DEVICE_LOGS):
        await db[collection].create_index([("device_id", ASCENDING), ("timestamp", ASCENDING)])
        await db[collection].create_index([("hardware_id", ASCENDING)], sparse=True)
    await db[AUDIO_ANALYSIS].create_index([("vehicle_id", ASCENDING)])
    await db[AUDIO_ANALYSIS].create_index([("predicted_class", ASCENDING)])
    await db[SENSOR_EVENTS].create_index([("vehicle_id", ASCENDING), ("timestamp", ASCENDING)])
    await db[DEVICE_LOGS].create_index([("vehicle_id", ASCENDING), ("timestamp", ASCENDING)])
    await db[DEVICE_HEARTBEATS].create_index([("device_id", ASCENDING)])
    await db[DEVICE_HEARTBEATS].create_index([("device_id", ASCENDING), ("received_at", ASCENDING)])
