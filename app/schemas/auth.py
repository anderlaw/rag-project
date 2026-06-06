from pydantic import BaseModel, Field

from app.core.auth import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class CurrentUserResponse(BaseModel):
    username: str
    role: UserRole


class LogoutResponse(BaseModel):
    success: bool
