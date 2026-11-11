from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, get_current_user
from app.db.postgres import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)) -> UserOut:
    return UserOut.model_validate(await auth_service.register(session, payload))


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> LoginResponse:
    return await auth_service.login(session, payload.email, payload.password)


@router.post("/logout")
async def logout(
    context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    await auth_service.logout(session, context.session_id)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
