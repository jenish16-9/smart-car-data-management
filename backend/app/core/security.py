from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    email: str
    role: str


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> CurrentUser:
    # Development identity adapter. Replace this with the shared identity provider.
    if credentials is None or credentials.credentials != "development-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(id="user-1", email="admin@example.com", role="admin")


AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
