"""Startup initialisation: MongoDB indexes and the development administrator.

Schema creation is handled by Alembic (`alembic upgrade head`), not here.
Run manually with:  python -m app.db.init_db
"""

import asyncio
import logging

from app.db.mongodb import close_mongo, ensure_indexes, get_mongo_db
from app.db.postgres import dispose_engine, get_sessionmaker
from app.services import auth_service

logger = logging.getLogger(__name__)


async def init_db() -> None:
    await ensure_indexes(get_mongo_db())
    async with get_sessionmaker()() as session:
        await auth_service.seed_dev_admin(session)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        await init_db()
    finally:
        await dispose_engine()
        close_mongo()


if __name__ == "__main__":
    asyncio.run(_main())
