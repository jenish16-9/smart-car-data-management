from fastapi import APIRouter, HTTPException

from app.schemas.auth import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if payload.password != "admin123":
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = UserResponse(
        id="user-1", email=payload.email, name="Admin", role="admin"
    )
    return LoginResponse(access_token="development-token", user=user)


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"message": "Logged out successfully"}

