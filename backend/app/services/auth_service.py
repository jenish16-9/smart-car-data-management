import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, dummy_hash, hash_password, verify_password
from app.models.common import utcnow
from app.models.user import User
from app.repositories import user_repository
from app.schemas.auth import LoginResponse, RegisterRequest
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)


async def register(session: AsyncSession, payload: RegisterRequest) -> User:
    if await user_repository.get_by_email(session, payload.email):
        raise ConflictError("An account with this email already exists")
    # Self-registration always creates a regular user; admins are created out of band.
    user = await user_repository.create(
        session,
        name=payload.name.strip(),
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    await session.commit()
    return user


async def create_user_by_admin(session: AsyncSession, *, name: str, email: str, password: str, role: str) -> User:
    if await user_repository.get_by_email(session, email):
        raise ConflictError("An account with this email already exists")
    user = await user_repository.create(
        session,
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    await session.commit()
    return user


async def login(session: AsyncSession, email: str, password: str) -> LoginResponse:
    user = await user_repository.get_by_email(session, email)
    password_hash = user.password_hash if user else dummy_hash()
    if not verify_password(password, password_hash) or user is None:
        raise UnauthorizedError("Invalid email or password")

    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    stored = await user_repository.create_session(session, user_id=user.id, expires_at=utcnow() + lifetime)
    await session.commit()
    token = create_access_token(user_id=user.id, session_id=stored.id, expires_at=stored.expires_at)
    return LoginResponse(
        access_token=token,
        expires_in=int(lifetime.total_seconds()),
        user=UserOut.model_validate(user),
    )


async def logout(session: AsyncSession, session_id) -> None:
    await user_repository.revoke_session(session, session_id)
    await session.commit()


async def update_profile(session: AsyncSession, user: User, *, name: str | None, email: str | None) -> User:
    fields: dict[str, str] = {}
    if name is not None:
        fields["name"] = name.strip()
    if email is not None and email.lower() != user.email:
        if await user_repository.get_by_email(session, email):
            raise ConflictError("An account with this email already exists")
        fields["email"] = email.lower()
    if fields:
        await user_repository.update(session, user, **fields)
        await session.commit()
    return user


async def seed_dev_admin(session: AsyncSession) -> None:
    """Create the development administrator from DEV_ADMIN_* (development only)."""
    if settings.environment != "development" or not settings.dev_admin_email or not settings.dev_admin_password:
        return
    if await user_repository.get_by_email(session, settings.dev_admin_email):
        return
    await user_repository.create(
        session,
        name="Admin",
        email=settings.dev_admin_email,
        password_hash=hash_password(settings.dev_admin_password),
        role="admin",
    )
    await session.commit()
    logger.info("Seeded development administrator %s", settings.dev_admin_email)
