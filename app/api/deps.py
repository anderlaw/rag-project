from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.auth import AuthError, AuthUser, UserRole, verify_session_token
from app.core.config import get_settings
from app.core.database import get_session


def get_db() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


def get_current_user(request: Request) -> AuthUser:
    settings = get_settings()
    try:
        return verify_session_token(settings, request.cookies.get("rag_session"))
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_authenticated_user(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    return user


def require_super_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="super admin role required")
    return user
