"""FastAPI dependencies: authentication and authorization."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.postgres import get_session
from app.models.user import User
from app.repositories import user_repository

_bearer = HTTPBearer(auto_error=False)
optional_bearer = _bearer  # for endpoints with an alternative credential (device key)


@dataclass
class AuthContext:
    user: User
    session_id: UUID


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def _parse_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    if credentials is None:
        raise _unauthorized("Missing authentication token")
    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise _unauthorized("Invalid or expired token")
    user_id, session_id = _parse_uuid(claims.get("sub")), _parse_uuid(claims.get("jti"))
    if user_id is None or session_id is None:
        raise _unauthorized("Invalid token")

    stored = await user_repository.get_session(session, session_id)
    if stored is None or stored.user_id != user_id or stored.revoked_at is not None:
        raise _unauthorized("Session is no longer valid")
    if stored.expires_at <= datetime.now(UTC):
        raise _unauthorized("Session has expired")
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise _unauthorized("User no longer exists")
    return AuthContext(user=user, session_id=session_id)


async def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user
