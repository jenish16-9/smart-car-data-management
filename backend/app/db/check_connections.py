"""Verify the configured PostgreSQL and MongoDB connections:  python -m app.db.check_connections

Read-only for PostgreSQL. For MongoDB it inserts one clearly marked probe document into
``device_logs``, reads it back and deletes only that document. Secrets are never printed.
"""

import asyncio
import sys
import uuid
from urllib.parse import urlsplit

from sqlalchemy import text

from app.core.config import settings
from app.db.mongodb import DEVICE_LOGS, close_mongo, get_mongo_db
from app.db.postgres import dispose_engine, get_engine
from app.models.common import utcnow


def _describe(url: str) -> str:
    """Local vs remote only: never print hosts, users or passwords."""
    host = urlsplit(url).hostname
    return "local server" if host in (None, "localhost", "127.0.0.1", "::1") else "remote (cloud) server"


async def check_postgres() -> bool:
    print(f"PostgreSQL: {_describe(settings.postgres_url)}")
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
            tables = (
                await conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"))
            ).scalar_one()
            has_version = (await conn.execute(text("SELECT to_regclass('public.alembic_version')"))).scalar_one()
            version = (
                (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
                if has_version
                else None
            )
        print(f"  OK - {tables} public tables, alembic revision: {version or 'not migrated'}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED - {type(exc).__name__}")
        return False


async def check_mongo() -> bool:
    print(f"MongoDB: {_describe(settings.mongodb_url)}, database={settings.mongodb_database}")
    probe_id = f"connection-check-{uuid.uuid4().hex}"
    collection = get_mongo_db()[DEVICE_LOGS]
    try:
        await collection.insert_one(
            {"vehicle_id": "__connection_check__", "event_type": probe_id, "message": "probe", "timestamp": utcnow()}
        )
        found = await collection.find_one({"event_type": probe_id})
        await collection.delete_one({"event_type": probe_id})
        indexes = sorted((await collection.index_information()).keys())
        print(f"  OK - insert/read/delete round trip: {bool(found)}; device_logs indexes: {indexes}")
        return bool(found)
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED - {type(exc).__name__}")
        return False


async def _main() -> int:
    try:
        results = [await check_postgres(), await check_mongo()]
    finally:
        await dispose_engine()
        close_mongo()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
