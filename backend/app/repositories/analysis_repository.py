"""MongoDB access for audio_analysis_results (ML output) and its aggregations."""

from datetime import UTC, datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import AUDIO_ANALYSIS
from app.repositories.telemetry_repository import aware, normalize


def _scope(vehicle_codes: list[str] | None) -> dict[str, Any]:
    return {} if vehicle_codes is None else {"vehicle_id": {"$in": vehicle_codes}}


async def insert_result(db: AsyncIOMotorDatabase, document: dict[str, Any]) -> None:
    await db[AUDIO_ANALYSIS].insert_one(dict(document))


async def get_for_audio(db: AsyncIOMotorDatabase, audio_record_id: str) -> dict[str, Any] | None:
    document = await db[AUDIO_ANALYSIS].find_one({"audio_record_id": audio_record_id}, {"_id": 0})
    return normalize(document) if document else None


async def get_for_event(db: AsyncIOMotorDatabase, event_id: str) -> dict[str, Any] | None:
    document = await db[AUDIO_ANALYSIS].find_one({"event_id": event_id}, {"_id": 0})
    return normalize(document) if document else None


async def get_for_audios(db: AsyncIOMotorDatabase, audio_record_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch lookup (one query) keyed by audio_record_id."""
    if not audio_record_ids:
        return {}
    cursor = db[AUDIO_ANALYSIS].find({"audio_record_id": {"$in": audio_record_ids}}, {"_id": 0})
    return {doc["audio_record_id"]: normalize(doc) async for doc in cursor}


async def summary(db: AsyncIOMotorDatabase, vehicle_codes: list[str] | None) -> dict[str, float]:
    pipeline = [
        {"$match": _scope(vehicle_codes)},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "confidence": {"$avg": "$confidence"},
                "detections": {"$sum": {"$cond": [{"$ne": ["$predicted_class", "normal"]}, 1, 0]}},
            }
        },
    ]
    rows = await db[AUDIO_ANALYSIS].aggregate(pipeline).to_list(1)
    if not rows:
        return {"total": 0, "detections": 0, "average_confidence": 0.0}
    row = rows[0]
    return {"total": row["total"], "detections": row["detections"], "average_confidence": row["confidence"] or 0.0}


async def events_over_time(
    db: AsyncIOMotorDatabase, vehicle_codes: list[str] | None, *, days: int
) -> list[dict[str, Any]]:
    since = datetime.now(UTC) - timedelta(days=days)
    pipeline = [
        {"$match": {**_scope(vehicle_codes), "created_at": {"$gte": since}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    return [{"date": row["_id"], "count": row["count"]} async for row in db[AUDIO_ANALYSIS].aggregate(pipeline)]


async def events_by_type(db: AsyncIOMotorDatabase, vehicle_codes: list[str] | None) -> list[dict[str, Any]]:
    pipeline = [
        {"$match": _scope(vehicle_codes)},
        {
            "$group": {
                "_id": "$predicted_class",
                "count": {"$sum": 1},
                "confidence": {"$avg": "$confidence"},
                "last_detected": {"$max": "$created_at"},
            }
        },
        {"$sort": {"count": -1}},
    ]
    return [
        {
            "event_type": row["_id"],
            "count": row["count"],
            "average_confidence": row["confidence"] or 0.0,
            "last_detected": aware(row["last_detected"]),
        }
        async for row in db[AUDIO_ANALYSIS].aggregate(pipeline)
    ]
