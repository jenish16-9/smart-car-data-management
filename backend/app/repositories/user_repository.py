from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import utcnow
from app.models.user import User, UserSession


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, *, name: str, email: str, password_hash: str, role: str) -> User:
    user = User(name=name, email=email.lower(), password_hash=password_hash, role=role)
    session.add(user)
    await session.flush()
    return user


async def update(session: AsyncSession, user: User, **fields: object) -> User:
    for key, value in fields.items():
        setattr(user, key, value)
    await session.flush()
    return user


async def create_session(session: AsyncSession, *, user_id: UUID, expires_at: datetime) -> UserSession:
    stored = UserSession(user_id=user_id, expires_at=expires_at)
    session.add(stored)
    await session.flush()
    return stored


async def get_session(session: AsyncSession, session_id: UUID) -> UserSession | None:
    return await session.get(UserSession, session_id)


async def revoke_session(session: AsyncSession, session_id: UUID) -> None:
    stored = await session.get(UserSession, session_id)
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = utcnow()
        await session.flush()
