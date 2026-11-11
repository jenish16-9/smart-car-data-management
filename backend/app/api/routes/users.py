from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
async def read_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> UserOut:
    updated = await auth_service.update_profile(session, user, name=payload.name, email=payload.email)
    return UserOut.model_validate(updated)
