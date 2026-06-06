from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import base64
import hashlib
import hmac
import json
import time

from app.core.config import Settings

SESSION_COOKIE_NAME = "rag_session"


class UserRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    NORMAL_USER = "NORMAL_USER"


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: UserRole


class AuthError(Exception):
    pass


def authenticate_user(settings: Settings, username: str, password: str) -> AuthUser | None:
    for user, stored_password in _configured_users(settings).items():
        if user.username == username and hmac.compare_digest(stored_password, password):
            return user
    return None


def create_session_token(settings: Settings, user: AuthUser) -> str:
    if not settings.auth_session_secret:
        raise AuthError("auth session secret is not configured")
    expires_at = int(time.time()) + settings.auth_token_expire_minutes * 60
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": expires_at,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_part = _base64_url_encode(payload_bytes)
    signature = _sign(settings.auth_session_secret, payload_part)
    return f"{payload_part}.{signature}"


def verify_session_token(settings: Settings, token: str | None) -> AuthUser:
    if not token:
        raise AuthError("missing session")
    if not settings.auth_session_secret:
        raise AuthError("auth session secret is not configured")

    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("invalid session") from exc

    expected_signature = _sign(settings.auth_session_secret, payload_part)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthError("invalid session")

    try:
        payload = json.loads(_base64_url_decode(payload_part))
        username = str(payload["sub"])
        role = UserRole(str(payload["role"]))
        expires_at = int(payload["exp"])
    except Exception as exc:
        raise AuthError("invalid session") from exc

    if expires_at < int(time.time()):
        raise AuthError("session expired")

    configured = _configured_users(settings)
    user = AuthUser(username=username, role=role)
    if user not in configured:
        raise AuthError("session user is no longer configured")
    return user


def _configured_users(settings: Settings) -> dict[AuthUser, str]:
    users: dict[AuthUser, str] = {}
    if settings.super_admin_username and settings.super_admin_password:
        users[AuthUser(username=settings.super_admin_username, role=UserRole.SUPER_ADMIN)] = settings.super_admin_password
    if settings.normal_user_username and settings.normal_user_password:
        users[AuthUser(username=settings.normal_user_username, role=UserRole.NORMAL_USER)] = settings.normal_user_password
    return users


def _sign(secret: str, payload_part: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).hexdigest()


def _base64_url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64_url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
