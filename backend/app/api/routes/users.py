from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_admin
from app.db.postgres import get_session
from app.models.user import User
from app.repositories import user_repository
from app.schemas.user import AdminUserCreate, UserOut, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut])
async def list_users(_: User = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> list[UserOut]:
    return [UserOut.model_validate(user) for user in await user_repository.list_users(session)]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: AdminUserCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    created = await auth_service.create_user_by_admin(
        session, name=payload.name, email=payload.email, password=payload.password, role=payload.role
    )
    return UserOut.model_validate(created)


@router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> UserOut:
    updated = await auth_service.update_profile(session, user, name=payload.name, email=payload.email)
    return UserOut.model_validate(updated)
