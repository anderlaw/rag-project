from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_current_user
from app.core.auth import SESSION_COOKIE_NAME, AuthUser, authenticate_user, create_session_token
from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse, LoginRequest, LogoutResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=CurrentUserResponse)
def login(request: LoginRequest, response: Response) -> CurrentUserResponse:
    settings = get_settings()
    user = authenticate_user(settings, request.username, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid username or password")

    token = create_session_token(settings, user)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=settings.auth_token_expire_minutes * 60,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )
    return CurrentUserResponse(username=user.username, role=user.role)


@router.get("/me", response_model=CurrentUserResponse)
def me(user: AuthUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(username=user.username, role=user.role)


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=True, httponly=True, samesite="none")
    return LogoutResponse(success=True)
