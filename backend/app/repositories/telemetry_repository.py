"""MongoDB access for telemetry_events, sensor_events and device_logs."""

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.db.mongodb import DEVICE_HEARTBEATS, DEVICE_LOGS, SENSOR_EVENTS, TELEMETRY


def aware(value: Any) -> Any:
    """Mongo returns naive UTC datetimes; make them timezone-aware."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def normalize(document: dict[str, Any]) -> dict[str, Any]:
    return {key: aware(value) for key, value in document.items() if key != "_id"}


async def insert_telemetry(db: AsyncIOMotorDatabase, document: dict[str, Any]) -> None:
    await db[TELEMETRY].insert_one(dict(document))


async def list_telemetry(
    db: AsyncIOMotorDatabase,
    vehicle_code: str,
    *,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"vehicle_id": vehicle_code}
    if start or end:
        query["timestamp"] = {**({"$gte": start} if start else {}), **({"$lte": end} if end else {})}
    cursor = db[TELEMETRY].find(query, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit)
    return [normalize(doc) async for doc in cursor]


async def latest_telemetry(db: AsyncIOMotorDatabase, vehicle_code: str) -> dict[str, Any] | None:
    document = await db[TELEMETRY].find_one({"vehicle_id": vehicle_code}, {"_id": 0}, sort=[("timestamp", DESCENDING)])
    return normalize(document) if document else None


async def insert_sensor_events(db: AsyncIOMotorDatabase, documents: list[dict[str, Any]]) -> None:
    if documents:
        await db[SENSOR_EVENTS].insert_many([dict(doc) for doc in documents])


async def insert_device_log(
    db: AsyncIOMotorDatabase,
    *,
    vehicle_code: str,
    event_type: str,
    message: str,
    timestamp: datetime,
    device_id: str | None = None,
    hardware_id: str | None = None,
) -> None:
    document: dict[str, Any] = {
        "vehicle_id": vehicle_code,
        "event_type": event_type,
        "message": message,
        "timestamp": timestamp,
    }
    if device_id:
        document.update(device_id=device_id, hardware_id=hardware_id)
    await db[DEVICE_LOGS].insert_one(document)


async def list_device_logs(db: AsyncIOMotorDatabase, vehicle_code: str, limit: int) -> list[dict[str, Any]]:
    cursor = (
        db[DEVICE_LOGS]
        .find({"vehicle_id": vehicle_code}, {"_id": 0})
        .sort([("timestamp", DESCENDING), ("_id", DESCENDING)])
        .limit(limit)
    )
    return [normalize(doc) async for doc in cursor]


async def insert_device_heartbeat(db: AsyncIOMotorDatabase, document: dict[str, Any]) -> None:
    await db[DEVICE_HEARTBEATS].insert_one(dict(document))


async def list_device_heartbeats(db: AsyncIOMotorDatabase, device_id: str, limit: int) -> list[dict[str, Any]]:
    cursor = (
        db[DEVICE_HEARTBEATS].find({"device_id": device_id}, {"_id": 0}).sort("received_at", DESCENDING).limit(limit)
    )
    return [normalize(doc) async for doc in cursor]
