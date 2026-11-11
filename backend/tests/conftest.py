"""Isolated test setup.

Every test gets a fresh in-memory SQLite database and an in-memory mongomock database,
injected through FastAPI dependency overrides. No real PostgreSQL or MongoDB is ever
contacted, so nothing here can delete or modify real data.
"""

import os

# Must be set before the application settings are imported.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "JWT_SECRET": "test-only-secret-not-for-production",
        "POSTGRES_URL": "sqlite+aiosqlite://",
        "MONGODB_URL": "mongodb://invalid.invalid:1",  # unreachable on purpose
        "BCRYPT_ROUNDS": "4",
        "DEV_ADMIN_EMAIL": "",
        "DEV_ADMIN_PASSWORD": "",
    }
)

from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.security import hash_password  # noqa: E402
from app.db.mongodb import get_mongo_db  # noqa: E402
from app.db.postgres import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import user_repository  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-test-pass"
USER_PASSWORD = "user-test-pass"


@pytest_asyncio.fixture
async def sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def mongo_db():
    return AsyncMongoMockClient()["smart_car_test"]


@pytest_asyncio.fixture
async def client(sessionmaker, mongo_db) -> AsyncIterator[httpx.AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_mongo_db] = lambda: mongo_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def _login(client: httpx.AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(client, sessionmaker) -> dict[str, str]:
    async with sessionmaker() as session:
        await user_repository.create(
            session, name="Admin", email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD), role="admin"
        )
        await session.commit()
    return await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest_asyncio.fixture
async def user_headers(client) -> dict[str, str]:
    payload = {"name": "Regular User", "email": "user@example.com", "password": USER_PASSWORD}
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    return await _login(client, payload["email"], USER_PASSWORD)


@pytest_asyncio.fixture
async def vehicle(client, admin_headers) -> dict:
    response = await client.post(
        "/vehicles",
        json={"vehicle_code": "CAR-1024", "vehicle_type": "Sedan", "status": "connected"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()
